import datetime
import json
import os
import re
from typing import Dict, List, Optional

from Crucible.config import Config
from Crucible.utils.db_manager import db_manager
from Crucible.utils.fs_router import fs_router
from Crucible.utils.wiki_editor import wiki_editor


def format_timestamp(seconds: float) -> str:
    total_seconds = max(0, int(seconds or 0))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def source_timestamp_link(source_note_rel_path: str, seconds: float) -> str:
    label = format_timestamp(seconds)
    note_target = source_note_rel_path[:-3] if source_note_rel_path.endswith(".md") else source_note_rel_path
    return f"[[{note_target}#{label}|{label}]]"


class SourceIndex:
    """管理来源页、时间轴片段和概念反查索引。"""

    def replace_source_index(
        self,
        *,
        source_name: str,
        source_type: str,
        source_uri: str,
        source_hash: str = "",
        duration: float = 0.0,
        asr_engine: str = "",
        vlm_model: str = "",
        metadata: Optional[Dict] = None,
        keyframes: Optional[List[Dict]] = None,
        segments: Optional[List[Dict]] = None,
        concepts: Optional[List[Dict]] = None,
    ) -> Dict:
        """在单个 SQLite 事务内替换来源、片段和概念反查索引。"""
        source_key = source_hash or source_uri
        source_note_path = self._source_note_rel_path(source_name)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        segments = segments or []
        concepts = concepts or []

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sources (
                    source_name, source_type, source_uri, source_hash, duration,
                    source_note_path, asr_engine, vlm_model, metadata_json,
                    keyframes_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_hash) DO UPDATE SET
                    source_name=excluded.source_name,
                    source_type=excluded.source_type,
                    source_uri=excluded.source_uri,
                    duration=excluded.duration,
                    source_note_path=excluded.source_note_path,
                    asr_engine=excluded.asr_engine,
                    vlm_model=excluded.vlm_model,
                    metadata_json=excluded.metadata_json,
                    keyframes_json=excluded.keyframes_json,
                    updated_at=excluded.updated_at
                """,
                (
                    source_name,
                    source_type,
                    source_uri,
                    source_key,
                    duration,
                    source_note_path,
                    asr_engine,
                    vlm_model,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    json.dumps(keyframes or [], ensure_ascii=False),
                    now,
                    now,
                ),
            )
            cursor.execute("SELECT * FROM sources WHERE source_hash = ?", (source_key,))
            source = dict(cursor.fetchone())
            source_id = source["id"]

            cursor.execute("DELETE FROM concept_mentions WHERE source_id = ?", (source_id,))
            cursor.execute("DELETE FROM segments WHERE source_id = ?", (source_id,))

            inserted_segments = []
            for idx, segment in enumerate(segments):
                start_time = float(segment.get("start") or 0.0)
                cursor.execute(
                    """
                    INSERT INTO segments (source_id, start_time, end_time, text, timestamp_label, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        start_time,
                        float(segment.get("end") or 0.0),
                        segment.get("text", ""),
                        format_timestamp(start_time),
                        idx,
                    ),
                )
                inserted_segments.append({
                    "id": cursor.lastrowid,
                    "source_id": source_id,
                    "start_time": start_time,
                    "end_time": float(segment.get("end") or 0.0),
                    "text": segment.get("text", ""),
                    "timestamp_label": format_timestamp(start_time),
                    "sort_order": idx,
                })

            self._insert_concept_mentions(cursor, source, inserted_segments, concepts)
            conn.commit()

        return source

    def upsert_source(
        self,
        source_name: str,
        source_type: str,
        source_uri: str,
        source_hash: str = "",
        duration: float = 0.0,
        asr_engine: str = "",
        vlm_model: str = "",
        metadata: Optional[Dict] = None,
        keyframes: Optional[List[Dict]] = None,
    ) -> Dict:
        source_note_rel_path = self._source_note_rel_path(source_name)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sources (
                    source_name, source_type, source_uri, source_hash, duration,
                    source_note_path, asr_engine, vlm_model, metadata_json,
                    keyframes_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_hash) DO UPDATE SET
                    source_name=excluded.source_name,
                    source_type=excluded.source_type,
                    source_uri=excluded.source_uri,
                    duration=excluded.duration,
                    source_note_path=excluded.source_note_path,
                    asr_engine=excluded.asr_engine,
                    vlm_model=excluded.vlm_model,
                    metadata_json=excluded.metadata_json,
                    keyframes_json=excluded.keyframes_json,
                    updated_at=excluded.updated_at
                """,
                (
                    source_name,
                    source_type,
                    source_uri,
                    source_hash or source_uri,
                    duration,
                    source_note_rel_path,
                    asr_engine,
                    vlm_model,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    json.dumps(keyframes or [], ensure_ascii=False),
                    now,
                    now,
                ),
            )
            conn.commit()
            cursor.execute("SELECT * FROM sources WHERE source_hash = ?", (source_hash or source_uri,))
            source = dict(cursor.fetchone())

        return source

    def replace_segments(self, source_id: int, segments: List[Dict]) -> None:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM segments WHERE source_id = ?", (source_id,))
            for idx, segment in enumerate(segments):
                cursor.execute(
                    """
                    INSERT INTO segments (source_id, start_time, end_time, text, timestamp_label, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        float(segment.get("start") or 0.0),
                        float(segment.get("end") or 0.0),
                        segment.get("text", ""),
                        format_timestamp(float(segment.get("start") or 0.0)),
                        idx,
                    ),
                )
            conn.commit()

    def replace_concept_mentions(self, source: Dict, concepts: List[Dict]) -> None:
        source_id = source["id"]
        segments = self.get_segments(source_id)

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM concept_mentions WHERE source_id = ?", (source_id,))
            self._insert_concept_mentions(cursor, source, segments, concepts)
            conn.commit()

    def write_source_note(self, source: Dict, segments: List[Dict], concepts: List[Dict]) -> str:
        source_note_abs_path = os.path.join(Config.OBSIDIAN_VAULT_PATH, source["source_note_path"].replace("/", os.sep))
        os.makedirs(os.path.dirname(source_note_abs_path), exist_ok=True)
        content = self._build_source_note_content(source, segments, concepts)
        wiki_editor.write_wiki_atomic(source_note_abs_path, content)
        return source_note_abs_path

    def _build_source_note_content(self, source: Dict, segments: List[Dict], concepts: List[Dict]) -> str:
        concept_links = [f"[[{item['concept']}]]" for item in concepts if item.get("concept")]
        metadata = self._json_field(source.get("metadata_json"), {})
        keyframes = self._json_field(source.get("keyframes_json"), [])
        source_name = source.get("source_name") or "Untitled Source"
        source_type = source.get("source_type") or "unknown"
        source_uri = source.get("source_uri") or ""
        source_hash = source.get("source_hash") or ""
        source_note_path = source.get("source_note_path") or self._source_note_path(source_name)
        timestamp_links = [
            source_timestamp_link(source_note_path, float(segment.get("start") or 0.0))
            for segment in segments
            if (segment.get("text") or "").strip()
        ]

        lines = [
            "---",
            f"source_name: \"{source_name}\"",
            f"source_type: \"{source_type}\"",
            f"source_uri: \"{source_uri}\"",
            f"source_hash: \"{source_hash}\"",
            f"duration: {source.get('duration') or 0}",
            f"asr_engine: \"{source.get('asr_engine') or ''}\"",
            f"vlm_model: \"{source.get('vlm_model') or ''}\"",
            f"source_timestamps: {self._yaml_string_list(timestamp_links)}",
            f"concepts: {self._yaml_string_list([item['concept'] for item in concepts if item.get('concept')])}",
            "tags: [source-note, crucible]",
            "---",
            "",
            f"# {source_name}",
            "",
            "## 元数据",
            "",
            f"- 来源路径: `{source_uri}`",
            f"- 文件 Hash: `{source_hash}`",
            f"- 时长: {format_timestamp(float(source.get('duration') or 0.0))}",
            f"- 分辨率: {metadata.get('resolution') or '未知'}",
            f"- FPS: {metadata.get('fps') or '未知'}",
            f"- 音轨: {metadata.get('audio_streams') or '未知'}",
            f"- 字幕: {metadata.get('subtitle_streams') or '未知'}",
            f"- 时间戳片段数: {len(timestamp_links)}",
            "",
            "## 关联概念",
            ", ".join(concept_links) if concept_links else "暂无",
            "",
            "## 关键帧",
        ]

        if keyframes:
            for item in keyframes:
                attachment = item.get("attachment_rel_path") or item.get("rel_path") or ""
                timestamp_label = item.get("timestamp_label") or format_timestamp(float(item.get("timestamp") or 0.0))
                lines.extend([
                    "",
                    f"### {timestamp_label}",
                    "",
                    f"![[{attachment}]]" if attachment else "",
                    "",
                    f"- OCR: {item.get('ocr') or '无'}",
                    f"- 画面描述: {item.get('description') or '无'}",
                ])
        else:
            lines.extend(["", "暂无关键帧。"])

        lines.extend([
            "",
            "## 时间轴",
        ])

        for segment in segments:
            label = format_timestamp(float(segment.get("start") or 0.0))
            link = source_timestamp_link(source_note_path, float(segment.get("start") or 0.0))
            lines.extend([
                "",
                f"### {label}",
                "",
                f"- 时间戳链接: {link}",
                "",
                segment.get("text", "").strip(),
            ])

        return "\n".join(lines).rstrip() + "\n"

    def get_source_detail(self, source_id: int) -> Optional[Dict]:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sources WHERE id = ?", (source_id,))
            row = cursor.fetchone()
        if not row:
            return None
        source = dict(row)
        return {
            "source": source,
            "segments": self.get_segments(source_id),
            "concept_mentions": self.get_mentions_for_source(source_id),
            "metadata": self._json_field(source.get("metadata_json"), {}),
            "keyframes": self._json_field(source.get("keyframes_json"), []),
        }

    def get_mentions_for_source(self, source_id: int) -> List[Dict]:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM concept_mentions WHERE source_id = ? ORDER BY concept_name ASC, timestamp_label ASC",
                (source_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_note_path_references(self, old_path: str, new_path: str) -> None:
        old_path = (old_path or "").replace("\\", "/")
        new_path = (new_path or "").replace("\\", "/")
        if not old_path or not new_path or old_path == new_path:
            return
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sources SET source_note_path = ? WHERE source_note_path = ?",
                (new_path, old_path),
            )
            cursor.execute(
                "UPDATE concept_mentions SET source_note_path = ? WHERE source_note_path = ?",
                (new_path, old_path),
            )
            conn.commit()

    def update_note_path_prefix(self, old_prefix: str, new_prefix: str) -> None:
        old_prefix = (old_prefix or "").strip("/").replace("\\", "/")
        new_prefix = (new_prefix or "").strip("/").replace("\\", "/")
        if not old_prefix or not new_prefix or old_prefix == new_prefix:
            return
        old_like = old_prefix + "/%"
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, source_note_path FROM sources WHERE source_note_path LIKE ?", (old_like,))
            source_rows = [dict(row) for row in cursor.fetchall()]
            for row in source_rows:
                next_path = new_prefix + row["source_note_path"][len(old_prefix):]
                cursor.execute("UPDATE sources SET source_note_path = ? WHERE id = ?", (next_path, row["id"]))
            cursor.execute("SELECT id, source_note_path FROM concept_mentions WHERE source_note_path LIKE ?", (old_like,))
            mention_rows = [dict(row) for row in cursor.fetchall()]
            for row in mention_rows:
                next_path = new_prefix + row["source_note_path"][len(old_prefix):]
                cursor.execute("UPDATE concept_mentions SET source_note_path = ? WHERE id = ?", (next_path, row["id"]))
            conn.commit()

    def update_concept_source_frontmatter(self, concept_name: str, source: Dict) -> None:
        file_path = fs_router.locate_concept_file(concept_name)
        if not file_path:
            return

        mentions = self.get_mentions_for_concept(concept_name, source_id=source["id"])
        links = [
            source_timestamp_link(source["source_note_path"], self._timestamp_to_seconds(item["timestamp_label"]))
            for item in mentions
        ]
        if not links:
            return

        content = wiki_editor.read_wiki(file_path)
        updated = wiki_editor.update_frontmatter_list_fields(
            content,
            {
                "sources": [source["source_note_path"]],
                "source_hashes": [source["source_hash"]],
                "source_timestamps": links,
            },
        )
        wiki_editor.write_wiki_atomic(file_path, updated)

    def search(self, keyword: str, limit: int = 100) -> List[Dict]:
        keyword = (keyword or "").strip()
        if not keyword:
            return []
        pattern = f"%{keyword}%"

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    s.source_name,
                    s.source_note_path,
                    sg.start_time,
                    sg.end_time,
                    sg.timestamp_label,
                    sg.text,
                    GROUP_CONCAT(DISTINCT cm.concept_name) AS concepts
                FROM segments sg
                JOIN sources s ON s.id = sg.source_id
                LEFT JOIN concept_mentions cm ON cm.segment_id = sg.id
                WHERE sg.text LIKE ? OR s.source_name LIKE ? OR cm.concept_name LIKE ?
                GROUP BY sg.id
                ORDER BY s.updated_at DESC, sg.sort_order ASC
                LIMIT ?
                """,
                (pattern, pattern, pattern, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_segments(self, source_id: int) -> List[Dict]:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM segments WHERE source_id = ? ORDER BY sort_order ASC",
                (source_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_mentions_for_concept(self, concept_name: str, source_id: Optional[int] = None) -> List[Dict]:
        query = "SELECT * FROM concept_mentions WHERE concept_name = ?"
        params = [concept_name]
        if source_id is not None:
            query += " AND source_id = ?"
            params.append(source_id)
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def graph_edges(self) -> List[Dict]:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    s.source_name,
                    s.source_note_path,
                    cm.concept_name,
                    cm.timestamp_label
                FROM concept_mentions cm
                JOIN sources s ON s.id = cm.source_id
                ORDER BY s.updated_at DESC, cm.concept_name ASC
                """
            )
            rows = [dict(row) for row in cursor.fetchall()]

        edges = []
        for row in rows:
            edges.append({
                "source": os.path.splitext(os.path.basename(row["source_note_path"]))[0],
                "target": row["concept_name"],
                "source_path": row["source_note_path"],
                "type": "source_mentions_concept",
                "timestamp": row["timestamp_label"],
            })
        return edges

    def _json_field(self, raw: str, fallback):
        try:
            return json.loads(raw or "")
        except Exception:
            return fallback

    def _yaml_string_list(self, values: List[str]) -> str:
        escaped = []
        for value in values:
            text = str(value).replace("\\", "\\\\").replace('"', '\\"')
            escaped.append(f'"{text}"')
        return "[" + ", ".join(escaped) + "]"

    def _source_note_path(self, source_name: str) -> str:
        safe_name = fs_router.sanitize_filename(source_name)
        return fs_router.resolve_note_path(os.path.join("Sources", safe_name), source_name)

    def _source_note_rel_path(self, source_name: str) -> str:
        return fs_router.get_relative_path(self._source_note_path(source_name))

    def _insert_concept_mentions(self, cursor, source: Dict, segments: List[Dict], concepts: List[Dict]) -> None:
        source_id = source["id"]
        source_note_path = source["source_note_path"]
        for concept in concepts:
            concept_name = concept.get("concept", "").strip()
            if not concept_name:
                continue
            matched_segments = self._match_segments(concept_name, segments)
            if not matched_segments and segments:
                matched_segments = [segments[0]]

            for segment in matched_segments:
                cursor.execute(
                    """
                    INSERT INTO concept_mentions (
                        source_id, concept_name, segment_id, timestamp_label, source_note_path
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        concept_name,
                        segment.get("id"),
                        segment.get("timestamp_label", "00:00:00"),
                        source_note_path,
                    ),
                )

    def _match_segments(self, concept_name: str, segments: List[Dict]) -> List[Dict]:
        pattern = re.compile(re.escape(concept_name), re.IGNORECASE)
        return [segment for segment in segments if pattern.search(segment.get("text", ""))]

    def _timestamp_to_seconds(self, timestamp_label: str) -> float:
        parts = [int(part) for part in (timestamp_label or "00:00:00").split(":")]
        while len(parts) < 3:
            parts.insert(0, 0)
        return float(parts[-3] * 3600 + parts[-2] * 60 + parts[-1])


source_index = SourceIndex()
