import datetime
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

    def upsert_source(
        self,
        source_name: str,
        source_type: str,
        source_uri: str,
        source_hash: str = "",
        duration: float = 0.0,
        asr_engine: str = "",
        vlm_model: str = "",
    ) -> Dict:
        source_note_path = self._source_note_path(source_name)
        source_note_rel_path = fs_router.get_relative_path(source_note_path)
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sources (
                    source_name, source_type, source_uri, source_hash, duration,
                    source_note_path, asr_engine, vlm_model, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_hash) DO UPDATE SET
                    source_name=excluded.source_name,
                    source_type=excluded.source_type,
                    source_uri=excluded.source_uri,
                    duration=excluded.duration,
                    source_note_path=excluded.source_note_path,
                    asr_engine=excluded.asr_engine,
                    vlm_model=excluded.vlm_model,
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
        source_note_path = source["source_note_path"]
        segments = self.get_segments(source_id)

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM concept_mentions WHERE source_id = ?", (source_id,))

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
            conn.commit()

    def write_source_note(self, source: Dict, segments: List[Dict], concepts: List[Dict]) -> str:
        source_note_abs_path = os.path.join(Config.OBSIDIAN_VAULT_PATH, source["source_note_path"].replace("/", os.sep))
        os.makedirs(os.path.dirname(source_note_abs_path), exist_ok=True)
        concept_links = [f"[[{item['concept']}]]" for item in concepts if item.get("concept")]

        lines = [
            "---",
            f"source_name: \"{source['source_name']}\"",
            f"source_type: \"{source['source_type']}\"",
            f"source_uri: \"{source['source_uri']}\"",
            f"source_hash: \"{source['source_hash']}\"",
            f"duration: {source.get('duration') or 0}",
            f"asr_engine: \"{source.get('asr_engine') or ''}\"",
            f"vlm_model: \"{source.get('vlm_model') or ''}\"",
            "tags: [source-note, crucible]",
            "---",
            "",
            f"# {source['source_name']}",
            "",
            "## 关联概念",
            ", ".join(concept_links) if concept_links else "暂无",
            "",
            "## 时间轴",
        ]

        for segment in segments:
            label = format_timestamp(float(segment.get("start") or 0.0))
            lines.extend([
                "",
                f"### {label}",
                "",
                segment.get("text", "").strip(),
            ])

        wiki_editor.write_wiki_atomic(source_note_abs_path, "\n".join(lines).rstrip() + "\n")
        return source_note_abs_path

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
            edges.append({
                "source": row["concept_name"],
                "target": row["timestamp_label"],
                "source_path": row["source_note_path"],
                "type": "concept_has_timestamp",
                "timestamp": row["timestamp_label"],
            })
        return edges

    def _source_note_path(self, source_name: str) -> str:
        safe_name = fs_router.sanitize_filename(source_name)
        return fs_router.resolve_note_path(os.path.join("Sources", safe_name), source_name)

    def _match_segments(self, concept_name: str, segments: List[Dict]) -> List[Dict]:
        pattern = re.compile(re.escape(concept_name), re.IGNORECASE)
        return [segment for segment in segments if pattern.search(segment.get("text", ""))]

    def _timestamp_to_seconds(self, timestamp_label: str) -> float:
        parts = [int(part) for part in (timestamp_label or "00:00:00").split(":")]
        while len(parts) < 3:
            parts.insert(0, 0)
        return float(parts[-3] * 3600 + parts[-2] * 60 + parts[-1])


source_index = SourceIndex()
