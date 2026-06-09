import hashlib
import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from Crucible.config import Config
from Crucible.models.api_client import llm_client
from Crucible.models.fact_checker import fact_checker
from Crucible.models.llm_core import llm_core
from Crucible.models.vlm_analyzer import vlm_analyzer
from Crucible.models.whisper_model import WhisperTranscriber
from Crucible.utils.audio_processor import audio_processor
from Crucible.utils.doc_parser import doc_parser
from Crucible.utils.fs_router import fs_router
from Crucible.utils.source_index import source_index
from Crucible.utils.video_processor import video_processor
from Crucible.utils.wiki_editor import wiki_editor


ProgressCallback = Callable[[str, int], None]


@dataclass
class ProcessingOptions:
    file_paths: List[str]
    whisper_lang: str = "auto"
    asr_engine: str = "dashscope"
    provider: str = "dashscope"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    llm_model: Optional[str] = None
    vlm_model: Optional[str] = None
    fact_model: Optional[str] = None


@dataclass
class ProcessingResult:
    processed_sources: int = 0
    written_notes: int = 0


class ProcessingWorkflow:
    """AI 知识库处理流程，供 GUI 线程和测试复用。"""

    def __init__(self, options: ProcessingOptions, progress_callback: ProgressCallback = None):
        self.options = options
        self.progress = progress_callback or (lambda _msg, _value: None)

    def run(self) -> ProcessingResult:
        llm_client.configure_from_provider(
            self.options.provider,
            api_key=self.options.api_key,
            api_base=self.options.api_base,
            model_name=self.options.llm_model,
            vlm_model_name=self.options.vlm_model,
            fact_checker_model_name=self.options.fact_model,
        )

        result = ProcessingResult()
        self.progress(">>> Crucible AI 工作流启动 ...", 5)

        for source in self.options.file_paths:
            source_payload = self._load_source(source)
            structured_source = source_payload.get("structured_source", "")
            if not structured_source:
                continue

            result.processed_sources += 1
            self.progress("第四步: LLM 智能提炼核心概念...", 75)
            extracted_concepts = llm_core.extract_concepts(structured_source)

            source_record = source_index.upsert_source(
                source_name=source_payload["source_name"],
                source_type=source_payload["source_type"],
                source_uri=source_payload["source_uri"],
                source_hash=source_payload["source_hash"],
                duration=source_payload["duration"],
                asr_engine=self.options.asr_engine,
                vlm_model=self.options.vlm_model or Config.VLM_MODEL_NAME,
                metadata=source_payload.get("metadata", {}),
                keyframes=source_payload.get("keyframes", []),
            )
            source_index.replace_segments(source_record["id"], source_payload["segments"])
            source_index.replace_concept_mentions(source_record, extracted_concepts)
            source_index.write_source_note(source_record, source_payload["segments"], extracted_concepts)

            self.progress(f"成功提取 {len(extracted_concepts)} 个概念，开始合并织网...", 85)
            if not extracted_concepts:
                self.progress(f"未从 {source_payload['source_name']} 中提取到有效概念，已写入来源页。", 90)
                continue

            for idx, concept_item in enumerate(extracted_concepts):
                concept_name = concept_item["concept"]
                self.progress(f"合并 Wiki 页面: {concept_name}...", 85 + int((idx / len(extracted_concepts)) * 10))

                merged_md = llm_core.merge_and_write_wiki(concept_item, source_payload["source_name"])
                result.written_notes += 1

                self.progress(f"执行事实一致性核对 -> {concept_name} ...", 95)
                check_result = fact_checker.check_consistency(structured_source, merged_md)
                self._write_fact_check_result(concept_name, check_result)
                source_index.update_concept_source_frontmatter(concept_name, source_record)

        self.progress(">>> Crucible AI 工作流成功执行完毕！", 100)
        return result

    def _load_source(self, source: str) -> Dict:
        is_url = source.startswith(("http://", "https://"))
        if not is_url and not os.path.exists(source):
            self.progress(f"源文件不存在，已跳过: {source}", 0)
            return {}

        if is_url:
            self.progress("正在解析在线视频标题...", 12)
            source_name = f"[视频]{audio_processor.get_video_title(source)}"
            source_ext = ".m4a"
            source_type = "url"
            self.progress(f"开始处理在线视频: {source_name}", 15)
        else:
            source_name = os.path.basename(source)
            source_ext = os.path.splitext(source_name)[1].lower()
            if source_ext in Config.SUPPORTED_VIDEO_FORMATS:
                source_type = "video"
            elif source_ext in Config.SUPPORTED_AUDIO_FORMATS:
                source_type = "audio"
            else:
                source_type = "document"
            self.progress(f"开始处理源文件: {source_name}", 10)

        source_hash = self._source_hash(source, is_url)
        segments = []
        duration = 0.0
        metadata = self._build_source_metadata(source, source_ext, source_type, is_url)
        keyframes = []
        if source_ext in Config.SUPPORTED_VIDEO_FORMATS or source_ext in Config.SUPPORTED_AUDIO_FORMATS:
            structured_source, segments, duration, keyframes = self._process_media_source(source, source_ext, is_url, source_hash)
            metadata["duration"] = duration
        elif source_ext in Config.SUPPORTED_DOC_FORMATS:
            self.progress("第一步: 解析并读取文档文本...", 30)
            structured_source = doc_parser.parse_file(source)
            segments = [{"start": 0.0, "end": 0.0, "text": structured_source[:4000]}]
        else:
            self.progress(f"不支持的文件格式: {source_name}", 0)
            return {}

        return {
            "source_name": source_name,
            "source_ext": source_ext,
            "source_type": source_type,
            "source_uri": source,
            "source_hash": source_hash,
            "duration": duration,
            "metadata": metadata,
            "keyframes": keyframes,
            "segments": segments,
            "structured_source": self._prepend_source_metadata(
                source=source,
                source_name=source_name,
                source_ext=source_ext,
                source_type=source_type,
                source_hash=source_hash,
                duration=duration,
                metadata=metadata,
                segments=segments,
                content=structured_source,
                is_url=is_url,
            ),
        }

    def _process_media_source(self, source: str, source_ext: str, is_url: bool, source_hash: str) -> tuple:
        self.progress("第一步: 音频分离与重采样中...", 20)
        wav_path = audio_processor.process_media(source, Config.TEMP_DIR)
        duration = audio_processor.get_audio_duration(wav_path)

        self.progress("第二步: ASR 转写语音文本中...", 40)
        transcriber = WhisperTranscriber(engine=self.options.asr_engine)
        segments = transcriber.transcribe(wav_path, language=self.options.whisper_lang)
        full_source_text = "\n".join(self._format_segment_line(seg) for seg in segments if seg.get("text"))

        structured_source = "【视频声音转写内容】:\n" + full_source_text + "\n\n"
        keyframes = []
        if not is_url and source_ext in Config.SUPPORTED_VIDEO_FORMATS:
            self.progress("第三步: 抽取视频关键帧并执行 VLM 分析 (OCR + 描述)...", 60)
            ts_list = [round(duration * 0.1, 2), round(duration * 0.5, 2), round(duration * 0.9, 2)]
            vlm_contexts = vlm_analyzer.analyze_video(source, ts_list)
            keyframes = self._save_keyframes(source, source_hash, ts_list, vlm_contexts)
            if vlm_contexts:
                structured_source += "【视频画面抽帧分析】:\n"
                for ts, ctx in vlm_contexts.items():
                    structured_source += f"- 在 {ts}s 画面:\n  OCR 文字: {ctx['ocr']}\n  画面描述: {ctx['description']}\n"

        return structured_source, segments, duration, keyframes

    def _build_source_metadata(self, source: str, source_ext: str, source_type: str, is_url: bool) -> Dict:
        metadata = {
            "source_ext": source_ext,
            "source_type": source_type,
            "source_uri": source,
            "is_url": is_url,
        }
        if not is_url and os.path.exists(source):
            metadata["file_size"] = os.path.getsize(source)
            if source_ext in Config.SUPPORTED_VIDEO_FORMATS:
                metadata.update(video_processor.get_video_metadata(source))
            elif source_ext in Config.SUPPORTED_AUDIO_FORMATS:
                metadata.update({
                    "resolution": "",
                    "fps": None,
                    "audio_streams": 1,
                    "subtitle_streams": 0,
                })
            else:
                metadata.update({
                    "resolution": "",
                    "fps": None,
                    "audio_streams": 0,
                    "subtitle_streams": 0,
                })
        return metadata

    def _save_keyframes(self, source: str, source_hash: str, timestamps: List[float], vlm_contexts: Dict[float, Dict]) -> List[Dict]:
        keyframes = []
        folder = os.path.join(Config.OBSIDIAN_VAULT_PATH, "Attachments", "keyframes", source_hash[:16])
        for timestamp in timestamps:
            label = self._format_timestamp(timestamp).replace(":", "-")
            filename = f"{label}.jpg"
            output_path = os.path.join(folder, filename)
            frame = video_processor.extract_frame_at_time(source, timestamp)
            saved = frame is not None and video_processor.save_frame_jpeg(frame, output_path)
            context = vlm_contexts.get(timestamp, {})
            if not saved:
                continue
            keyframes.append({
                "timestamp": timestamp,
                "timestamp_label": self._format_timestamp(timestamp),
                "filename": filename,
                "attachment_rel_path": fs_router.get_relative_path(output_path),
                "ocr": context.get("ocr", "无"),
                "description": context.get("description", ""),
            })
        return keyframes

    def _format_timestamp(self, seconds: float) -> str:
        total = max(0, int(seconds or 0))
        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"

    def _prepend_source_metadata(
        self,
        source: str,
        source_name: str,
        source_ext: str,
        source_type: str,
        source_hash: str,
        duration: float,
        metadata: Dict,
        segments: List[Dict],
        content: str,
        is_url: bool,
    ) -> str:
        metadata_lines = [
            "【来源元数据】",
            f"source_name: {source_name}",
            f"source_type: {source_type}",
            f"source_ext: {source_ext or 'url'}",
            f"source: {source}",
            f"source_hash_sha256: {source_hash}",
            f"duration_seconds: {round(float(duration or 0.0), 2)}",
            f"duration_label: {self._format_timestamp(duration)}",
            f"is_url: {str(is_url).lower()}",
        ]
        if not is_url:
            metadata_lines.append(f"file_size: {metadata.get('file_size', 0)}")

        for key in ("resolution", "width", "height", "fps", "audio_streams", "subtitle_streams"):
            value = metadata.get(key)
            if value not in (None, ""):
                metadata_lines.append(f"{key}: {value}")

        segment_lines = [
            "【来源时间戳片段】",
        ]
        for segment in segments:
            text = (segment.get("text") or "").strip()
            if not text:
                continue
            segment_lines.append(f"- {self._format_segment_line(segment)}")
        if len(segment_lines) == 1:
            segment_lines.append("- 暂无可用片段")

        return "\n".join(metadata_lines) + "\n\n" + "\n".join(segment_lines) + "\n\n" + content

    def _format_segment_line(self, segment: Dict) -> str:
        text = (segment.get("text") or "").strip()
        start = self._format_timestamp(segment.get("start"))
        end = self._format_timestamp(segment.get("end"))
        return f"{start} - {end}: {text}"

    def _source_hash(self, source: str, is_url: bool) -> str:
        if is_url:
            return hashlib.sha256(source.encode("utf-8")).hexdigest()
        return self._hash_file(source)

    def _hash_file(self, file_path: str) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _write_fact_check_result(self, concept_name: str, check_result: Dict) -> None:
        file_path = fs_router.locate_concept_file(concept_name)
        if not file_path or not os.path.exists(file_path):
            return

        content = wiki_editor.read_wiki(file_path)
        updated_content = wiki_editor.update_frontmatter_fields(
            content,
            {
                "qe_score": check_result.get("score", 0),
                "qe_consistent": str(check_result.get("consistent", False)).lower(),
            },
        )
        wiki_editor.write_wiki_atomic(file_path, updated_content)
