import os
import re
import json
import shutil
import logging
import datetime
import uuid
from typing import Dict, List, Optional, Tuple
from Crucible.config import Config

logger = logging.getLogger(__name__)

class FSRouter:
    ORGANIZATION_RULES_FILENAME = "_crucible_organization_rules.md"

    def __init__(self, vault_path: str = Config.OBSIDIAN_VAULT_PATH):
        self.vault_path = vault_path
        # 建立缓存，映射 "概念名" -> "文件绝对路径"
        self.concept_cache: Dict[str, str] = {}
        self.scan_vault()

    def scan_vault(self):
        """扫描本地 Obsidian 目录，解析所有 .md 文件名及 Frontmatter 中的别名"""
        logger.info(f"开始扫描 Obsidian 知识库: {self.vault_path}")
        self.concept_cache.clear()
        
        if not os.path.exists(self.vault_path):
            os.makedirs(self.vault_path, exist_ok=True)
            return

        # 遍历目录
        for root, dirs, files in os.walk(self.vault_path):
            for file in files:
                if file.endswith('.md'):
                    file_path = os.path.join(root, file)
                    # 1. 以文件名（不含扩展名）作为默认概念名
                    concept_name = os.path.splitext(file)[0]
                    self.concept_cache[concept_name.lower()] = file_path
                    
                    # 2. 读取文件头部 YAML Frontmatter 提取 alias/别名
                    aliases = self._parse_frontmatter_aliases(file_path)
                    for alias in aliases:
                        self.concept_cache[alias.lower()] = file_path

        logger.info(f"知识库扫描完成，索引了 {len(self.concept_cache)} 个概念路径。")

    def _safe_join_vault(self, relative_path: str) -> str:
        """把相对路径解析到 vault 内，防止路径穿越。"""
        cleaned = (relative_path or "").strip().replace("\\", os.sep).replace("/", os.sep)
        cleaned = cleaned.lstrip("\\/")
        abs_path = os.path.abspath(os.path.join(self.vault_path, cleaned))
        vault_root = os.path.abspath(self.vault_path)
        if os.path.commonpath([vault_root, abs_path]) != vault_root:
            raise ValueError(f"目标路径越过知识库根目录: {relative_path}")
        return abs_path

    def sanitize_filename(self, name: str, suffix: str = ".md") -> str:
        """生成适合 Windows/Obsidian 的文件名。"""
        safe_name = re.sub(r'[\\/*?:"<>|]', '_', (name or "Untitled").strip()).strip(". ")
        if not safe_name:
            safe_name = "Untitled"
        if suffix and not safe_name.lower().endswith(suffix.lower()):
            safe_name += suffix
        return safe_name

    def resolve_note_path(self, requested_path: str, fallback_concept: str) -> str:
        """解析 LLM 或用户给出的目标笔记路径，空值则按概念名写入根目录。"""
        if requested_path:
            requested_path = requested_path.strip()
            if requested_path.lower().endswith(".md"):
                target_path = self._safe_join_vault(requested_path)
            else:
                target_path = self._safe_join_vault(os.path.join(requested_path, self.sanitize_filename(fallback_concept)))
            return target_path
        return os.path.join(self.vault_path, self.sanitize_filename(fallback_concept))

    def get_relative_path(self, file_path: str) -> str:
        """返回相对 vault 的路径，方便给 LLM 和 UI 展示。"""
        return os.path.relpath(file_path, self.vault_path).replace("\\", "/")

    def get_vault_structure_summary(self, max_items: int = 120) -> str:
        """生成轻量目录树摘要，供 LLM 判断笔记应放在哪。"""
        if not os.path.exists(self.vault_path):
            return "(vault is empty)"

        lines = []
        count = 0
        for root, dirs, files in os.walk(self.vault_path):
            dirs[:] = sorted([d for d in dirs if not d.startswith(".")])
            md_files = sorted([f for f in files if f.endswith(".md")])
            depth = max(0, len(os.path.relpath(root, self.vault_path).split(os.sep)) - 1)
            if root == self.vault_path:
                lines.append("/")
            else:
                lines.append(f"{'  ' * depth}- {os.path.basename(root)}/")
            count += 1
            for file_name in md_files:
                if file_name == self.ORGANIZATION_RULES_FILENAME:
                    continue
                lines.append(f"{'  ' * (depth + 1)}- {file_name}")
                count += 1
                if count >= max_items:
                    lines.append("  ...")
                    return "\n".join(lines)
        return "\n".join(lines) if lines else "(vault is empty)"

    def get_organization_rules_path(self) -> str:
        return os.path.join(self.vault_path, self.ORGANIZATION_RULES_FILENAME)

    def ensure_organization_rules(self) -> str:
        """创建并返回知识库整理规则文件。"""
        path = self.get_organization_rules_path()
        if not os.path.exists(path):
            os.makedirs(self.vault_path, exist_ok=True)
            default_rules = """# Crucible Organization Rules

## Folder Strategy
- `Sources/` stores source-oriented notes for imported videos, audio, PDFs, and web links.
- `Concepts/` stores atomic concept notes.
- `People/` stores people and organization notes.
- `Projects/` stores project-specific working notes.
- `Media/` stores notes that are tightly coupled to video scenes, timestamps, or visual analysis.

## Naming
- Use concise Chinese or English concept names.
- Keep Markdown files portable and Obsidian-compatible.
- Prefer stable topic folders over one-off deep nesting.

## LLM Filing Rules
- If a note is about a reusable idea, place it under `Concepts/`.
- If a note mostly summarizes a specific video or document, place it under `Sources/`.
- Preserve user-written notes and frontmatter.
- Never move or delete files unless the user explicitly requests reorganization.
"""
            with open(path, "w", encoding="utf-8") as f:
                f.write(default_rules)
        return path

    def read_organization_rules(self) -> str:
        path = self.ensure_organization_rules()
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _parse_frontmatter_aliases(self, file_path: str) -> List[str]:
        """解析 markdown 头部 frontmatter 中的别名或标签"""
        aliases = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 匹配 YAML 格式: 开头 --- 到第二个 ---
            match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
            if match:
                yaml_text = match.group(1)
                # 模糊提取 aliases 行
                alias_match = re.search(r'aliases:\s*\[?(.*?)\]?$', yaml_text, re.MULTILINE | re.IGNORECASE)
                if alias_match:
                    items = alias_match.group(1).split(',')
                    for item in items:
                        cleaned = item.strip().strip('"').strip("'")
                        if cleaned:
                            aliases.append(cleaned)
        except Exception as e:
            logger.warning(f"读取 Frontmatter 失败: {file_path}, {e}")
        return aliases

    def locate_concept_file(self, concept: str) -> Optional[str]:
        """
        查找并定位概念所对应的本地笔记路径。如果存在，返回绝对路径，否则返回 None。
        
        Args:
            concept: 概念名称 (如 'Transformer')
        """
        # 先利用缓存快速检索 (不区分大小写)
        key = concept.strip().lower()
        if key in self.concept_cache:
            path = self.concept_cache[key]
            if os.path.exists(path):
                return path
            else:
                # 缓存失效，重新扫描
                self.scan_vault()
                return self.concept_cache.get(key)
        
        # 缓存中未找到，重新扫描一次以防有新手动创建的文件
        self.scan_vault()
        return self.concept_cache.get(key)

    def get_concept_write_path(self, concept: str) -> str:
        """
        根据概念名称获取应该写入的文件路径。
        如果已存在则返回原路径；如果不存在，则在 vault 根目录下返回 `[概念名].md`
        """
        existing_path = self.locate_concept_file(concept)
        if existing_path:
            return existing_path
        
        # 安全化文件名，移除非法字符
        return os.path.join(self.vault_path, self.sanitize_filename(concept))

    def create_folder(self, parent_path: str, folder_name: str) -> str:
        safe_name = self.sanitize_filename(folder_name, suffix="")
        base = parent_path if parent_path and os.path.isdir(parent_path) else self.vault_path
        target = self._safe_join_vault(os.path.join(self.get_relative_path(base), safe_name))
        os.makedirs(target, exist_ok=True)
        return target

    def create_note(self, parent_path: str, note_name: str, content: str = "") -> str:
        safe_name = self.sanitize_filename(note_name)
        base = parent_path if parent_path and os.path.isdir(parent_path) else self.vault_path
        target = self._safe_join_vault(os.path.join(self.get_relative_path(base), safe_name))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if not os.path.exists(target):
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
        return target

    def rename_path(self, path: str, new_name: str) -> str:
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"路径不存在: {path}")
        suffix = "" if os.path.isdir(path) else os.path.splitext(path)[1]
        safe_name = self.sanitize_filename(new_name, suffix=suffix)
        target = self._safe_join_vault(os.path.join(self.get_relative_path(os.path.dirname(path)), safe_name))
        os.replace(path, target)
        self.scan_vault()
        return target

    def move_path(self, path: str, target_dir: str) -> str:
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"路径不存在: {path}")
        if not target_dir or not os.path.isdir(target_dir):
            raise NotADirectoryError(f"目标目录不存在: {target_dir}")
        target = self._safe_join_vault(os.path.join(self.get_relative_path(target_dir), os.path.basename(path)))
        os.replace(path, target)
        self.scan_vault()
        return target

    def trash_path(self, path: str, confirm_name: str) -> Dict:
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"路径不存在: {path}")
        vault_root = os.path.abspath(self.vault_path)
        abs_path = os.path.abspath(path)
        if os.path.commonpath([vault_root, abs_path]) != vault_root:
            raise ValueError("只能删除 vault 内的文件或目录")
        basename = os.path.basename(abs_path)
        if confirm_name != basename:
            raise ValueError("确认名称不匹配")

        trash_id = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        trash_dir = os.path.join(Config.TRASH_DIR, trash_id)
        os.makedirs(trash_dir, exist_ok=True)
        stored_path = os.path.join(trash_dir, basename)
        original_rel_path = self.get_relative_path(abs_path)
        manifest = {
            "id": trash_id,
            "name": basename,
            "type": "directory" if os.path.isdir(abs_path) else "file",
            "original_path": original_rel_path,
            "stored_path": stored_path,
            "trashed_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        shutil.move(abs_path, stored_path)
        with open(os.path.join(trash_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        self.scan_vault()
        return manifest

    def list_trash(self) -> List[Dict]:
        if not os.path.exists(Config.TRASH_DIR):
            return []
        items = []
        for entry in os.scandir(Config.TRASH_DIR):
            if not entry.is_dir():
                continue
            manifest_path = os.path.join(entry.path, "manifest.json")
            if not os.path.exists(manifest_path):
                continue
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                items.append(manifest)
            except Exception as e:
                logger.warning(f"读取回收站 manifest 失败: {manifest_path}, {e}")
        items.sort(key=lambda item: item.get("trashed_at", ""), reverse=True)
        return items

    def restore_trash(self, trash_id: str) -> Dict:
        trash_id = (trash_id or "").strip()
        if not re.match(r'^[0-9A-Za-z_-]+$', trash_id):
            raise ValueError("非法回收站 ID")
        trash_dir = os.path.abspath(os.path.join(Config.TRASH_DIR, trash_id))
        trash_root = os.path.abspath(Config.TRASH_DIR)
        if os.path.commonpath([trash_root, trash_dir]) != trash_root:
            raise ValueError("非法回收站路径")
        manifest_path = os.path.join(trash_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            raise FileNotFoundError("回收站项目不存在")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        stored_path = manifest.get("stored_path") or os.path.join(trash_dir, manifest["name"])
        if not os.path.exists(stored_path):
            raise FileNotFoundError("回收站文件不存在")

        target = self._safe_join_vault(manifest.get("original_path", manifest["name"]))
        if os.path.exists(target):
            base, ext = os.path.splitext(target)
            suffix = datetime.datetime.now().strftime("_restored_%Y%m%d_%H%M%S")
            target = base + suffix + ext
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.move(stored_path, target)
        try:
            os.remove(manifest_path)
            os.rmdir(trash_dir)
        except OSError:
            pass
        self.scan_vault()
        manifest["restored_path"] = self.get_relative_path(target)
        return manifest

    def get_vault_tree_nodes(self) -> List[Dict]:
        """
        以树形结构数据列出所有的 markdown 文件（用于 PyQt6 界面展示）
        """
        nodes = []
        if not os.path.exists(self.vault_path):
            return nodes

        def recurse_dir(dir_path: str) -> List[Dict]:
            items = []
            try:
                for entry in os.scandir(dir_path):
                    if entry.is_dir():
                        children = recurse_dir(entry.path)
                        items.append({
                            "name": entry.name,
                            "type": "directory",
                            "path": entry.path,
                            "children": children
                        })
                    elif entry.is_file() and entry.name.endswith('.md'):
                        items.append({
                            "name": entry.name,
                            "type": "file",
                            "path": entry.path
                        })
            except Exception as e:
                logger.error(f"遍历目录 {dir_path} 出错: {e}")
            # 目录排前面，文件排后面，按名称排序
            items.sort(key=lambda x: (0 if x['type'] == 'directory' else 1, x['name'].lower()))
            return items

        return recurse_dir(self.vault_path)

# 实例化单例
fs_router = FSRouter()
