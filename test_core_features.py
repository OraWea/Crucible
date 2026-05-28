import os
import sys
import tempfile
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Crucible.config import Config
from Crucible.models.api_client import OpenAICompatibleClient
from Crucible.utils.fs_router import FSRouter
from Crucible.utils.graph_builder import KnowledgeGraphBuilder
from Crucible.utils.source_index import format_timestamp, source_timestamp_link
from Crucible.utils.wiki_editor import wiki_editor


class TestCoreFeatures(unittest.TestCase):
    def test_provider_preset_configures_client(self):
        client = OpenAICompatibleClient()
        client.configure_from_provider(
            "deepseek",
            api_key="test-key",
            model_name="deepseek-chat",
            vlm_model_name="deepseek-chat",
        )

        self.assertEqual(client.api_key, "test-key")
        self.assertEqual(client.api_base, "https://api.deepseek.com")
        self.assertEqual(client.model_name, "deepseek-chat")
        self.assertEqual(Config.VLM_MODEL_NAME, "deepseek-chat")

    def test_frontmatter_update_preserves_body(self):
        content = "---\ntags: [old]\n---\n# Title\nBody"
        updated = wiki_editor.update_frontmatter_fields(content, {"qe_score": 91, "qe_consistent": "true"})

        self.assertTrue(updated.startswith("---\n"))
        self.assertIn("tags: [old]", updated)
        self.assertIn("qe_score: 91", updated)
        self.assertIn("# Title\nBody", updated)

    def test_frontmatter_list_fields_merge_without_duplicates(self):
        content = '---\nsources: ["Sources/A.md"]\n---\nBody'
        updated = wiki_editor.update_frontmatter_list_fields(
            content,
            {"sources": ["Sources/A.md", "Sources/B.md"]},
        )

        self.assertIn('sources: ["Sources/A.md", "Sources/B.md"]', updated)

    def test_fs_router_blocks_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            router = FSRouter(vault_path=tmp_dir)

            with self.assertRaises(ValueError):
                router.resolve_note_path("../escape.md", "Escape")

    def test_fs_router_resolves_relative_note_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            router = FSRouter(vault_path=tmp_dir)
            target = router.resolve_note_path("Concepts/Transformer.md", "Transformer")

            self.assertEqual(os.path.basename(target), "Transformer.md")
            self.assertTrue(target.startswith(os.path.abspath(tmp_dir)))

    def test_graph_builder_extracts_obsidian_links(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = os.path.join(tmp_dir, "Source.md")
            with open(source_path, "w", encoding="utf-8") as f:
                f.write("# Source\nSee [[Target]] and [[Other|Alias]].")

            graph = KnowledgeGraphBuilder(vault_path=tmp_dir).build_graph()
            edges = {(edge["source"], edge["target"]) for edge in graph["edges"]}

            self.assertIn(("Source", "Target"), edges)
            self.assertIn(("Source", "Other"), edges)

    def test_timestamp_helpers(self):
        self.assertEqual(format_timestamp(3723), "01:02:03")
        self.assertEqual(
            source_timestamp_link("Sources/Demo.md", 12),
            "[[Sources/Demo#00:00:12|00:00:12]]",
        )

    def test_wiki_link_parser_supports_alias_and_anchor(self):
        items = wiki_editor.extract_wiki_link_items("[[Sources/Demo#00:00:12|Clip]] and [[Concept]]")

        self.assertEqual(items[0]["target"], "Sources/Demo")
        self.assertEqual(items[0]["anchor"], "00:00:12")
        self.assertEqual(items[0]["alias"], "Clip")
        self.assertEqual(items[1]["target"], "Concept")

    def test_markdown_preview_converts_wiki_links(self):
        html = wiki_editor.render_markdown_preview("See [[Concept|Alias]].")

        self.assertIn("crucible://note/", html)
        self.assertIn("Alias", html)


if __name__ == "__main__":
    unittest.main()
