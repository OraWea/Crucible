import os
from typing import Dict, List

from Crucible.config import Config
from Crucible.utils.fs_router import fs_router
from Crucible.utils.source_index import source_index
from Crucible.utils.wiki_editor import wiki_editor


class NoteAnalyzer:
    """分析当前 Markdown 笔记的属性、出链、反链和来源时间戳。"""

    def analyze(self, file_path: str) -> Dict:
        content = wiki_editor.read_wiki(file_path)
        note_name = os.path.splitext(os.path.basename(file_path))[0]
        frontmatter = wiki_editor.read_frontmatter(content)
        outgoing = wiki_editor.extract_wiki_link_items(content)
        backlinks = self.find_backlinks(note_name, file_path)
        source_mentions = source_index.get_mentions_for_concept(note_name)

        return {
            "frontmatter": frontmatter,
            "outgoing_links": outgoing,
            "backlinks": backlinks,
            "source_mentions": source_mentions,
            "tags": frontmatter.get("tags", []),
        }

    def find_backlinks(self, note_name: str, current_path: str = "") -> List[Dict]:
        backlinks = []
        if not os.path.exists(Config.OBSIDIAN_VAULT_PATH):
            return backlinks

        for root, _, files in os.walk(Config.OBSIDIAN_VAULT_PATH):
            for file_name in files:
                if not file_name.endswith(".md"):
                    continue
                path = os.path.join(root, file_name)
                if current_path and os.path.abspath(path) == os.path.abspath(current_path):
                    continue
                content = wiki_editor.read_wiki(path)
                for item in wiki_editor.extract_wiki_link_items(content):
                    if item["target"] == note_name or item["target"].endswith("/" + note_name):
                        backlinks.append({
                            "source": os.path.splitext(file_name)[0],
                            "path": fs_router.get_relative_path(path),
                            "label": item["label"],
                        })
                        break
        return backlinks


note_analyzer = NoteAnalyzer()
