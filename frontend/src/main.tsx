import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import {
  AudioLines,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Clock3,
  FilePlus2,
  FileText,
  Folder,
  FolderOpen,
  GitFork,
  Hash,
  Image as ImageIcon,
  Link2,
  ListChecks,
  Loader2,
  LogOut,
  MoreHorizontal,
  MoveRight,
  PanelRight,
  Play,
  RotateCcw,
  Save,
  Search,
  Settings2,
  ShieldAlert,
  Sparkles,
  Trash2,
  UploadCloud,
  UserPlus,
  Video
} from "lucide-react";
import "./styles.css";
import type {
  ConfigTestResult,
  GraphData,
  NotePayload,
  ProcessJob,
  ProviderInfo,
  SearchResult,
  SegmentRecord,
  SourceDetail,
  SourceRecord,
  TrashItem,
  User,
  VaultNode
} from "./types";
import {
  displayMeta,
  displayTags,
  findFirstNote,
  flattenDirectories,
  flattenNotes,
  formatDuration,
  normalizeUrlInput,
  parentPathOf,
  previewCacheKey,
  sourceKind
} from "./utils";

const TOKEN_KEY = "crucible_web_token";
const DEFAULT_TEMPLATES = ["空白"];
const DEFAULT_ASR_OPTIONS = {
  whisper_lang: "auto",
  asr_engine: "dashscope"
};

const navItems = [
  { label: "Vault", icon: FolderOpen },
  { label: "来源", icon: Video },
  { label: "检索", icon: Search },
  { label: "图谱", icon: GitFork },
  { label: "设置", icon: Settings2 }
];

function SourceIcon({ kind }: { kind: string }) {
  if (kind === "audio") return <AudioLines size={16} />;
  if (kind === "document") return <FileText size={16} />;
  return <Video size={16} />;
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || "");
  const [user, setUser] = useState<User | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [activeNav, setActiveNav] = useState("Vault");

  const [tree, setTree] = useState<VaultNode[]>([]);
  const [templates, setTemplates] = useState(DEFAULT_TEMPLATES);
  const [newItemParent, setNewItemParent] = useState("");
  const [newNoteTemplate, setNewNoteTemplate] = useState(DEFAULT_TEMPLATES[0]);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [activeSource, setActiveSource] = useState<SourceRecord | null>(null);
  const [sourceDetail, setSourceDetail] = useState<SourceDetail | null>(null);
  const [sourceFilter, setSourceFilter] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [urlStatus, setUrlStatus] = useState("");
  const [keyframeUrls, setKeyframeUrls] = useState<Record<string, string>>({});
  const [segments, setSegments] = useState<SegmentRecord[]>([]);
  const [note, setNote] = useState<NotePayload | null>(null);
  const [activeAnchor, setActiveAnchor] = useState("");
  const [editorContent, setEditorContent] = useState("");
  const [editorMode, setEditorMode] = useState<"edit" | "preview">("edit");
  const [previewHtml, setPreviewHtml] = useState("");
  const [previewPending, setPreviewPending] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [] });
  const [graphSummary, setGraphSummary] = useState("");
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [jobs, setJobs] = useState<ProcessJob[]>([]);
  const [activeJobId, setActiveJobId] = useState("");
  const [logs, setLogs] = useState<Array<Record<string, unknown>>>([]);
  const [trashItems, setTrashItems] = useState<TrashItem[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [settings, setSettings] = useState({
    provider: "dashscope",
    api_base: "",
    llm_model: "",
    vlm_model: "",
    fact_model: "",
    whisper_model: "base",
    whisper_device: "cpu",
    api_key: ""
  });
  const [settingsStatus, setSettingsStatus] = useState<ConfigTestResult | null>(null);
  const [asrOptions, setAsrOptions] = useState(DEFAULT_ASR_OPTIONS);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const editorRef = useRef<HTMLTextAreaElement | null>(null);
  const previewRef = useRef<HTMLDivElement | null>(null);
  const previousJobStatusesRef = useRef<Record<string, ProcessJob["status"]>>({});
  const previewCacheRef = useRef<Map<string, string>>(new Map());
  const previewAbortRef = useRef<AbortController | null>(null);
  const previewRequestKeyRef = useRef("");

  const rememberPreview = useCallback((path: string, content: string, html: string) => {
    const cacheKey = previewCacheKey(path, content);
    previewCacheRef.current.set(cacheKey, html);
    while (previewCacheRef.current.size > 24) {
      const oldest = previewCacheRef.current.keys().next().value;
      if (oldest === undefined) break;
      previewCacheRef.current.delete(oldest);
    }
  }, []);

  const api = useCallback(async <T,>(path: string, options: RequestInit = {}): Promise<T> => {
    const headers = new Headers(options.headers);
    if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(path, { ...options, headers });
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const data = await response.json();
        detail = data.detail || detail;
      } catch {
        detail = await response.text();
      }
      throw new Error(detail);
    }
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) return response.json();
    return response.text() as T;
  }, [token]);

  const apiBlob = useCallback(async (path: string): Promise<Blob> => {
    const headers = new Headers();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(path, { headers });
    if (!response.ok) {
      throw new Error(response.statusText);
    }
    return response.blob();
  }, [token]);

  const showError = useCallback((error: unknown) => {
    setMessage(error instanceof Error ? error.message : String(error));
  }, []);

  const openNote = useCallback(async (path: string, anchor = "") => {
    try {
      const suffix = anchor ? `?anchor=${encodeURIComponent(anchor)}` : "";
      const loaded = await api<NotePayload>(`/api/notes/${encodeURIComponent(path).replace(/%2F/g, "/")}${suffix}`);
      setNote(loaded);
      setEditorContent(loaded.content);
      setPreviewHtml(loaded.preview_html);
      rememberPreview(loaded.path, loaded.content, loaded.preview_html);
      setActiveAnchor(anchor);
      setNewItemParent(parentPathOf(loaded.path));
      if (anchor) setEditorMode("preview");
      setDirty(false);
      setActiveNav("Vault");
    } catch (error) {
      showError(error);
    }
  }, [api, rememberPreview, showError]);

  const refreshVault = useCallback(async () => {
    const data = await api<{ nodes: VaultNode[] }>("/api/vault/tree");
    setTree(data.nodes);
    const firstNote = findFirstNote(data.nodes);
    if (!note && firstNote) await openNote(firstNote.path);
  }, [api, note, openNote]);

  const refreshSources = useCallback(async () => {
    const data = await api<{ sources: SourceRecord[] }>("/api/sources");
    setSources(data.sources);
    setActiveSource((current) => {
      if (!data.sources.length) return null;
      if (!current) return data.sources[0];
      return data.sources.find((source) => source.id === current.id) || data.sources[0];
    });
  }, [api]);

  const refreshGraph = useCallback(async () => {
    const data = await api<{ graph: GraphData; summary: string }>("/api/graph");
    setGraph(data.graph);
    setGraphSummary(data.summary);
  }, [api]);

  const refreshLogs = useCallback(async () => {
    if (user?.role !== "admin") return;
    const data = await api<{ logs: Array<Record<string, unknown>> }>("/api/admin/logs?limit=80");
    setLogs(data.logs);
  }, [api, user?.role]);

  const refreshJobs = useCallback(async () => {
    const data = await api<{ jobs: ProcessJob[] }>("/api/process");
    setJobs(data.jobs);
  }, [api]);

  const refreshTemplates = useCallback(async () => {
    const data = await api<{ templates: string[] }>("/api/templates");
    const nextTemplates = data.templates.length ? data.templates : DEFAULT_TEMPLATES;
    setTemplates(nextTemplates);
    setNewNoteTemplate((current) => nextTemplates.includes(current) ? current : nextTemplates[0]);
  }, [api]);

  const refreshTrash = useCallback(async () => {
    const data = await api<{ items: TrashItem[] }>("/api/vault/trash");
    setTrashItems(data.items);
  }, [api]);

  const refreshKnowledgeState = useCallback(async () => {
    await Promise.all([refreshVault(), refreshSources(), refreshGraph(), refreshLogs(), refreshTrash()]);
  }, [refreshVault, refreshSources, refreshGraph, refreshLogs, refreshTrash]);

  const refreshAll = useCallback(async () => {
    try {
      setLoading(true);
      await Promise.all([refreshKnowledgeState(), refreshJobs(), refreshTemplates()]);
      setMessage("已同步后端状态");
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }, [refreshKnowledgeState, refreshJobs, refreshTemplates, showError]);

  const login = async (event?: React.FormEvent) => {
    event?.preventDefault();
    try {
      setLoading(true);
      const data = await api<{ token: string; user: User }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password })
      });
      localStorage.setItem(TOKEN_KEY, data.token);
      setToken(data.token);
      setUser(data.user);
      setMessage(`已登录：${data.user.username}`);
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  };

  const register = async (event?: React.FormEvent) => {
    event?.preventDefault();
    try {
      setLoading(true);
      const created = await api<User>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, password, role: "user" })
      });
      setAuthMode("login");
      setMessage(`已创建用户：${created.username}，请登录`);
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  };

  const clearSession = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUser(null);
    setNote(null);
    setActiveAnchor("");
    setPreviewHtml("");
    setEditorMode("edit");
    setTree([]);
    setSources([]);
    setActiveSource(null);
    setSourceDetail(null);
    setSourceFilter("");
    Object.values(keyframeUrls).forEach((url) => URL.revokeObjectURL(url));
    setKeyframeUrls({});
    setSegments([]);
    setGraph({ nodes: [], edges: [] });
    setGraphSummary("");
    setSearchResults([]);
    setJobs([]);
    setLogs([]);
    setTrashItems([]);
    setSettingsStatus(null);
    previewCacheRef.current.clear();
    previewAbortRef.current?.abort();
    previewAbortRef.current = null;
    previewRequestKeyRef.current = "";
  };

  const logout = async () => {
    try {
      if (token) {
        await api("/api/auth/logout", { method: "POST" });
      }
    } catch {
      // 后端会话已失效时仍要清理本地状态。
    } finally {
      clearSession();
    }
  };

  useEffect(() => {
    if (!token) return;
    api<User>("/api/auth/me")
      .then(setUser)
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setToken("");
      });
  }, [api, token]);

  useEffect(() => {
    if (user) refreshAll();
  }, [user]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    api<{ providers: ProviderInfo[]; current: typeof settings }>("/api/config/providers")
      .then((data) => {
        setProviders(data.providers);
        setSettings((current) => ({ ...current, ...data.current, api_key: "" }));
      })
      .catch(() => undefined);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!activeSource) {
      setSourceDetail(null);
      setSegments([]);
      return;
    }
    api<SourceDetail>(`/api/sources/${activeSource.id}`)
      .then((data) => {
        setSourceDetail(data);
        setSegments(data.segments);
      })
      .catch(() => {
        setSourceDetail(null);
        setSegments([]);
      });
  }, [activeSource, api]);

  useEffect(() => {
    const urls: Record<string, string> = {};
    let cancelled = false;

    async function loadKeyframes() {
      if (!activeSource || !sourceDetail?.keyframes.length) {
        setKeyframeUrls({});
        return;
      }
      await Promise.all(sourceDetail.keyframes.map(async (frame) => {
        try {
          const blob = await apiBlob(`/api/sources/${activeSource.id}/keyframes/${encodeURIComponent(frame.filename)}`);
          urls[frame.filename] = URL.createObjectURL(blob);
        } catch {
          // 单张关键帧丢失时保留其他图片。
        }
      }));
      if (!cancelled) setKeyframeUrls(urls);
    }

    loadKeyframes();
    return () => {
      cancelled = true;
      Object.values(urls).forEach((url) => URL.revokeObjectURL(url));
    };
  }, [activeSource, apiBlob, sourceDetail?.keyframes]);

  useEffect(() => {
    if (!jobs.some((job) => job.status === "running" || job.status === "queued")) return;
    const id = window.setInterval(refreshJobs, 1800);
    return () => window.clearInterval(id);
  }, [jobs, refreshJobs]);

  useEffect(() => {
    const previous = previousJobStatusesRef.current;
    const completedJob = jobs.find((job) => {
      const oldStatus = previous[job.id];
      return (oldStatus === "queued" || oldStatus === "running") && (job.status === "succeeded" || job.status === "failed");
    });

    previousJobStatusesRef.current = Object.fromEntries(jobs.map((job) => [job.id, job.status]));
    if (!completedJob) return;

    if (completedJob.status === "succeeded") {
      refreshKnowledgeState()
        .then(() => setMessage("处理任务已完成，知识库状态已刷新"))
        .catch(showError);
    } else {
      refreshLogs().catch(() => undefined);
      setMessage(`处理任务失败：${completedJob.error || "请查看任务日志"}`);
    }
  }, [jobs, refreshKnowledgeState, refreshLogs, showError]);

  useEffect(() => {
    if (!user || !note) {
      setPreviewHtml("");
      previewAbortRef.current?.abort();
      previewAbortRef.current = null;
      previewRequestKeyRef.current = "";
      return;
    }

    const cacheKey = previewCacheKey(note.path, editorContent);
    const cachedPreview = previewCacheRef.current.get(cacheKey);
    if (cachedPreview !== undefined) {
      setPreviewHtml(cachedPreview);
      setPreviewPending(false);
      return;
    }
    if (previewRequestKeyRef.current === cacheKey) return;

    let cancelled = false;
    const id = window.setTimeout(() => {
      previewAbortRef.current?.abort();
      const controller = new AbortController();
      previewAbortRef.current = controller;
      previewRequestKeyRef.current = cacheKey;
      setPreviewPending(true);
      api<{ preview_html: string }>("/api/notes/preview", {
        method: "POST",
        body: JSON.stringify({ content: editorContent }),
        signal: controller.signal
      })
        .then((data) => {
          if (cancelled) return;
          previewCacheRef.current.set(cacheKey, data.preview_html);
          while (previewCacheRef.current.size > 24) {
            const oldest = previewCacheRef.current.keys().next().value;
            if (oldest === undefined) break;
            previewCacheRef.current.delete(oldest);
          }
          setPreviewHtml(data.preview_html);
        })
        .catch((error) => {
          if (error instanceof DOMException && error.name === "AbortError") return;
        })
        .finally(() => {
          if (previewAbortRef.current === controller) {
            previewAbortRef.current = null;
          }
          if (previewRequestKeyRef.current === cacheKey) {
            previewRequestKeyRef.current = "";
          }
          if (!cancelled) setPreviewPending(false);
        });
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(id);
      previewAbortRef.current?.abort();
    };
  }, [api, editorContent, note?.path, user]);

  useEffect(() => {
    if (!activeAnchor || !note) return;

    const id = window.setTimeout(() => {
      if (editorMode === "edit") {
        const editor = editorRef.current;
        const index = editorContent.indexOf(activeAnchor);
        if (!editor || index < 0) return;
        editor.focus();
        editor.setSelectionRange(index, index + activeAnchor.length);
        return;
      }

      const preview = previewRef.current;
      if (!preview) return;
      const candidates = Array.from(preview.querySelectorAll<HTMLElement>("h1,h2,h3,h4,h5,h6,p,li,time"));
      const matched = candidates.find((item) => (item.textContent || "").includes(activeAnchor));
      if (!matched) return;
      preview.querySelectorAll(".anchor-hit").forEach((item) => item.classList.remove("anchor-hit"));
      matched.classList.add("anchor-hit");
      matched.scrollIntoView({ block: "center" });
    }, 80);

    return () => window.clearTimeout(id);
  }, [activeAnchor, editorContent, editorMode, note, previewHtml]);

  const recentNotes = useMemo(() => flattenNotes(tree).slice(0, 8), [tree]);
  const directoryOptions = useMemo(() => [{ path: "", label: "data/vault" }, ...flattenDirectories(tree)], [tree]);
  const activeJob = jobs.find((job) => job.id === activeJobId) || jobs[0];
  const currentSourceKind = sourceKind(activeSource?.source_type);
  const filteredSegments = useMemo(() => {
    const needle = sourceFilter.trim().toLowerCase();
    if (!needle) return segments;
    return segments.filter((segment) =>
      segment.text.toLowerCase().includes(needle) ||
      segment.timestamp_label.includes(needle)
    );
  }, [segments, sourceFilter]);
  const activeSegments = filteredSegments;
  const sourceMetadata = sourceDetail?.metadata || {};
  const processPayload = useCallback((sourcesToProcess: string[]) => ({
    sources: sourcesToProcess,
    whisper_lang: asrOptions.whisper_lang,
    asr_engine: asrOptions.asr_engine,
    provider: settings.provider,
    api_base: settings.api_base,
    llm_model: settings.llm_model,
    vlm_model: settings.vlm_model,
    fact_model: settings.fact_model,
    api_key: settings.api_key || undefined
  }), [asrOptions, settings]);

  const trackStartedJob = useCallback((jobId: string) => {
    previousJobStatusesRef.current = {
      ...previousJobStatusesRef.current,
      [jobId]: "queued"
    };
    setActiveJobId(jobId);
    setActiveNav("来源");
  }, []);

  const saveNote = async () => {
    if (!note) return;
    try {
      const saved = await api<NotePayload>(`/api/notes/${encodeURIComponent(note.path).replace(/%2F/g, "/")}`, {
        method: "PUT",
        body: JSON.stringify({ content: editorContent })
      });
      setNote(saved);
      setEditorContent(saved.content);
      setPreviewHtml(saved.preview_html);
      rememberPreview(saved.path, saved.content, saved.preview_html);
      setDirty(false);
      setMessage("笔记已保存");
      await Promise.all([refreshVault(), refreshGraph()]);
    } catch (error) {
      showError(error);
    }
  };

  const createNote = async () => {
    const name = window.prompt("新建笔记名称", "Untitled.md");
    if (!name) return;
    try {
      const created = await api<NotePayload>("/api/vault/notes", {
        method: "POST",
        body: JSON.stringify({ name, parent_path: newItemParent, template: newNoteTemplate })
      });
      setNote(created);
      setEditorContent(created.content);
      setPreviewHtml(created.preview_html);
      rememberPreview(created.path, created.content, created.preview_html);
      setEditorMode("edit");
      setActiveAnchor("");
      setNewItemParent(parentPathOf(created.path));
      setDirty(false);
      await refreshVault();
    } catch (error) {
      showError(error);
    }
  };

  const createFolder = async () => {
    const name = window.prompt("新建文件夹名称", "Concepts");
    if (!name) return;
    try {
      await api("/api/vault/folders", {
        method: "POST",
        body: JSON.stringify({ name, parent_path: newItemParent })
      });
      await refreshVault();
      setMessage("文件夹已创建");
    } catch (error) {
      showError(error);
    }
  };

  const renameCurrentNote = async () => {
    if (!note) return;
    const nextName = window.prompt("新名称", note.name);
    if (!nextName || nextName === note.name) return;
    try {
      const renamed = await api<{ path: string }>("/api/vault/rename", {
        method: "POST",
        body: JSON.stringify({ path: note.path, new_name: nextName })
      });
      await refreshVault();
      await openNote(renamed.path);
      setMessage("已重命名");
    } catch (error) {
      showError(error);
    }
  };

  const openOrganizationRules = async () => {
    try {
      const rules = await api<NotePayload>("/api/vault/organization-rules");
      setNote(rules);
      setEditorContent(rules.content);
      setPreviewHtml(rules.preview_html);
      rememberPreview(rules.path, rules.content, rules.preview_html);
      setEditorMode("edit");
      setActiveAnchor("");
      setNewItemParent(parentPathOf(rules.path));
      setDirty(false);
    } catch (error) {
      showError(error);
    }
  };

  const openWikiTarget = async (target: string) => {
    try {
      const loaded = await api<NotePayload>("/api/notes/open-wiki-target", {
        method: "POST",
        body: JSON.stringify({ target })
      });
      setNote(loaded);
      setEditorContent(loaded.content);
      setPreviewHtml(loaded.preview_html);
      rememberPreview(loaded.path, loaded.content, loaded.preview_html);
      setActiveAnchor(loaded.anchor || "");
      setNewItemParent(parentPathOf(loaded.path));
      if (loaded.anchor) setEditorMode("preview");
      setDirty(false);
      setActiveNav("Vault");
    } catch (error) {
      showError(error);
    }
  };

  const handlePreviewClick = async (event: React.MouseEvent<HTMLDivElement>) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const link = target.closest<HTMLAnchorElement>("a");
    if (!link) return;

    const href = link.getAttribute("href") || "";
    if (href.startsWith("crucible://note/")) {
      event.preventDefault();
      await openWikiTarget(decodeURIComponent(href.replace("crucible://note/", "")));
      return;
    }

    if (/^https?:\/\//i.test(href)) {
      event.preventDefault();
      window.open(href, "_blank", "noopener,noreferrer");
    }
  };

  const runSearch = async () => {
    if (!query.trim()) return;
    try {
      const data = await api<{ results: SearchResult[] }>("/api/search", {
        method: "POST",
        body: JSON.stringify({ keyword: query.trim(), limit: 100 })
      });
      setSearchResults(data.results);
      setActiveNav("检索");
    } catch (error) {
      showError(error);
    }
  };

  const openSearchResult = async (result: SearchResult) => {
    await openNote(result.source_note_path, result.timestamp_label);
  };

  const uploadAndProcess = async (files: FileList | null) => {
    if (!files?.length) return;
    try {
      setLoading(true);
      const form = new FormData();
      Array.from(files).forEach((file) => form.append("files", file));
      const uploaded = await api<{ files: Array<{ path: string }> }>("/api/uploads", {
        method: "POST",
        body: form
      });
      const process = await api<{ job_id: string }>("/api/process", {
        method: "POST",
        body: JSON.stringify(processPayload(uploaded.files.map((file) => file.path)))
      });
      trackStartedJob(process.job_id);
      setMessage("处理任务已启动");
      await refreshJobs();
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const processCurrentSource = async () => {
    if (!activeSource) return;
    try {
      const data = await api<{ job_id: string }>("/api/process", {
        method: "POST",
        body: JSON.stringify(processPayload([activeSource.source_uri]))
      });
      trackStartedJob(data.job_id);
      setMessage("当前来源已加入处理任务");
      await refreshJobs();
    } catch (error) {
      showError(error);
    }
  };

  const addUrlAndProcess = async () => {
    const url = normalizeUrlInput(urlInput);
    if (!url || !/^https?:\/\/\S+$/i.test(url)) {
      const feedback = url ? "请输入合法的 HTTP/HTTPS 链接" : "请输入要添加的视频或网页链接";
      setUrlStatus(feedback);
      setMessage(feedback);
      return;
    }
    try {
      setLoading(true);
      setUrlStatus(`正在创建处理任务：${url}`);
      setMessage(`正在添加链接：${url}`);
      const data = await api<{ job_id: string }>("/api/process", {
        method: "POST",
        body: JSON.stringify(processPayload([url]))
      });
      trackStartedJob(data.job_id);
      setUrlInput("");
      setUrlStatus("已加入处理队列，可在右侧任务面板查看进度");
      setActiveNav("来源");
      setMessage(`URL 来源处理任务已启动：${url}`);
      await refreshJobs();
    } catch (error) {
      setUrlStatus("添加链接失败，请查看错误提示");
      showError(error);
    } finally {
      setLoading(false);
    }
  };

  const exportLogs = async () => {
    try {
      const text = await api<string>("/api/admin/logs/export");
      const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "crucible_audit_logs.txt";
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      showError(error);
    }
  };

  const saveSettings = async () => {
    try {
      await api("/api/config/runtime", {
        method: "POST",
        body: JSON.stringify(settings)
      });
      setMessage("模型配置已保存");
    } catch (error) {
      showError(error);
    }
  };

  const testSettings = async () => {
    try {
      const result = await api<ConfigTestResult>("/api/config/test", {
        method: "POST",
        body: JSON.stringify(settings)
      });
      setSettingsStatus(result);
      setMessage(result.message);
    } catch (error) {
      showError(error);
    }
  };

  const retryJob = async (jobId: string) => {
    try {
      const data = await api<{ job_id: string }>(`/api/process/${jobId}/retry`, { method: "POST" });
      trackStartedJob(data.job_id);
      await refreshJobs();
      setMessage("失败任务已重新加入队列");
    } catch (error) {
      showError(error);
    }
  };

  const moveVaultPath = async (path: string) => {
    const targetDir = window.prompt("移动到目录路径，例如 Concepts 或 Sources", newItemParent || "");
    if (targetDir === null) return;
    try {
      const moved = await api<{ path: string }>("/api/vault/move", {
        method: "POST",
        body: JSON.stringify({ path, target_dir: targetDir })
      });
      await refreshKnowledgeState();
      if (note?.path === path) await openNote(moved.path);
      setMessage("已移动");
    } catch (error) {
      showError(error);
    }
  };

  const deleteVaultPath = async (path: string, name: string) => {
    const confirmName = window.prompt(`输入名称以移入回收站：${name}`);
    if (!confirmName) return;
    try {
      await api("/api/vault/delete", {
        method: "POST",
        body: JSON.stringify({ path, confirm_name: confirmName })
      });
      if (note?.path === path) {
        setNote(null);
        setEditorContent("");
        setPreviewHtml("");
        setDirty(false);
      }
      await refreshKnowledgeState();
      setMessage("已移入回收站");
    } catch (error) {
      showError(error);
    }
  };

  const restoreTrashItem = async (trashId: string) => {
    try {
      const restored = await api<{ restored: { restored_path: string } }>("/api/vault/restore", {
        method: "POST",
        body: JSON.stringify({ trash_id: trashId })
      });
      await refreshKnowledgeState();
      if (restored.restored?.restored_path?.endsWith(".md")) {
        await openNote(restored.restored.restored_path);
      }
      setMessage("已从回收站恢复");
    } catch (error) {
      showError(error);
    }
  };

  const selectProvider = (providerKey: string) => {
    const provider = providers.find((item) => item.key === providerKey);
    setSettingsStatus(null);
    setSettings((current) => ({
      ...current,
      provider: providerKey,
      api_base: provider?.preset.api_base || current.api_base,
      llm_model: provider?.preset.model || current.llm_model,
      vlm_model: provider?.preset.vlm_model || provider?.preset.model || current.vlm_model,
      fact_model: provider?.preset.model || current.fact_model
    }));
    if (providerKey === "ollama" || providerKey === "lmstudio") {
      setAsrOptions((current) => ({ ...current, asr_engine: "local" }));
    }
  };

  if (!user) {
    return (
      <main className="login-shell">
        <form className="login-card sketch-card" onSubmit={authMode === "login" ? login : register}>
          <div className="brand-mark">
            <span className="brand-sigil">C</span>
            <div>
              <p className="eyebrow">Crucible Web</p>
              <h1>{authMode === "login" ? "登录知识库" : "注册账户"}</h1>
            </div>
          </div>
          <label>
            <span>用户名</span>
            <input value={username} onChange={(event) => setUsername(event.target.value)} />
          </label>
          <label>
            <span>密码</span>
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          <button className="marker-button primary" type="submit" disabled={loading}>
            {loading ? <Loader2 size={17} className="spin" /> : authMode === "login" ? <Play size={17} /> : <UserPlus size={17} />}
            {authMode === "login" ? "登录" : "注册"}
          </button>
          <button
            className="marker-button"
            type="button"
            onClick={() => {
              setAuthMode(authMode === "login" ? "register" : "login");
              setMessage("");
            }}
          >
            {authMode === "login" ? "创建新账户" : "返回登录"}
          </button>
          {message && <p className="message-line">{message}</p>}
        </form>
      </main>
    );
  }

  return (
    <main className="workspace-shell">
      <aside className="left-rail sketch-panel">
        <div className="brand-mark">
          <span className="brand-sigil">C</span>
          <div>
            <p className="eyebrow">Video-first KB</p>
            <h1>Crucible</h1>
          </div>
        </div>

        <nav className="bookmark-nav" aria-label="主导航">
          {navItems.map((item, index) => {
            const Icon = item.icon;
            return (
              <button
                className={`bookmark ${activeNav === item.label ? "active" : ""}`}
                key={item.label}
                onClick={() => setActiveNav(item.label)}
                style={{ "--tilt": `${index % 2 === 0 ? -0.9 : 1.1}deg` } as React.CSSProperties}
              >
                <Icon size={17} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <section className="vault-tree">
          <div className="panel-title">
            <span><Folder size={16} /> data/vault</span>
            <div className="panel-actions">
              <button aria-label="新建文件夹" onClick={createFolder}><Folder size={16} /></button>
              <button aria-label="新建笔记" onClick={createNote}><FilePlus2 size={16} /></button>
            </div>
          </div>
          <div className="vault-create-options">
            <select value={newItemParent} onChange={(event) => setNewItemParent(event.target.value)} aria-label="新建位置">
              {directoryOptions.map((item) => <option key={item.path || "root"} value={item.path}>{item.label}</option>)}
            </select>
            <select value={newNoteTemplate} onChange={(event) => setNewNoteTemplate(event.target.value)} aria-label="新建笔记模板">
              {templates.map((template) => <option key={template} value={template}>{template}</option>)}
            </select>
          </div>
          <Tree
            nodes={tree}
            activePath={note?.path || ""}
            onOpenNote={openNote}
            onMove={moveVaultPath}
            onDelete={deleteVaultPath}
          />
        </section>
      </aside>

      <section className="main-workspace">
        <header className="command-bar sketch-card">
          <label className="search-box">
            <Search size={18} />
            <input
              placeholder="搜索来源片段、来源名或关联概念..."
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") runSearch();
              }}
            />
          </label>
          <div className="command-actions">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              accept=".mp4,.mkv,.avi,.mov,.webm,.mp3,.wav,.m4a,.flac,.aac,.pdf,.txt,.md"
              onChange={(event) => uploadAndProcess(event.target.files)}
            />
            <button className="marker-button" onClick={() => fileInputRef.current?.click()}>
              <UploadCloud size={17} />
              导入来源
            </button>
            <label className="url-add-box">
              <Link2 size={16} />
              <input
                aria-label="添加来源链接"
                placeholder="粘贴视频或网页 URL..."
                value={urlInput}
                onChange={(event) => {
                  setUrlInput(event.target.value);
                  if (urlStatus) setUrlStatus("");
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") addUrlAndProcess();
                }}
              />
            </label>
            <button className="marker-button" onClick={addUrlAndProcess}>
              <Link2 size={17} />
              添加链接
            </button>
            <button className="marker-button primary" onClick={processCurrentSource} disabled={!activeSource}>
              <Sparkles size={17} />
              提炼当前来源
            </button>
          </div>
        </header>

        {urlStatus && <section className="url-feedback sketch-card">{urlStatus}</section>}

        <section className="work-grid">
          <article className="source-pane sketch-card">
            <div className="section-title">
              <div>
                <p className="eyebrow">Active source</p>
                <h2>{activeSource?.source_name || "暂无来源"}</h2>
              </div>
              <button className="icon-chip" aria-label="打开来源页" onClick={() => activeSource && openNote(activeSource.source_note_path)}>
                <Play size={18} />
              </button>
            </div>

            <div className="source-stage">
              <div className={`source-badge ${currentSourceKind}`}>
                <SourceIcon kind={currentSourceKind} />
                <span>{currentSourceKind}</span>
              </div>
              <div className="progress-block">
                <div className="progress-meta">
                  <strong>{activeSource ? "已入库" : "等待导入"}</strong>
                  <span>{activeSource ? "100%" : "0%"}</span>
                </div>
                <div className="pencil-progress">
                  <span style={{ width: activeSource ? "100%" : "0%" }} />
                </div>
                <p>{activeSource ? `${activeSource.source_note_path} · ${formatDuration(activeSource.duration)}` : "上传视频、音频或文档后会生成来源页。"}</p>
              </div>
            </div>

            {activeSource && (
              <div className="source-meta-grid">
                <span><strong>Hash</strong>{displayMeta(activeSource.source_hash)}</span>
                <span><strong>分辨率</strong>{displayMeta(sourceMetadata.resolution)}</span>
                <span><strong>FPS</strong>{displayMeta(sourceMetadata.fps)}</span>
                <span><strong>音轨</strong>{displayMeta(sourceMetadata.audio_streams)}</span>
                <span><strong>字幕</strong>{displayMeta(sourceMetadata.subtitle_streams)}</span>
                <span><strong>大小</strong>{sourceMetadata.file_size ? `${Math.round(Number(sourceMetadata.file_size) / 1024 / 1024 * 10) / 10} MB` : "未知"}</span>
              </div>
            )}

            {sourceDetail?.keyframes.length ? (
              <div className="keyframe-strip">
                {sourceDetail.keyframes.map((frame) => (
                  <button
                    className="keyframe-card"
                    key={`${frame.filename}-${frame.timestamp_label}`}
                    onClick={() => activeSource && openNote(activeSource.source_note_path, frame.timestamp_label)}
                  >
                    {keyframeUrls[frame.filename] ? (
                      <img src={keyframeUrls[frame.filename]} alt={frame.timestamp_label} />
                    ) : (
                      <span className="keyframe-placeholder"><ImageIcon size={18} /></span>
                    )}
                    <strong>{frame.timestamp_label}</strong>
                    <small>{frame.description || frame.ocr || "关键帧"}</small>
                  </button>
                ))}
              </div>
            ) : activeSource && currentSourceKind === "video" ? (
              <div className="empty-state">暂无关键帧。重新处理本地视频后会保存抽帧 OCR 与画面描述。</div>
            ) : null}

            <label className="inline-filter">
              <Search size={15} />
              <input value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)} placeholder="筛选片段或时间戳" />
            </label>

            <div className="segment-list scroll-list">
              {activeSegments.length > 0 ? activeSegments.map((segment, index) => (
                <button
                  className={`segment-row tone-${["blue", "yellow", "green"][index % 3]}`}
                  key={segment.id}
                  onClick={() => activeSource && openNote(activeSource.source_note_path, segment.timestamp_label)}
                >
                  <Clock3 size={15} />
                  <time>{segment.timestamp_label}</time>
                  <span>{segment.text || "空片段"}</span>
                  <small>{activeSource ? `[[${activeSource.source_note_path.replace(/\.md$/, "")}#${segment.timestamp_label}|${segment.timestamp_label}]]` : ""}</small>
                </button>
              )) : (
                <div className="empty-state">暂无片段。处理来源后这里会显示可追溯时间戳。</div>
              )}
            </div>
          </article>

          <article className="editor-pane sketch-card">
            <div className="editor-tabs">
              <button className={`paper-tab ${editorMode === "edit" ? "active" : ""}`} onClick={() => setEditorMode("edit")}>编辑</button>
              <button className={`paper-tab ${editorMode === "preview" ? "active" : ""}`} onClick={() => setEditorMode("preview")} disabled={!note}>预览</button>
              <button className="paper-tab" onClick={openOrganizationRules}>整理规则</button>
              <button className="paper-tab" onClick={renameCurrentNote} disabled={!note}>重命名</button>
              <button className="paper-tab" onClick={saveNote} disabled={!note || !dirty}><Save size={15} /> 保存</button>
              <button className="tab-more" aria-label="刷新" onClick={refreshAll}><MoreHorizontal size={18} /></button>
            </div>

            <div className="note-header">
              <p className="eyebrow">{note?.path || "未打开笔记"}</p>
              <h2>{note ? note.name.replace(/\.md$/, "") : "选择或新建一个 Markdown 笔记"}</h2>
              <div className="tag-row">
                {note ? displayTags(note.tags).map((tag) => <span key={tag}>#{tag.replace(/^#/, "")}</span>) : <span>#empty</span>}
                {dirty && <span>#unsaved</span>}
              </div>
            </div>

            {editorMode === "edit" ? (
              <textarea
                ref={editorRef}
                className="markdown-editor"
                value={editorContent}
                onChange={(event) => {
                  setEditorContent(event.target.value);
                  setDirty(true);
                }}
                placeholder="打开或创建笔记后开始编辑..."
              />
            ) : (
              <div className="preview-shell">
                <div className="preview-status">
                  <span>{previewPending ? "正在渲染" : dirty ? "未保存预览" : "已保存预览"}</span>
                </div>
                <div
                  ref={previewRef}
                  className="markdown-preview"
                  onClick={handlePreviewClick}
                  dangerouslySetInnerHTML={{ __html: previewHtml || "<p>暂无可预览内容。</p>" }}
                />
              </div>
            )}
          </article>
        </section>

        <section className="bottom-shelf">
          <article className="queue-card sketch-card">
            <div className="section-title compact">
              <h3>最近来源</h3>
              <span>{sources.length} items</span>
            </div>
            <div className="queue-list">
              {sources.length > 0 ? sources.slice(0, 8).map((source) => (
                <button className={source.id === activeSource?.id ? "queue-item active" : "queue-item"} key={source.id} onClick={() => setActiveSource(source)}>
                  <SourceIcon kind={sourceKind(source.source_type)} />
                  <span>{source.source_name}</span>
                  <small>{source.source_type}</small>
                </button>
              )) : <div className="empty-state">暂无来源。先导入一个文件。</div>}
            </div>
          </article>

          <article className="queue-card sketch-card">
            <div className="section-title compact">
              <h3>{activeNav === "检索" ? "检索结果" : activeNav === "图谱" ? "图谱边" : "最近笔记"}</h3>
              <span>{activeNav === "检索" ? `${searchResults.length} hits` : activeNav === "图谱" ? `${graph.edges.length} edges` : `${recentNotes.length} notes`}</span>
            </div>
            {activeNav === "检索" ? (
              <div className="note-list">
                {searchResults.map((result, index) => (
                  <button className="note-row" key={`${result.source_note_path}-${result.timestamp_label}-${index}`} onClick={() => openSearchResult(result)}>
                    <Search size={15} />
                    <span>{result.source_name} · {result.timestamp_label}<em>{result.text}</em></span>
                    <small>{result.concepts || "match"}</small>
                  </button>
                ))}
                {!searchResults.length && <div className="empty-state">输入关键词后按 Enter 检索来源片段、标题或概念。</div>}
              </div>
            ) : activeNav === "图谱" ? (
              <div className="graph-workbench">
                <GraphView graph={graph} currentPath={note?.path || ""} onOpenNote={openNote} />
                <div className="note-list scroll-list compact-list">
                {graph.edges.map((edge, index) => (
                  <button className="note-row" key={`${edge.source}-${edge.target}-${index}`} onClick={() => openNote(edge.source_path, edge.timestamp)}>
                    <GitFork size={15} />
                    <span>{edge.source} {"->"} {edge.target}</span>
                    <small>{edge.type}</small>
                  </button>
                ))}
                </div>
              </div>
            ) : (
              <div className="note-list">
                {recentNotes.map((item) => (
                  <button className={item.path === note?.path ? "note-row active" : "note-row"} key={item.path} onClick={() => openNote(item.path)}>
                    <FileText size={15} />
                    <span>{item.name.replace(/\.md$/, "")}</span>
                    <small>md</small>
                  </button>
                ))}
              </div>
            )}
          </article>
        </section>
      </section>

      <aside className="context-panel sketch-panel">
        <div className="panel-title">
          <span><PanelRight size={16} /> 上下文</span>
          <button aria-label="退出登录" onClick={logout}><LogOut size={16} /></button>
        </div>

        {message && <section className="context-card message-card">{message}</section>}

        <section className="context-card">
          <p className="eyebrow">Properties</p>
          <dl>
            <div><dt>用户</dt><dd>{user.username} / {user.role}</dd></div>
            <div><dt>路径</dt><dd>{note?.path || "-"}</dd></div>
            <div><dt>追溯</dt><dd>{note?.source_mentions.length || 0} 个时间戳</dd></div>
          </dl>
        </section>

        <section className="context-card">
          <p className="eyebrow">Backlinks</p>
          <div className="backlink-list">
            {note?.backlinks.length ? note.backlinks.map((link) => (
              <button key={`${link.path}-${link.label}`} onClick={() => openNote(link.path)}><Link2 size={14} /> {link.source}</button>
            )) : <span className="muted-text">暂无反链</span>}
          </div>
        </section>

        <section className="context-card">
          <p className="eyebrow">Graph sketch</p>
          <div className="mini-graph" aria-label="当前笔记关系图">
            <span className="node center"><Hash size={14} /> {note?.name.replace(/\.md$/, "") || "Note"}</span>
            <span className="node n1">{graph.nodes[0]?.id || "来源证据"}</span>
            <span className="node n2">{graph.nodes[1]?.id || "事实核查"}</span>
            <span className="node n3">{graph.nodes[2]?.id || "时间戳索引"}</span>
          </div>
          {graphSummary && <pre className="graph-summary">{graphSummary}</pre>}
        </section>

        <section className="context-card">
          <p className="eyebrow">{activeNav === "设置" ? "Model settings" : activeNav === "来源" ? "Process jobs" : "Action queue"}</p>
          {activeNav === "设置" ? (
            <div className="settings-form">
              <select value={settings.provider} onChange={(event) => selectProvider(event.target.value)}>
                {providers.map((provider) => <option key={provider.key} value={provider.key}>{provider.label}</option>)}
              </select>
              <input value={settings.api_base} onChange={(event) => setSettings({ ...settings, api_base: event.target.value })} placeholder="API Base" />
              <input value={settings.llm_model} onChange={(event) => setSettings({ ...settings, llm_model: event.target.value })} placeholder="LLM Model" />
              <input value={settings.vlm_model} onChange={(event) => setSettings({ ...settings, vlm_model: event.target.value })} placeholder="VLM Model" />
              <input value={settings.fact_model} onChange={(event) => setSettings({ ...settings, fact_model: event.target.value })} placeholder="Fact Model" />
              <input value={settings.whisper_model} onChange={(event) => setSettings({ ...settings, whisper_model: event.target.value })} placeholder="Whisper Model" />
              <select value={settings.whisper_device} onChange={(event) => setSettings({ ...settings, whisper_device: event.target.value })}>
                <option value="cpu">CPU</option>
                <option value="cuda">CUDA</option>
              </select>
              <input type="password" value={settings.api_key} onChange={(event) => setSettings({ ...settings, api_key: event.target.value })} placeholder="API Key" />
              <div className="settings-row">
                <label>
                  <span>ASR</span>
                  <select value={asrOptions.asr_engine} onChange={(event) => setAsrOptions({ ...asrOptions, asr_engine: event.target.value })}>
                    <option value="dashscope">DashScope</option>
                    <option value="local">Local Whisper</option>
                  </select>
                </label>
                <label>
                  <span>语言</span>
                  <select value={asrOptions.whisper_lang} onChange={(event) => setAsrOptions({ ...asrOptions, whisper_lang: event.target.value })}>
                    <option value="auto">Auto</option>
                    <option value="zh">中文</option>
                    <option value="en">English</option>
                    <option value="ja">日本語</option>
                  </select>
                </label>
              </div>
              {settingsStatus && (
                <p className={settingsStatus.ok ? "settings-status ok" : "settings-status error"}>
                  {settingsStatus.message} · {settingsStatus.status || "local"}
                </p>
              )}
              <div className="settings-actions">
                <button className="marker-button" onClick={testSettings}>测试配置</button>
                <button className="marker-button primary" onClick={saveSettings}>保存配置</button>
              </div>
            </div>
          ) : activeNav === "来源" ? (
            <div className="task-list">
              {jobs.slice(0, 5).map((job) => (
                <button className={job.id === activeJob?.id ? "job-row active" : "job-row"} key={job.id} onClick={() => setActiveJobId(job.id)}>
                  <span>{job.status}</span>
                  <strong>{job.progress}%</strong>
                </button>
              ))}
              {activeJob ? (
                <div className="job-detail">
                  <p><strong>{activeJob.id.slice(0, 10)}</strong> · {activeJob.status}</p>
                  {activeJob.result && <p>来源 {activeJob.result.processed_sources} · 笔记 {activeJob.result.written_notes}</p>}
                  {activeJob.error && <p className="error-text">{activeJob.error}</p>}
                  {activeJob.status === "failed" && <button className="tiny-button" onClick={() => retryJob(activeJob.id)}>重试</button>}
                  <div className="job-log-list">
                    {activeJob.logs.map((log) => (
                      <label key={`${log.time}-${log.message}`}><CircleDot size={15} /><span>{log.time} · {log.message}</span></label>
                    ))}
                  </div>
                </div>
              ) : <span className="muted-text">暂无处理任务</span>}
            </div>
          ) : (
            <div className="task-list">
              {(note?.source_mentions || []).slice(0, 4).map((item) => (
                <label key={`${item.source_note_path}-${item.timestamp_label}`}>
                  <ShieldAlert size={15} />
                  <span>{item.source_note_path}#{item.timestamp_label}</span>
                </label>
              ))}
              <label><ListChecks size={15} /><span>保存后自动刷新反链和图谱</span></label>
              {trashItems.slice(0, 4).map((item) => (
                <button className="trash-row" key={item.id} onClick={() => restoreTrashItem(item.id)}>
                  <RotateCcw size={15} />
                  <span>{item.name}</span>
                  <small>{item.original_path}</small>
                </button>
              ))}
            </div>
          )}
        </section>

        {user.role === "admin" && (
          <section className="context-card admin-log">
            <div className="section-title compact">
              <p className="eyebrow">Admin logs</p>
              <button className="tiny-button" onClick={exportLogs}>导出</button>
            </div>
            {logs.slice(0, 5).map((log, index) => (
              <p key={index}><strong>{String(log.action || "")}</strong> {String(log.detail || "")}</p>
            ))}
          </section>
        )}

        <section className="status-note">
          {loading ? <Loader2 size={17} className="spin" /> : <CheckCircle2 size={17} />}
          <span>本地优先，API Key 不在界面明文展示。</span>
        </section>
      </aside>
    </main>
  );
}

function GraphView({
  graph,
  currentPath,
  onOpenNote
}: {
  graph: GraphData;
  currentPath: string;
  onOpenNote: (path: string, anchor?: string) => void;
}) {
  const edges = useMemo(() => {
    const scoped = currentPath ? graph.edges.filter((edge) => edge.source_path === currentPath) : [];
    return (scoped.length ? scoped : graph.edges).slice(0, 18);
  }, [currentPath, graph.edges]);

  const nodeIds = Array.from(new Set(edges.flatMap((edge) => [edge.source, edge.target]))).slice(0, 14);
  const positions = nodeIds.map((id, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(1, nodeIds.length);
    const radius = id === nodeIds[0] ? 0 : 118;
    return {
      id,
      x: 160 + Math.cos(angle) * radius,
      y: 135 + Math.sin(angle) * radius
    };
  });
  const positionById = Object.fromEntries(positions.map((item) => [item.id, item]));
  const nodePath = (id: string) => graph.nodes.find((node) => node.id === id)?.path;

  if (!edges.length) return <div className="empty-state">暂无图谱边。处理来源或保存双链后刷新。</div>;

  return (
    <svg className="graph-canvas" viewBox="0 0 320 270" role="img" aria-label="知识图谱">
      {edges.map((edge, index) => {
        const from = positionById[edge.source];
        const to = positionById[edge.target];
        if (!from || !to) return null;
        return (
          <line
            key={`${edge.source}-${edge.target}-${index}`}
            x1={from.x}
            y1={from.y}
            x2={to.x}
            y2={to.y}
            className="graph-edge"
          />
        );
      })}
      {positions.map((node, index) => {
        const path = nodePath(node.id);
        return (
          <g
            key={node.id}
            className={`graph-node ${index === 0 ? "primary" : ""}`}
            onClick={() => path && onOpenNote(path)}
            tabIndex={path ? 0 : -1}
          >
            <circle cx={node.x} cy={node.y} r={index === 0 ? 24 : 19} />
            <text x={node.x} y={node.y + 4}>{node.id.slice(0, 10)}</text>
          </g>
        );
      })}
    </svg>
  );
}

function Tree({
  nodes,
  activePath,
  onOpenNote,
  onMove,
  onDelete
}: {
  nodes: VaultNode[];
  activePath: string;
  onOpenNote: (path: string) => void;
  onMove: (path: string) => void;
  onDelete: (path: string, name: string) => void;
}) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  if (!nodes.length) return <div className="empty-state">Vault 为空，点击新建笔记开始。</div>;
  return (
    <>
      {nodes.map((node) => {
        const isCollapsed = Boolean(collapsed[node.path]);
        return (
          <div className="tree-group" key={node.path}>
            {node.type === "directory" ? (
              <>
                <div className="tree-node-line">
                  <button
                    className="tree-folder"
                    aria-expanded={!isCollapsed}
                    onClick={() => setCollapsed((current) => ({ ...current, [node.path]: !current[node.path] }))}
                  >
                    <ChevronDown size={14} className={isCollapsed ? "chevron-collapsed" : ""} /> {node.name}
                  </button>
                  <button className="tree-action" aria-label="移动文件夹" onClick={() => onMove(node.path)}><MoveRight size={13} /></button>
                  <button className="tree-action danger" aria-label="删除文件夹" onClick={() => onDelete(node.path, node.name)}><Trash2 size={13} /></button>
                </div>
                {!isCollapsed && (
                  <div className="tree-children">
                    <Tree nodes={node.children || []} activePath={activePath} onOpenNote={onOpenNote} onMove={onMove} onDelete={onDelete} />
                  </div>
                )}
              </>
            ) : (
              <div className="tree-node-line">
                <button className={`tree-file ${node.path === activePath ? "selected" : ""}`} onClick={() => onOpenNote(node.path)}>
                  <BookOpen size={15} />
                  <span>{node.name.replace(/\.md$/, "")}</span>
                </button>
                <button className="tree-action" aria-label="移动笔记" onClick={() => onMove(node.path)}><MoveRight size={13} /></button>
                <button className="tree-action danger" aria-label="删除笔记" onClick={() => onDelete(node.path, node.name)}><Trash2 size={13} /></button>
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
