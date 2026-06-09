export type User = {
  username: string;
  role: "admin" | "user";
};

export type VaultNode = {
  name: string;
  type: "directory" | "file";
  path: string;
  abs_path?: string;
  children?: VaultNode[];
};

export type NotePayload = {
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

export type SourceRecord = {
  id: number;
  source_name: string;
  source_type: string;
  source_uri: string;
  source_hash?: string;
  duration?: number;
  source_note_path: string;
  updated_at?: string;
};

export type SegmentRecord = {
  id: number;
  timestamp_label: string;
  text: string;
  start_time: number;
  end_time: number;
};

export type KeyframeRecord = {
  timestamp: number;
  timestamp_label: string;
  filename: string;
  attachment_rel_path: string;
  ocr?: string;
  description?: string;
};

export type ConceptMention = {
  id: number;
  concept_name: string;
  timestamp_label: string;
  source_note_path: string;
};

export type SourceDetail = {
  source: SourceRecord;
  segments: SegmentRecord[];
  concept_mentions: ConceptMention[];
  metadata: Record<string, unknown>;
  keyframes: KeyframeRecord[];
};

export type GraphData = {
  nodes: Array<{ id: string; path: string; in_degree: number; out_degree: number }>;
  edges: Array<{ source: string; target: string; source_path: string; type: string; timestamp: string }>;
};

export type SearchResult = {
  source_name: string;
  source_note_path: string;
  timestamp_label: string;
  text: string;
  concepts: string;
};

export type ProcessJob = {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  progress: number;
  logs: Array<{ message: string; progress: number; time: string }>;
  result?: { processed_sources: number; written_notes: number };
  error?: string;
  payload?: Record<string, unknown>;
};

export type ProviderInfo = {
  key: string;
  label: string;
  preset: { api_base: string; model: string; vlm_model?: string };
};

export type TrashItem = {
  id: string;
  name: string;
  type: "file" | "directory";
  original_path: string;
  trashed_at: string;
};

export type ConfigTestResult = {
  ok: boolean;
  status: number;
  message: string;
  has_valid_api_key: boolean;
};
