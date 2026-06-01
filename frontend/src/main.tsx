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
  Link2,
  ListChecks,
  Loader2,
  LogOut,
  MoreHorizontal,
  PanelRight,
  Play,
  Save,
  Search,
  Settings2,
  ShieldAlert,
  Sparkles,
  UploadCloud,
  Video
} from "lucide-react";
import "./styles.css";

type User = {
  username: string;
  role: "admin" | "user";
};

type VaultNode = {
  name: string;
  type: "directory" | "file";
  path: string;
  abs_path?: string;
  children?: VaultNode[];
};

type NotePayload = {
  path: string;
  name: string;
  anchor?: string;
  content: string;
  preview_html: string;
  frontmatter: Record<string, unknown>;
  outgoing_links: Array<{ raw: string; target: string; anchor: string; label: string }>;
  backlinks: Array<{ source: string; path: string; label: string }>;
  source_mentions: Array<{ concept_name: string; source_note_path: string; timestamp_label: string }>;
  tags: string[] | string;
};

type SourceRecord = {
  id: number;
  source_name: string;
  source_type: string;
  source_uri: string;
  duration?: number;
  source_note_path: string;
  updated_at?: string;
};

type SegmentRecord = {
  id: number;
  timestamp_label: string;
  text: string;
  start_time: number;
  end_time: number;
};

type GraphData = {
  nodes: Array<{ id: string; path: string; in_degree: number; out_degree: number }>;
  edges: Array<{ source: string; target: string; source_path: string; type: string; timestamp: string }>;
};

type SearchResult = {
  source_name: string;
  source_note_path: string;
  timestamp_label: string;
  text: string;
  concepts: string;
};

type ProcessJob = {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  progress: number;
  logs: Array<{ message: string; progress: number; time: string }>;
  result?: { processed_sources: number; written_notes: number };
  error?: string;
};

type ProviderInfo = {
  key: string;
  label: string;
  preset: { api_base: string; model: string; vlm_model?: string };
};

const TOKEN_KEY = "crucible_web_token";

const navItems = [
  { label: "Vault", icon: FolderOpen },
  { label: "来源", icon: Video },
  { label: "检索", icon: Search },
  { label: "图谱", icon: GitFork },
  { label: "设置", icon: Settings2 }
];

function sourceKind(sourceType = "") {
  if (sourceType.includes("audio")) return "audio";
  if (sourceType.includes("document") || sourceType.includes("pdf") || sourceType.includes("doc")) return "document";
  return "video";
}

function SourceIcon({ kind }: { kind: string }) {
  if (kind === "audio") return <AudioLines size={16} />;
  if (kind === "document") return <FileText size={16} />;
  return <Video size={16} />;
}

function formatDuration(seconds?: number) {
  if (!seconds) return "未知时长";
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600).toString().padStart(2, "0");
  const m = Math.floor((total % 3600) / 60).toString().padStart(2, "0");
  const s = Math.floor(total % 60).toString().padStart(2, "0");
  return `${h}:${m}:${s}`;
}

function displayTags(tags: NotePayload["tags"]) {
  if (Array.isArray(tags)) return tags;
  if (!tags) return [];
  return String(tags).split(",").map((tag) => tag.trim()).filter(Boolean);
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || "");
  const [user, setUser] = useState<User | null>(null);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [activeNav, setActiveNav] = useState("Vault");

  const [tree, setTree] = useState<VaultNode[]>([]);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [activeSource, setActiveSource] = useState<SourceRecord | null>(null);
  const [segments, setSegments] = useState<SegmentRecord[]>([]);
  const [note, setNote] = useState<NotePayload | null>(null);
  const [editorContent, setEditorContent] = useState("");
  const [dirty, setDirty] = useState(false);
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [] });
  const [graphSummary, setGraphSummary] = useState("");
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [jobs, setJobs] = useState<ProcessJob[]>([]);
  const [activeJobId, setActiveJobId] = useState("");
  const [logs, setLogs] = useState<Array<Record<string, unknown>>>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [settings, setSettings] = useState({
    provider: "dashscope",
    api_base: "",
    llm_model: "",
    vlm_model: "",
    fact_model: "",
    api_key: ""
  });
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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

  const showError = useCallback((error: unknown) => {
    setMessage(error instanceof Error ? error.message : String(error));
  }, []);

  const openNote = useCallback(async (path: string, anchor = "") => {
    try {
      const suffix = anchor ? `?anchor=${encodeURIComponent(anchor)}` : "";
      const loaded = await api<NotePayload>(`/api/notes/${encodeURIComponent(path).replace(/%2F/g, "/")}${suffix}`);
      setNote(loaded);
      setEditorContent(loaded.content);
      setDirty(false);
      setActiveNav("Vault");
    } catch (error) {
      showError(error);
    }
  }, [api, showError]);

  const refreshVault = useCallback(async () => {
    const data = await api<{ nodes: VaultNode[] }>("/api/vault/tree");
    setTree(data.nodes);
    const firstNote = findFirstNote(data.nodes);
    if (!note && firstNote) await openNote(firstNote.path);
  }, [api, note, openNote]);

  const refreshSources = useCallback(async () => {
    const data = await api<{ sources: SourceRecord[] }>("/api/sources");
    setSources(data.sources);
    if (!activeSource && data.sources.length > 0) setActiveSource(data.sources[0]);
  }, [api, activeSource]);

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

  const refreshAll = useCallback(async () => {
    try {
      setLoading(true);
      await Promise.all([refreshVault(), refreshSources(), refreshGraph(), refreshJobs(), refreshLogs()]);
      setMessage("已同步后端状态");
    } catch (error) {
      showError(error);
    } finally {
      setLoading(false);
    }
  }, [refreshVault, refreshSources, refreshGraph, refreshJobs, refreshLogs, showError]);

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

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUser(null);
    setNote(null);
    setTree([]);
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
      setSegments([]);
      return;
    }
    api<{ segments: SegmentRecord[] }>(`/api/sources/${activeSource.id}/segments`)
      .then((data) => setSegments(data.segments))
      .catch(() => setSegments([]));
  }, [activeSource, api]);

  useEffect(() => {
    if (!jobs.some((job) => job.status === "running" || job.status === "queued")) return;
    const id = window.setInterval(refreshJobs, 1800);
    return () => window.clearInterval(id);
  }, [jobs, refreshJobs]);

  const recentNotes = useMemo(() => flattenNotes(tree).slice(0, 8), [tree]);
  const activeJob = jobs.find((job) => job.id === activeJobId) || jobs[0];
  const currentSourceKind = sourceKind(activeSource?.source_type);
  const activeSegments = segments.slice(0, 6);

  const saveNote = async () => {
    if (!note) return;
    try {
      const saved = await api<NotePayload>(`/api/notes/${encodeURIComponent(note.path).replace(/%2F/g, "/")}`, {
        method: "PUT",
        body: JSON.stringify({ content: editorContent })
      });
      setNote(saved);
      setEditorContent(saved.content);
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
        body: JSON.stringify({ name, parent_path: "", template: "空白" })
      });
      setNote(created);
      setEditorContent(created.content);
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
        body: JSON.stringify({ name, parent_path: "" })
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
      setDirty(false);
    } catch (error) {
      showError(error);
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
        body: JSON.stringify({
          sources: uploaded.files.map((file) => file.path),
          whisper_lang: "auto",
          asr_engine: "dashscope",
          provider: settings.provider,
          api_base: settings.api_base,
          llm_model: settings.llm_model,
          vlm_model: settings.vlm_model,
          fact_model: settings.fact_model,
          api_key: settings.api_key || undefined
        })
      });
      setActiveJobId(process.job_id);
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
        body: JSON.stringify({
          sources: [activeSource.source_uri],
          whisper_lang: "auto",
          provider: settings.provider,
          api_base: settings.api_base,
          llm_model: settings.llm_model,
          vlm_model: settings.vlm_model,
          fact_model: settings.fact_model,
          api_key: settings.api_key || undefined
        })
      });
      setActiveJobId(data.job_id);
      setMessage("当前来源已加入处理任务");
      await refreshJobs();
    } catch (error) {
      showError(error);
    }
  };

  const addUrlAndProcess = async () => {
    const url = window.prompt("输入在线视频或网页来源 URL", "https://");
    if (!url || !/^https?:\/\/\S+$/i.test(url.trim())) {
      if (url) setMessage("请输入合法的 HTTP/HTTPS 链接");
      return;
    }
    try {
      const data = await api<{ job_id: string }>("/api/process", {
        method: "POST",
        body: JSON.stringify({
          sources: [url.trim()],
          whisper_lang: "auto",
          provider: settings.provider,
          api_base: settings.api_base,
          llm_model: settings.llm_model,
          vlm_model: settings.vlm_model,
          fact_model: settings.fact_model,
          api_key: settings.api_key || undefined
        })
      });
      setActiveJobId(data.job_id);
      setActiveNav("来源");
      setMessage("URL 来源处理任务已启动");
      await refreshJobs();
    } catch (error) {
      showError(error);
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

  const selectProvider = (providerKey: string) => {
    const provider = providers.find((item) => item.key === providerKey);
    setSettings((current) => ({
      ...current,
      provider: providerKey,
      api_base: provider?.preset.api_base || current.api_base,
      llm_model: provider?.preset.model || current.llm_model,
      vlm_model: provider?.preset.vlm_model || provider?.preset.model || current.vlm_model
    }));
  };

  if (!user) {
    return (
      <main className="login-shell">
        <form className="login-card sketch-card" onSubmit={login}>
          <div className="brand-mark">
            <span className="brand-sigil">C</span>
            <div>
              <p className="eyebrow">Crucible Web</p>
              <h1>登录知识库</h1>
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
            {loading ? <Loader2 size={17} className="spin" /> : <Play size={17} />}
            登录
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
          <Tree nodes={tree} activePath={note?.path || ""} onOpenNote={openNote} />
        </section>
      </aside>

      <section className="main-workspace">
        <header className="command-bar sketch-card">
          <label className="search-box">
            <Search size={18} />
            <input
              placeholder="搜索笔记、来源、概念或时间戳..."
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") runSearch();
              }}
            />
          </label>
          <div className="command-actions">
            <input ref={fileInputRef} type="file" multiple hidden onChange={(event) => uploadAndProcess(event.target.files)} />
            <button className="marker-button" onClick={() => fileInputRef.current?.click()}>
              <UploadCloud size={17} />
              导入来源
            </button>
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

            <div className="segment-list">
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
              <button className="paper-tab active">编辑</button>
              <button className="paper-tab" onClick={() => note && setMessage("预览 HTML 已在右侧上下文同步生成")}>预览</button>
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

            <textarea
              className="markdown-editor"
              value={editorContent}
              onChange={(event) => {
                setEditorContent(event.target.value);
                setDirty(true);
              }}
              placeholder="打开或创建笔记后开始编辑..."
            />
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
                    <span>{result.source_name} · {result.timestamp_label}</span>
                    <small>{result.concepts || "match"}</small>
                  </button>
                ))}
              </div>
            ) : activeNav === "图谱" ? (
              <div className="note-list">
                {graph.edges.slice(0, 8).map((edge, index) => (
                  <button className="note-row" key={`${edge.source}-${edge.target}-${index}`} onClick={() => openNote(edge.source_path, edge.timestamp)}>
                    <GitFork size={15} />
                    <span>{edge.source} {"->"} {edge.target}</span>
                    <small>{edge.type}</small>
                  </button>
                ))}
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
              <input type="password" value={settings.api_key} onChange={(event) => setSettings({ ...settings, api_key: event.target.value })} placeholder="API Key" />
              <button className="marker-button primary" onClick={saveSettings}>保存配置</button>
            </div>
          ) : activeNav === "来源" ? (
            <div className="task-list">
              {jobs.slice(0, 5).map((job) => (
                <button className="job-row" key={job.id} onClick={() => setActiveJobId(job.id)}>
                  <span>{job.status}</span>
                  <strong>{job.progress}%</strong>
                </button>
              ))}
              {activeJob?.logs.slice(-3).map((log) => <label key={`${log.time}-${log.message}`}><CircleDot size={15} /><span>{log.message}</span></label>)}
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

function Tree({ nodes, activePath, onOpenNote }: { nodes: VaultNode[]; activePath: string; onOpenNote: (path: string) => void }) {
  if (!nodes.length) return <div className="empty-state">Vault 为空，点击新建笔记开始。</div>;
  return (
    <>
      {nodes.map((node) => (
        <div className="tree-group" key={node.path}>
          {node.type === "directory" ? (
            <>
              <button className="tree-folder"><ChevronDown size={14} /> {node.name}</button>
              <div className="tree-children">
                <Tree nodes={node.children || []} activePath={activePath} onOpenNote={onOpenNote} />
              </div>
            </>
          ) : (
            <button className={`tree-file ${node.path === activePath ? "selected" : ""}`} onClick={() => onOpenNote(node.path)}>
              <BookOpen size={15} />
              <span>{node.name.replace(/\.md$/, "")}</span>
            </button>
          )}
        </div>
      ))}
    </>
  );
}

function findFirstNote(nodes: VaultNode[]): VaultNode | null {
  for (const node of nodes) {
    if (node.type === "file") return node;
    const child = findFirstNote(node.children || []);
    if (child) return child;
  }
  return null;
}

function flattenNotes(nodes: VaultNode[]): VaultNode[] {
  return nodes.flatMap((node) => node.type === "file" ? [node] : flattenNotes(node.children || []));
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
