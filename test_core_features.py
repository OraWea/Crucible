import os
import hashlib
import sys
import tempfile
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Crucible.config import Config
from Crucible.models.api_client import OpenAICompatibleClient, ProviderUnavailableError
from Crucible.utils.processing_workflow import ProcessingOptions, ProcessingWorkflow
from Crucible.utils.fs_router import FSRouter
from Crucible.utils.graph_builder import KnowledgeGraphBuilder
from Crucible.utils.source_index import SourceIndex
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

    def test_cloud_provider_requires_valid_api_key_before_request(self):
        old_provider = Config.LLM_PROVIDER
        try:
            Config.LLM_PROVIDER = "dashscope"
            client = OpenAICompatibleClient(api_key="your-api-key", provider="dashscope")

            with self.assertRaises(ProviderUnavailableError):
                client.chat([{"role": "user", "content": "ping"}], timeout=1)
        finally:
            Config.LLM_PROVIDER = old_provider

    def test_local_provider_allows_empty_api_key(self):
        self.assertTrue(Config.has_valid_api_key("", provider="ollama"))
        self.assertTrue(Config.has_valid_api_key(None, provider="lmstudio"))

    def test_secret_redaction_masks_runtime_key(self):
        old_key = Config.LLM_API_KEY
        try:
            Config.LLM_API_KEY = "sk-test-secret-123456"
            redacted = Config.redact_secrets("failed with sk-test-secret-123456")

            self.assertNotIn("sk-test-secret-123456", redacted)
            self.assertIn("sk-t...3456", redacted)
        finally:
            Config.LLM_API_KEY = old_key

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

    def test_markdown_preview_escapes_raw_html(self):
        html = wiki_editor.render_markdown_preview('<img src=x onerror="alert(1)"><script>alert(2)</script>')

        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertNotIn(' onerror="', html)
        self.assertIn("&lt;script&gt;", html)

    def test_markdown_preview_uses_bounded_cache(self):
        old_limit = wiki_editor.PREVIEW_CACHE_LIMIT
        try:
            wiki_editor.PREVIEW_CACHE_LIMIT = 2
            wiki_editor._preview_cache.clear()

            first = wiki_editor.render_markdown_preview("See [[Concept|Alias]].")
            second = wiki_editor.render_markdown_preview("See [[Concept|Alias]].")
            wiki_editor.render_markdown_preview("One")
            wiki_editor.render_markdown_preview("Two")
            wiki_editor.render_markdown_preview("Three")

            self.assertEqual(first, second)
            self.assertLessEqual(len(wiki_editor._preview_cache), 2)
        finally:
            wiki_editor.PREVIEW_CACHE_LIMIT = old_limit
            wiki_editor._preview_cache.clear()

    def test_fs_router_trash_and_restore_path(self):
        old_trash_dir = Config.TRASH_DIR
        old_backup_dir = Config.BACKUP_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                Config.BACKUP_DIR = os.path.join(tmp_dir, "backups")
                Config.TRASH_DIR = os.path.join(Config.BACKUP_DIR, "trash")
                os.makedirs(Config.TRASH_DIR, exist_ok=True)
                router = FSRouter(vault_path=os.path.join(tmp_dir, "vault"))
                note_path = router.create_note(router.vault_path, "Demo.md", "# Demo")

                manifest = router.trash_path(note_path, "Demo.md")
                self.assertFalse(os.path.exists(note_path))
                self.assertEqual(manifest["original_path"], "Demo.md")

                restored = router.restore_trash(manifest["id"])
                self.assertTrue(os.path.exists(os.path.join(router.vault_path, restored["restored_path"])))
        finally:
            Config.TRASH_DIR = old_trash_dir
            Config.BACKUP_DIR = old_backup_dir

    def test_source_index_json_detail_fields(self):
        import Crucible.utils.source_index as source_index_module

        old_db_manager = source_index_module.db_manager
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                db_path = os.path.join(tmp_dir, "test.db")
                from Crucible.utils.db_manager import DBManager

                source_index_module.db_manager = DBManager(db_path)
                index = SourceIndex()
                source = index.upsert_source(
                    source_name="Demo.mp4",
                    source_type="video",
                    source_uri="Demo.mp4",
                    source_hash="hash-demo",
                    duration=12,
                    metadata={"resolution": "1920x1080"},
                    keyframes=[{"filename": "00-00-01.jpg", "timestamp_label": "00:00:01"}],
                )
                detail = index.get_source_detail(source["id"])

                self.assertEqual(detail["metadata"]["resolution"], "1920x1080")
                self.assertEqual(detail["keyframes"][0]["filename"], "00-00-01.jpg")
        finally:
            source_index_module.db_manager = old_db_manager

    def test_source_note_contains_traceable_timestamp_links(self):
        index = SourceIndex()
        source = {
            "source_name": "Demo.mp4",
            "source_type": "video",
            "source_uri": "Demo.mp4",
            "source_hash": "hash-demo",
            "duration": 70,
            "source_note_path": "Sources/Demo.mp4.md",
            "asr_engine": "local",
            "vlm_model": "vlm-test",
            "metadata_json": '{"resolution":"1920x1080","audio_streams":1,"subtitle_streams":0}',
            "keyframes_json": "[]",
        }
        segments = [
            {"start": 12, "end": 15, "text": "Transformer 使用自注意力机制。"},
            {"start": 65, "end": 70, "text": "结尾总结。"},
        ]
        concepts = [{"concept": "Transformer"}, {"concept": "自注意力机制"}]

        content = index._build_source_note_content(source, segments, concepts)
        frontmatter = wiki_editor.read_frontmatter(content)
        links = wiki_editor.extract_wiki_link_items(content)

        self.assertIn("source_timestamps", frontmatter)
        self.assertIn("[[Sources/Demo.mp4#00:00:12|00:00:12]]", frontmatter["source_timestamps"])
        self.assertIn("[[Sources/Demo.mp4#00:01:05|00:01:05]]", frontmatter["source_timestamps"])
        self.assertIn('concepts: ["Transformer", "自注意力机制"]', content)
        self.assertIn("- 时间戳链接: [[Sources/Demo.mp4#00:00:12|00:00:12]]", content)
        self.assertIn("- 时间戳链接: [[Sources/Demo.mp4#00:01:05|00:01:05]]", content)
        self.assertTrue(any(item["target"] == "Sources/Demo.mp4" and item["anchor"] == "00:00:12" for item in links))
        self.assertTrue(any(item["target"] == "Transformer" for item in links))

    def test_processing_workflow_structured_metadata_block(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = os.path.join(tmp_dir, "demo.mp4")
            with open(source_path, "wb") as f:
                f.write(b"demo-video-bytes")

            workflow = ProcessingWorkflow(ProcessingOptions(file_paths=[]))
            source_hash = workflow._source_hash(source_path, is_url=False)
            metadata = {
                "file_size": os.path.getsize(source_path),
                "resolution": "1280x720",
                "width": 1280,
                "height": 720,
                "fps": 29.97,
                "audio_streams": 1,
                "subtitle_streams": 2,
            }
            segments = [
                {"start": 1.2, "end": 3.8, "text": "第一段内容"},
                {"start": 65, "end": 70, "text": "第二段内容"},
            ]

            structured = workflow._prepend_source_metadata(
                source=source_path,
                source_name="demo.mp4",
                source_ext=".mp4",
                source_type="video",
                source_hash=source_hash,
                duration=70.4,
                metadata=metadata,
                segments=segments,
                content="【视频声音转写内容】:\nbody",
                is_url=False,
            )

            self.assertEqual(source_hash, hashlib.sha256(b"demo-video-bytes").hexdigest())
            self.assertIn("source_type: video", structured)
            self.assertIn("source_ext: .mp4", structured)
            self.assertIn(f"source_hash_sha256: {source_hash}", structured)
            self.assertIn("duration_label: 00:01:10", structured)
            self.assertIn("resolution: 1280x720", structured)
            self.assertIn("audio_streams: 1", structured)
            self.assertIn("subtitle_streams: 2", structured)
            self.assertIn("【来源时间戳片段】", structured)
            self.assertIn("- 00:00:01 - 00:00:03: 第一段内容", structured)
            self.assertIn("- 00:01:05 - 00:01:10: 第二段内容", structured)

    def test_processing_workflow_url_hash_is_stable(self):
        workflow = ProcessingWorkflow(ProcessingOptions(file_paths=[]))
        url = "https://example.com/video?id=42"

        self.assertEqual(
            workflow._source_hash(url, is_url=True),
            hashlib.sha256(url.encode("utf-8")).hexdigest(),
        )

    def test_process_entrypoints_keep_heavy_work_async(self):
        root_dir = os.path.dirname(os.path.abspath(__file__))
        backend_path = os.path.join(root_dir, "backend", "app.py")
        gui_path = os.path.join(root_dir, "gui.py")

        with open(backend_path, "r", encoding="utf-8") as f:
            backend_source = f.read()
        with open(gui_path, "r", encoding="utf-8") as f:
            gui_source = f.read()

        self.assertIn("ThreadPoolExecutor", backend_source)
        self.assertIn("def _process_worker_count()", backend_source)
        self.assertIn("_process_executor.submit(runner)", backend_source)
        self.assertIn("def _job_payload_snapshot", backend_source)
        self.assertIn('data["api_key"] = None', backend_source)
        self.assertIn('"payload": _job_payload_snapshot(payload)', backend_source)
        self.assertIn("safe_error = Config.redact_secrets(str(exc))", backend_source)
        self.assertIn('_jobs[job_id]["error"] = safe_error', backend_source)
        self.assertNotIn('"payload": payload.model_dump()', backend_source)
        self.assertNotIn('"payload": payload.dict()', backend_source)
        self.assertNotIn('Config.mask_secret(data["api_key"])', backend_source)
        self.assertNotIn("threading.Thread(target=runner", backend_source)
        self.assertIn("self.active_worker and self.active_worker.isRunning()", gui_source)
        self.assertIn("file_paths=list(self.selected_files)", gui_source)

    def test_provider_downgrade_paths_are_present(self):
        root_dir = os.path.dirname(os.path.abspath(__file__))
        llm_path = os.path.join(root_dir, "models", "llm_core.py")
        vlm_path = os.path.join(root_dir, "models", "vlm_analyzer.py")

        with open(llm_path, "r", encoding="utf-8") as f:
            llm_source = f.read()
        with open(vlm_path, "r", encoding="utf-8") as f:
            vlm_source = f.read()

        self.assertIn("except ProviderUnavailableError", llm_source)
        self.assertIn("return []", llm_source)
        self.assertIn("_build_fallback_concept_note", llm_source)
        self.assertIn("VLM Provider 与本地模型均不可用，跳过关键帧视觉分析", vlm_source)
        self.assertIn("Config.redact_secrets", vlm_source)


if __name__ == "__main__":
    unittest.main()
