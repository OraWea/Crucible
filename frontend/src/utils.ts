import type { NotePayload, VaultNode } from "./types";

export function sourceKind(sourceType = "") {
  if (sourceType.includes("audio")) return "audio";
  if (sourceType.includes("document") || sourceType.includes("pdf") || sourceType.includes("doc")) return "document";
  return "video";
}

export function formatDuration(seconds?: number) {
  if (!seconds) return "未知时长";
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600).toString().padStart(2, "0");
  const m = Math.floor((total % 3600) / 60).toString().padStart(2, "0");
  const s = Math.floor(total % 60).toString().padStart(2, "0");
  return `${h}:${m}:${s}`;
}

export function displayTags(tags: NotePayload["tags"]) {
  if (Array.isArray(tags)) return tags;
  if (!tags) return [];
  return String(tags).split(",").map((tag) => tag.trim()).filter(Boolean);
}

export function displayMeta(value: unknown) {
  if (value === null || value === undefined || value === "") return "未知";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "无";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function parentPathOf(path = "") {
  const index = path.lastIndexOf("/");
  return index > -1 ? path.slice(0, index) : "";
}

export function normalizeUrlInput(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return "";
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  if (!trimmed.includes(" ") && (trimmed.includes(".") || trimmed.startsWith("www."))) {
    return `https://${trimmed}`;
  }
  return trimmed;
}

export function findFirstNote(nodes: VaultNode[]): VaultNode | null {
  for (const node of nodes) {
    if (node.type === "file") return node;
    const child = findFirstNote(node.children || []);
    if (child) return child;
  }
  return null;
}

export function flattenNotes(nodes: VaultNode[]): VaultNode[] {
  return nodes.flatMap((node) => node.type === "file" ? [node] : flattenNotes(node.children || []));
}

export function flattenDirectories(nodes: VaultNode[]): Array<{ path: string; label: string }> {
  return nodes.flatMap((node) => {
    if (node.type !== "directory") return [];
    return [
      { path: node.path, label: node.path },
      ...flattenDirectories(node.children || [])
    ];
  });
}
