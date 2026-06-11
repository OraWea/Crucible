import datetime
import hashlib
import importlib
import mimetypes
import os
import requests
import secrets
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_PARENT = os.path.dirname(PROJECT_DIR)
if PROJECT_PARENT not in sys.path:
    sys.path.insert(0, PROJECT_PARENT)

from Crucible.config import Config
from Crucible.utils.db_manager import db_manager
from Crucible.utils.fs_router import fs_router
from Crucible.utils.graph_builder import knowledge_graph_builder
from Crucible.utils.note_analyzer import note_analyzer
from Crucible.utils.source_index import source_index
from Crucible.utils.templates import template_manager
from Crucible.utils.wiki_editor import wiki_editor


Config.init_paths()

app = FastAPI(title="Crucible API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_sessions: Dict[str, Dict[str, str]] = {}
_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _process_worker_count() -> int:
    try:
        return max(1, int(os.environ.get("CRUCIBLE_PROCESS_WORKERS", "2")))
    except ValueError:
        return 2


_process_executor = ThreadPoolExecutor(
    max_workers=_process_worker_count(),
    thread_name_prefix="crucible-process",
)


def _load_processing_workflow():
    """加载处理流水线；兼容开发期后端进程缓存了旧模块的情况。"""
    importlib.invalidate_caches()
    module = importlib.import_module("Crucible.utils.processing_workflow")
    if not hasattr(module, "ProcessingOptions") or not hasattr(module, "ProcessingWorkflow"):
        module = importlib.reload(module)
    if not hasattr(module, "ProcessingOptions") or not hasattr(module, "ProcessingWorkflow"):
        raise RuntimeError("处理流水线模块加载异常：缺少 ProcessingOptions 或 ProcessingWorkflow，请重启后端服务。")
    return module.ProcessingOptions, module.ProcessingWorkflow


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class CreateFolderRequest(BaseModel):
    parent_path: str = ""
    name: str


class CreateNoteRequest(BaseModel):
    parent_path: str = ""
    name: str
    template: str = "空白"
    content: Optional[str] = None


class RenameRequest(BaseModel):
    path: str
    new_name: str


class MoveRequest(BaseModel):
    path: str
    target_dir: str


class DeleteRequest(BaseModel):
    path: str
    confirm_name: str


class RestoreRequest(BaseModel):
    trash_id: str


class SaveNoteRequest(BaseModel):
    content: str


class PreviewRequest(BaseModel):
    content: str


class OpenWikiTargetRequest(BaseModel):
    target: str


class SearchRequest(BaseModel):
    keyword: str
    limit: int = Field(default=100, ge=1, le=500)


class RuntimeSettingsRequest(BaseModel):
    provider: str
    api_base: str
    llm_model: str
    vlm_model: str
    fact_model: str
    api_key: Optional[str] = None
    whisper_model: Optional[str] = None
    whisper_device: Optional[str] = None


class ConfigTestRequest(BaseModel):
    provider: str
    api_base: str
    llm_model: str
    api_key: Optional[str] = None


class ProcessRequest(BaseModel):
    sources: List[str]
    whisper_lang: str = "auto"
    asr_engine: str = "dashscope"
    provider: str = Config.LLM_PROVIDER
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    llm_model: Optional[str] = None
    vlm_model: Optional[str] = None
    fact_model: Optional[str] = None


def _init_default_users() -> None:
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
            )
            """
        )
        cursor.execute("SELECT COUNT(*) AS cnt FROM users")
        if cursor.fetchone()["cnt"] == 0:
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", _password_hash("admin123"), "admin"),
            )
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("user", _password_hash("user123"), "user"),
            )
            conn.commit()
            db_manager.add_log("INFO", "Backend", "Init_Default_Users", "Injected default admin/user accounts")


def _password_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _current_user(authorization: str = Header(default="")) -> Dict[str, str]:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    user = _sessions.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


def _resolve_token(authorization: str = Header(default=""), token: Optional[str] = None) -> Dict[str, str]:
    """同时支持 Authorization header 和 ?token= query param，供 <video src> 使用。"""
    raw_token: Optional[str] = None
    if authorization.startswith("Bearer "):
        raw_token = authorization.removeprefix("Bearer ").strip()
    elif token:
        raw_token = token.strip()
    if not raw_token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    user = _sessions.get(raw_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


def _admin_user(user: Dict[str, str] = Depends(_current_user)) -> Dict[str, str]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def _safe_vault_path(path: str = "") -> str:
    if not path:
        return Config.OBSIDIAN_VAULT_PATH
    normalized = path.replace("\\", os.sep).replace("/", os.sep)
    if os.path.isabs(normalized):
        abs_path = os.path.abspath(normalized)
    else:
        abs_path = os.path.abspath(os.path.join(Config.OBSIDIAN_VAULT_PATH, normalized.lstrip("\\/")))
    vault_root = os.path.abspath(Config.OBSIDIAN_VAULT_PATH)
    if os.path.commonpath([vault_root, abs_path]) != vault_root:
        raise HTTPException(status_code=400, detail="Path escapes vault")
    return abs_path


def _relative(file_path: str) -> str:
    return fs_router.get_relative_path(file_path)


def _job_payload_snapshot(payload: BaseModel) -> Dict[str, Any]:
    """返回可展示/可持久化的任务参数快照，避免泄露 API Key。"""
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    data["api_key"] = None
    return data


def _sync_path_reference(old_path: str, new_path: str, was_dir: bool) -> None:
    old_rel = _relative(old_path)
    new_rel = _relative(new_path)
    if was_dir:
        source_index.update_note_path_prefix(old_rel, new_rel)
    else:
        source_index.update_note_path_references(old_rel, new_rel)


def _serialize_tree(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    serialized = []
    for node in nodes:
        item = dict(node)
        if "path" in item:
            item["abs_path"] = item["path"]
            item["path"] = _relative(item["path"])
        if item.get("children"):
            item["children"] = _serialize_tree(item["children"])
        serialized.append(item)
    return serialized


def _note_payload(file_path: str, anchor: str = "") -> Dict[str, Any]:
    if not os.path.exists(file_path) or not file_path.endswith(".md"):
        raise HTTPException(status_code=404, detail="Note not found")
    content = wiki_editor.read_wiki(file_path)
    analysis = note_analyzer.analyze(file_path)
    return {
        "path": _relative(file_path),
        "abs_path": file_path,
        "name": os.path.basename(file_path),
        "anchor": anchor,
        "content": content,
        "preview_html": wiki_editor.render_markdown_preview(content),
        "frontmatter": analysis["frontmatter"],
        "outgoing_links": analysis["outgoing_links"],
        "backlinks": analysis["backlinks"],
        "source_mentions": analysis["source_mentions"],
        "tags": analysis["tags"],
    }


def _resolve_wiki_target(raw_target: str) -> tuple[str, str]:
    items = wiki_editor.extract_wiki_link_items(f"[[{raw_target}]]")
    if not items:
        raise HTTPException(status_code=400, detail="Invalid wiki target")
    item = items[0]
    target = item["target"]
    anchor = item["anchor"]
    if target.endswith(".md") or "/" in target:
        candidate = _safe_vault_path(target)
        if not candidate.endswith(".md"):
            candidate += ".md"
        file_path = candidate
    else:
        file_path = fs_router.locate_concept_file(target) or fs_router.resolve_note_path("", target)
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        title = os.path.splitext(os.path.basename(file_path))[0]
        wiki_editor.write_wiki_atomic(file_path, f"---\ntags: [linked-note]\n---\n\n# {title}\n")
        fs_router.scan_vault()
    return file_path, anchor


@app.on_event("startup")
def startup() -> None:
    _init_default_users()
    fs_router.scan_vault()


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "vault_path": Config.OBSIDIAN_VAULT_PATH,
        "database_path": Config.DATABASE_PATH,
        "provider": Config.LLM_PROVIDER,
    }


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> Dict[str, Any]:
    _init_default_users()
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT username, role FROM users WHERE username = ? AND password_hash = ?",
            (payload.username.strip(), _password_hash(payload.password.strip())),
        )
        row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = secrets.token_urlsafe(32)
    user = {"username": row["username"], "role": row["role"]}
    _sessions[token] = user
    db_manager.add_log("INFO", "Backend", "User_Login", f"用户 {user['username']} 登录 Web API")
    return {"token": token, "user": user}


@app.post("/api/auth/register")
def register(payload: RegisterRequest) -> Dict[str, Any]:
    role = payload.role if payload.role in ("admin", "user") else "user"
    username = payload.username.strip()
    password = payload.password.strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名或密码不能为空")
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, _password_hash(password), role),
            )
            conn.commit()
    except Exception:
        raise HTTPException(status_code=409, detail="用户名已存在")
    db_manager.add_log("INFO", "Backend", "User_Register", f"注册用户 {username}")
    return {"username": username, "role": role}


@app.get("/api/auth/me")
def me(user: Dict[str, str] = Depends(_current_user)) -> Dict[str, str]:
    return user


@app.post("/api/auth/logout")
def logout(authorization: str = Header(default="")) -> Dict[str, bool]:
    if authorization.startswith("Bearer "):
        _sessions.pop(authorization.removeprefix("Bearer ").strip(), None)
    return {"ok": True}


@app.get("/api/config/providers")
def providers() -> Dict[str, Any]:
    return {
        "providers": [
            {"key": key, "label": label, "preset": Config.get_provider_preset(key)}
            for key, label in Config.get_provider_options()
        ],
        "current": {
            "provider": Config.LLM_PROVIDER,
            "api_base": Config.LLM_API_BASE,
            "llm_model": Config.LLM_MODEL_NAME,
            "vlm_model": Config.VLM_MODEL_NAME,
            "fact_model": Config.FACT_CHECKER_MODEL_NAME,
            "whisper_model": Config.WHISPER_MODEL_NAME,
            "whisper_device": Config.WHISPER_DEVICE,
        },
    }


@app.post("/api/config/runtime")
def save_runtime_settings(payload: RuntimeSettingsRequest, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    Config.save_local_settings(
        provider=payload.provider,
        api_base=payload.api_base,
        llm_model=payload.llm_model,
        vlm_model=payload.vlm_model,
        fact_model=payload.fact_model,
        api_key=payload.api_key,
        whisper_model=payload.whisper_model,
        whisper_device=payload.whisper_device,
    )
    Config.update_llm_runtime(
        api_key=payload.api_key,
        api_base=payload.api_base,
        model_name=payload.llm_model,
        provider=payload.provider,
        vlm_model_name=payload.vlm_model,
        fact_checker_model_name=payload.fact_model,
    )
    db_manager.add_log("INFO", "Backend", "Save_Runtime_Settings", f"用户 {user['username']} 更新模型配置")
    return {"ok": True, "has_valid_api_key": Config.has_valid_api_key(payload.api_key)}


@app.post("/api/config/test")
def test_runtime_settings(payload: ConfigTestRequest, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    provider = payload.provider.strip()
    api_base = payload.api_base.rstrip("/")
    if provider in ("ollama", "lmstudio"):
        try:
            response = requests.get(f"{api_base}/models", timeout=5)
            return {
                "ok": response.status_code < 500,
                "status": response.status_code,
                "message": "本地 OpenAI-compatible 服务可访问" if response.status_code < 500 else "本地服务返回错误",
                "has_valid_api_key": True,
            }
        except Exception as exc:
            return {"ok": False, "status": 0, "message": f"本地服务不可访问: {exc}", "has_valid_api_key": True}

    if not payload.api_key or payload.api_key.strip() == "your-api-key":
        return {"ok": False, "status": 0, "message": "缺少有效 API Key", "has_valid_api_key": False}

    try:
        response = requests.get(
            f"{api_base}/models",
            headers={"Authorization": f"Bearer {payload.api_key}"},
            timeout=8,
        )
        return {
            "ok": response.status_code < 500,
            "status": response.status_code,
            "message": "Provider 配置可访问" if response.status_code < 500 else "Provider 返回错误",
            "has_valid_api_key": True,
        }
    except Exception as exc:
        return {"ok": False, "status": 0, "message": f"Provider 测试失败: {exc}", "has_valid_api_key": True}


@app.get("/api/templates")
def templates(user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    return {"templates": ["空白"] + template_manager.list_templates()}


@app.get("/api/vault/tree")
def vault_tree(user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    fs_router.scan_vault()
    return {
        "root": Config.OBSIDIAN_VAULT_PATH,
        "nodes": _serialize_tree(fs_router.get_vault_tree_nodes()),
        "summary": fs_router.get_vault_structure_summary(),
    }


@app.post("/api/vault/folders")
def create_folder(payload: CreateFolderRequest, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    parent = _safe_vault_path(payload.parent_path)
    path = fs_router.create_folder(parent, payload.name)
    db_manager.add_log("INFO", "Backend", "Create_Folder", _relative(path))
    return {"path": _relative(path), "abs_path": path}


@app.post("/api/vault/notes")
def create_note(payload: CreateNoteRequest, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    parent = _safe_vault_path(payload.parent_path)
    title = os.path.splitext(payload.name.strip())[0]
    if payload.content is not None:
        content = payload.content
    elif payload.template == "空白":
        content = f"---\ntags: [manual-note]\n---\n\n# {title}\n"
    else:
        content = template_manager.render_template(payload.template, title)
    path = fs_router.create_note(parent, payload.name, content)
    fs_router.scan_vault()
    db_manager.add_log("INFO", "Backend", "Create_Note", _relative(path))
    return _note_payload(path)


@app.post("/api/vault/rename")
def rename_path(payload: RenameRequest, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    path = _safe_vault_path(payload.path)
    was_dir = os.path.isdir(path)
    new_path = fs_router.rename_path(path, payload.new_name)
    _sync_path_reference(path, new_path, was_dir)
    db_manager.add_log("INFO", "Backend", "Rename_Path", f"{_relative(path)} -> {_relative(new_path)}")
    return {"path": _relative(new_path), "abs_path": new_path}


@app.post("/api/vault/move")
def move_path(payload: MoveRequest, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    path = _safe_vault_path(payload.path)
    target_dir = _safe_vault_path(payload.target_dir)
    was_dir = os.path.isdir(path)
    new_path = fs_router.move_path(path, target_dir)
    _sync_path_reference(path, new_path, was_dir)
    db_manager.add_log("INFO", "Backend", "Move_Path", f"{_relative(path)} -> {_relative(new_path)}")
    return {"path": _relative(new_path), "abs_path": new_path}


@app.post("/api/vault/delete")
def delete_path(payload: DeleteRequest, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    path = _safe_vault_path(payload.path)
    manifest = fs_router.trash_path(path, payload.confirm_name)
    db_manager.add_log("WARNING", "Backend", "Trash_Path", f"用户 {user['username']} 移入回收站: {manifest['original_path']}")
    return {"ok": True, "trash": manifest}


@app.get("/api/vault/trash")
def list_trash(user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    return {"items": fs_router.list_trash()}


@app.post("/api/vault/restore")
def restore_path(payload: RestoreRequest, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    manifest = fs_router.restore_trash(payload.trash_id)
    original_path = manifest.get("original_path", "")
    restored_path = manifest.get("restored_path", "")
    if original_path and restored_path and original_path != restored_path:
        if manifest.get("type") == "directory":
            source_index.update_note_path_prefix(original_path, restored_path)
        else:
            source_index.update_note_path_references(original_path, restored_path)
    db_manager.add_log("INFO", "Backend", "Restore_Path", f"用户 {user['username']} 恢复: {restored_path}")
    return {"ok": True, "restored": manifest}


@app.get("/api/vault/organization-rules")
def organization_rules(user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    path = fs_router.ensure_organization_rules()
    fs_router.scan_vault()
    return _note_payload(path)


@app.get("/api/notes/{note_path:path}")
def get_note(note_path: str, anchor: str = "", user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    return _note_payload(_safe_vault_path(note_path), anchor)


@app.put("/api/notes/{note_path:path}")
def save_note(note_path: str, payload: SaveNoteRequest, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    file_path = _safe_vault_path(note_path)
    success = wiki_editor.write_wiki_atomic(file_path, payload.content)
    if not success:
        raise HTTPException(status_code=500, detail="无法原子写入文件")
    fs_router.scan_vault()
    db_manager.add_log("INFO", "Backend", "Manual_Save", f"用户 {user['username']} 保存笔记: {_relative(file_path)}")
    return _note_payload(file_path)


@app.post("/api/notes/preview")
def preview_note(payload: PreviewRequest, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, str]:
    return {"preview_html": wiki_editor.render_markdown_preview(payload.content)}


@app.get("/api/assets")
def get_vault_asset(path: str) -> FileResponse:
    rel_path = (path or "").split("#", 1)[0].strip()
    file_path = _safe_vault_path(rel_path)
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        raise HTTPException(status_code=400, detail="Unsupported asset type")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Asset not found")
    media_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    return FileResponse(file_path, media_type=media_type)


@app.post("/api/notes/open-wiki-target")
def open_wiki_target(payload: OpenWikiTargetRequest, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    file_path, anchor = _resolve_wiki_target(payload.target)
    return _note_payload(file_path, anchor)


@app.post("/api/search")
def search(payload: SearchRequest, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    results = source_index.search(payload.keyword, limit=payload.limit)
    return {"results": results, "count": len(results)}


@app.get("/api/graph")
def graph(user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    graph_data = knowledge_graph_builder.build_graph()
    return {"graph": graph_data, "summary": knowledge_graph_builder.build_summary()}


@app.post("/api/uploads")
async def upload_files(files: List[UploadFile] = File(...), user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    upload_dir = os.path.join(Config.TEMP_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    saved = []
    for file in files:
        safe_name = fs_router.sanitize_filename(file.filename or "upload", suffix="")
        target = os.path.abspath(os.path.join(upload_dir, f"{uuid.uuid4().hex}_{safe_name}"))
        with open(target, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        saved.append({"filename": file.filename, "path": target})
    db_manager.add_log("INFO", "Backend", "Upload_Files", f"用户 {user['username']} 上传 {len(saved)} 个文件")
    return {"files": saved}


@app.post("/api/process")
def start_process(payload: ProcessRequest, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    if not payload.sources:
        raise HTTPException(status_code=400, detail="sources 不能为空")
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {
            "id": job_id,
            "status": "queued",
            "progress": 0,
            "logs": [],
            "result": None,
            "error": None,
            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "user": user["username"],
            "payload": _job_payload_snapshot(payload),
        }

    def progress(message: str, value: int) -> None:
        with _jobs_lock:
            job = _jobs[job_id]
            job["status"] = "running"
            job["progress"] = max(0, min(100, int(value)))
            job["logs"].append({"message": message, "progress": job["progress"], "time": datetime.datetime.now().isoformat(timespec="seconds")})
            job["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")

    def runner() -> None:
        try:
            ProcessingOptions, ProcessingWorkflow = _load_processing_workflow()

            progress("处理任务开始执行", 1)

            options = ProcessingOptions(
                file_paths=payload.sources,
                whisper_lang=payload.whisper_lang,
                asr_engine=payload.asr_engine,
                provider=payload.provider,
                api_key=payload.api_key,
                api_base=payload.api_base,
                llm_model=payload.llm_model,
                vlm_model=payload.vlm_model,
                fact_model=payload.fact_model,
            )
            result = ProcessingWorkflow(options, progress).run()
            with _jobs_lock:
                _jobs[job_id]["status"] = "succeeded"
                _jobs[job_id]["progress"] = 100
                _jobs[job_id]["result"] = asdict(result)
                _jobs[job_id]["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            fs_router.scan_vault()
            db_manager.add_log("INFO", "Backend", "Process_Succeeded", f"job={job_id}")
        except Exception as exc:
            safe_error = Config.redact_secrets(str(exc))
            with _jobs_lock:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = safe_error
                _jobs[job_id]["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
            db_manager.add_log("ERROR", "Backend", "Process_Failed", f"job={job_id}, error={safe_error}")

    _process_executor.submit(runner)
    return {"job_id": job_id}


@app.get("/api/process/{job_id}")
def get_process_job(job_id: str, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/process/{job_id}/retry")
def retry_process_job(job_id: str, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    payload_data = job.get("payload")
    if not payload_data:
        raise HTTPException(status_code=400, detail="Job payload is not available")
    return start_process(ProcessRequest(**payload_data), user)


@app.get("/api/process")
def list_process_jobs(user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    with _jobs_lock:
        jobs = sorted(_jobs.values(), key=lambda item: item["created_at"], reverse=True)
    return {"jobs": jobs}


@app.get("/api/admin/logs")
def admin_logs(
    limit: int = 200,
    level: Optional[str] = None,
    keyword: Optional[str] = None,
    user: Dict[str, str] = Depends(_admin_user),
) -> Dict[str, Any]:
    logs = db_manager.get_logs(limit=limit, level_filter=level, keyword=keyword)
    return {"logs": logs, "count": len(logs)}


@app.get("/api/admin/logs/export", response_class=PlainTextResponse)
def export_logs(user: Dict[str, str] = Depends(_admin_user)) -> str:
    logs = db_manager.get_logs(limit=1000)
    lines = [
        f"Crucible System Audit Logs - Exported at {datetime.datetime.now()}",
        "=" * 80,
        "",
    ]
    for row in logs:
        lines.append(
            f"[{row['timestamp']}] [{row['level']}] [{row['module']}] "
            f"{row['action']} - {row['detail']} (Duration: {row['duration']}s)"
        )
    db_manager.add_log("INFO", "Backend", "Export_Logs", f"管理员 {user['username']} 导出日志")
    return "\n".join(lines) + "\n"


@app.get("/api/sources")
def list_sources(user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sources ORDER BY updated_at DESC, id DESC")
        rows = [dict(row) for row in cursor.fetchall()]
    return {"sources": rows}


@app.get("/api/sources/{source_id}")
def get_source(source_id: int, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    detail = source_index.get_source_detail(source_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Source not found")
    return detail


@app.get("/api/sources/{source_id}/segments")
def list_source_segments(source_id: int, user: Dict[str, str] = Depends(_current_user)) -> Dict[str, Any]:
    return {"segments": source_index.get_segments(source_id)}


@app.get("/api/sources/{source_id}/keyframes/{filename}")
def get_source_keyframe(source_id: int, filename: str, user: Dict[str, str] = Depends(_current_user)) -> FileResponse:
    detail = source_index.get_source_detail(source_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Source not found")
    keyframe = next((item for item in detail["keyframes"] if item.get("filename") == filename), None)
    if not keyframe:
        raise HTTPException(status_code=404, detail="Keyframe not found")
    rel_path = keyframe.get("attachment_rel_path") or keyframe.get("rel_path")
    if not rel_path:
        raise HTTPException(status_code=404, detail="Keyframe path not found")
    file_path = _safe_vault_path(rel_path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Keyframe file not found")
    return FileResponse(file_path, media_type="image/jpeg")


@app.get("/api/sources/{source_id}/video")
def stream_source_video(source_id: int, request: Request, user: Dict[str, str] = Depends(_resolve_token)):
    """流式传输本地视频文件，支持 HTTP Range 请求以便浏览器原生 <video> 播放。
    鉴权同时接受 Authorization header 和 ?token= query param。
    """
    detail = source_index.get_source_detail(source_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Source not found")

    source = detail["source"]
    source_uri = source.get("source_uri", "")

    # 仅支持本地文件，URL 类型来源不在此处理
    if source_uri.startswith(("http://", "https://")):
        raise HTTPException(status_code=404, detail="URL sources cannot be streamed")

    if not os.path.exists(source_uri):
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    ext = os.path.splitext(source_uri)[1].lower()
    media_type_map = {
        ".mp4": "video/mp4",
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
    }
    media_type = media_type_map.get(ext)
    if not media_type:
        raise HTTPException(status_code=400, detail="Unsupported video format")

    file_size = os.path.getsize(source_uri)
    range_header = request.headers.get("range")
    chunk_size = 1024 * 1024  # 1 MB

    if range_header:
        try:
            range_val = range_header.strip().replace("bytes=", "")
            range_start, range_end = range_val.split("-")
            start = int(range_start)
            end = int(range_end) if range_end else min(start + chunk_size - 1, file_size - 1)
        except (ValueError, AttributeError):
            raise HTTPException(status_code=416, detail="Invalid Range header")

        if start >= file_size or end >= file_size:
            raise HTTPException(status_code=416, detail="Range out of bounds")

        content_length = end - start + 1

        def video_chunk_generator():
            with open(source_uri, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    data = f.read(min(chunk_size, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            video_chunk_generator(),
            status_code=206,
            media_type=media_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
            },
        )

    # 无 Range 请求：返回完整文件
    def full_generator():
        with open(source_uri, "rb") as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                yield data

    return StreamingResponse(
        full_generator(),
        status_code=200,
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        },
    )
