import os
import logging
import time
import wave
import threading
from typing import Dict, Any, List
import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult
from Crucible.config import Config
from Crucible.utils.db_manager import db_manager

logger = logging.getLogger(__name__)


class _ASRCollectorCallback(RecognitionCallback):
    """
    内部回调类：收集百炼实时 ASR 流式识别返回的所有完整句子片段。
    每当一个句子被确认结束（is_sentence_end == True），就将其存入 segments 列表。
    """

    def __init__(self):
        self.segments: List[Dict[str, Any]] = []
        self._error: Exception = None
        self._done_event = threading.Event()
        self._started = False

    def on_open(self) -> None:
        logger.info("百炼实时 ASR 连接已建立。")
        self._started = True

    def on_event(self, result: RecognitionResult) -> None:
        sentence = result.get_sentence()
        if sentence and RecognitionResult.is_sentence_end(sentence):
            text = sentence.get("text", "").strip()
            if text:
                begin_ms = sentence.get("begin_time", 0) or 0
                end_ms = sentence.get("end_time", 0) or 0
                self.segments.append({
                    "start": round(begin_ms / 1000.0, 2),
                    "end": round(end_ms / 1000.0, 2),
                    "text": text
                })
                logger.debug(f"ASR 识别到句子: [{begin_ms/1000.0:.2f}s-{end_ms/1000.0:.2f}s] {text}")

    def on_close(self) -> None:
        logger.info("百炼实时 ASR 连接已关闭。")
        self._done_event.set()

    def on_error(self, error) -> None:
        try:
            err_str = str(error)
        except Exception:
            err_str = "未知 ASR 回调错误"
        logger.error(f"百炼实时 ASR 回调报错: {err_str}")
        self._error = RuntimeError(err_str)
        self._done_event.set()

    @property
    def is_connected(self) -> bool:
        return self._started and not self._done_event.is_set()

    def wait_until_done(self, timeout: float = 600.0) -> None:
        """阻塞等待识别流程完成或超时"""
        completed = self._done_event.wait(timeout=timeout)
        if not completed:
            raise TimeoutError(f"ASR 识别等待超时（{timeout}s）")
        if self._error:
            raise self._error


class WhisperTranscriber:
    def __init__(self, model_name: str = Config.WHISPER_MODEL_NAME, device: str = Config.WHISPER_DEVICE, engine: str = 'dashscope'):
        self.model_name = model_name
        self.device = device
        self.engine = self._resolve_engine(engine)
        self.local_model = None
        # 设置 dashscope API key
        if self.engine == 'dashscope':
            dashscope.api_key = Config.LLM_API_KEY
        self.load_model()

    def _resolve_engine(self, engine: str) -> str:
        normalized = (engine or 'dashscope').strip().lower()
        if normalized not in {'dashscope', 'local'}:
            logger.warning(f"未知 ASR 引擎 '{engine}'，自动回退为本地 Whisper。")
            return 'local'
        if normalized == 'dashscope' and not Config.has_valid_api_key():
            logger.warning("未配置有效 API Key，ASR 自动回退为本地 Whisper。")
            return 'local'
        return normalized

    def load_model(self):
        if self.engine == 'dashscope':
            logger.info("已切换为阿里云百炼实时流式 ASR 服务，无需本地加载大模型。")
            db_manager.add_log("INFO", "ASR", "Model_Load_Success", "使用百炼云端实时流式 ASR 识别服务")
        else:
            # 自动检测 CUDA 可用性，不可用时回退到 CPU
            try:
                import torch
                if self.device == 'cuda' and not torch.cuda.is_available():
                    logger.warning("配置为 CUDA 但未检测到可用 GPU，自动回退至 CPU。")
                    self.device = 'cpu'
            except ImportError:
                self.device = 'cpu'
            logger.info(f"正在加载本地 Whisper 模型 '{self.model_name}' (设备: {self.device})...")
            try:
                import whisper
                self.local_model = whisper.load_model(self.model_name, device=self.device)
                logger.info("本地 Whisper 模型加载成功。")
                db_manager.add_log("INFO", "ASR", "Model_Load_Success", f"本地 Whisper 模型加载成功: {self.model_name}")
            except ImportError:
                logger.error("缺少 'whisper' 库，请使用 pip install openai-whisper 安装。")
                raise RuntimeError("未安装 openai-whisper 库。")
            except Exception as e:
                logger.error(f"加载本地 Whisper 模型失败: {e}")
                raise

    def transcribe(self, audio_path: str, language: str = "auto") -> List[Dict[str, Any]]:
        """
        使用选择的 ASR 引擎对本地音频文件进行转写，输出带精准时间戳的片段列表。
        
        Args:
            audio_path: 本地已转换的 WAV 音频路径
            language: 语言代码 (如 'zh', 'en', 'auto')
            
        Returns:
            List[Dict]: 每个元素包含 'start', 'end', 'text' 键的字典列表
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"未找到音频转录输入文件: {audio_path}")

        if self.engine == 'dashscope':
            return self._transcribe_dashscope(audio_path, language)
        else:
            return self._transcribe_local(audio_path, language)

    def _transcribe_local(self, audio_path: str, language: str) -> List[Dict[str, Any]]:
        try:
            start_time = time.time()
            logger.info(f"开始本地 Whisper ASR 任务: {audio_path}")
            db_manager.add_log("INFO", "ASR", "Transcribe_Start", f"开始处理音频(本地): {os.path.basename(audio_path)}")

            if self.local_model is None:
                raise RuntimeError("本地 Whisper 模型尚未加载。")

            lang = None if language == "auto" else language
            result = self.local_model.transcribe(audio_path, language=lang)

            processed_segments = []
            for seg in result.get("segments", []):
                processed_segments.append({
                    "start": round(seg["start"], 2),
                    "end": round(seg["end"], 2),
                    "text": seg["text"].strip()
                })

            duration = time.time() - start_time
            logger.info(f"本地 Whisper ASR 识别完成，共生成 {len(processed_segments)} 个片段，用时 {duration:.2f}s")
            db_manager.add_log("INFO", "ASR", "Transcribe_Success",
                               f"本地 ASR 转写成功，产生 {len(processed_segments)} 个文本片段",
                               duration=duration)
            return processed_segments
        except Exception as e:
            logger.error(f"本地 Whisper ASR 识别失败: {e}", exc_info=True)
            db_manager.add_log("ERROR", "ASR", "Transcribe_Failure", str(e))
            raise

    def _transcribe_dashscope(self, audio_path: str, language: str) -> List[Dict[str, Any]]:
        try:
            start_time = time.time()
            logger.info(f"开始百炼实时流式 ASR 任务: {audio_path}")
            db_manager.add_log("INFO", "ASR", "Transcribe_Start", f"开始处理音频: {os.path.basename(audio_path)}")

            # 1. 确保 API Key 在调用前最新
            if not Config.has_valid_api_key():
                raise RuntimeError("未配置有效 API Key，无法使用百炼实时 ASR。")
            dashscope.api_key = Config.LLM_API_KEY

            # 2. 映射模型名称：将旧 Whisper 名称映射为百炼实时模型
            model = self.model_name
            if model in ["tiny", "base", "small", "medium", "large", "turbo", "paraformer-v2"]:
                model = "paraformer-realtime-v2"

            # 3. 读取 WAV 文件的元信息
            with wave.open(audio_path, 'rb') as wf:
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                n_frames = wf.getnframes()
                if sample_rate <= 0:
                    raise ValueError(f"非法音频采样率: {sample_rate}")
                audio_duration = n_frames / sample_rate
            
            logger.info(f"音频参数: {sample_rate}Hz, {channels}ch, {sampwidth*8}bit, 时长 {audio_duration:.1f}s")
            logger.info(f"正在启动百炼实时 ASR，使用模型: {model}")

            # 4. 构造回调收集器
            callback = _ASRCollectorCallback()

            # 5. 初始化 Recognition 实例，使用 pcm 格式（发送裸 PCM 数据不含文件头）
            recognition = Recognition(
                model=model,
                format='pcm',
                sample_rate=sample_rate,
                callback=callback
            )
            recognition.start()

            # 等待连接建立（最多等 10 秒）
            wait_start = time.time()
            while not callback._started and (time.time() - wait_start) < 10.0:
                if callback._done_event.is_set():
                    if callback._error:
                        raise callback._error
                    raise RuntimeError("百炼 ASR 连接未能建立，请检查 API Key 是否正确配置。")
                time.sleep(0.1)

            if not callback._started:
                raise RuntimeError("百炼 ASR 连接超时（10 秒），请检查网络连接和 API Key。")

            # 6. 使用 wave 模块读取纯 PCM 数据（跳过 WAV 文件头），分块流式发送
            #    每次发送 100ms 的数据：16000Hz * 2bytes * 1ch * 0.1s = 3200 bytes
            bytes_per_second = sample_rate * sampwidth * channels
            chunk_duration_ms = 100  # 每块 100ms
            chunk_size = int(bytes_per_second * chunk_duration_ms / 1000)
            sleep_time = chunk_duration_ms / 1000.0 * 0.5  # 发送速度约为实时的 2 倍

            logger.info(f"开始流式发送 PCM 数据，每块 {chunk_size} bytes ({chunk_duration_ms}ms)，总计约 {n_frames * sampwidth / chunk_size:.0f} 块")

            with wave.open(audio_path, 'rb') as wf:
                frames_per_chunk = chunk_size // (sampwidth * channels)
                while True:
                    pcm_data = wf.readframes(frames_per_chunk)
                    if not pcm_data:
                        break
                    if not callback.is_connected:
                        logger.warning("ASR 连接已断开，提前终止音频发送。")
                        break
                    recognition.send_audio_frame(pcm_data)
                    time.sleep(sleep_time)

            # 7. 通知服务端音频发送结束
            try:
                recognition.stop()
            except Exception as stop_err:
                logger.warning(f"停止 ASR 时出现异常（可忽略）: {stop_err}")

            # 8. 等待所有回调执行完毕
            callback.wait_until_done(timeout=600.0)

            processed_segments = callback.segments
            duration = time.time() - start_time
            logger.info(f"百炼实时 ASR 识别完成，共生成 {len(processed_segments)} 个片段，用时 {duration:.2f}s")
            db_manager.add_log("INFO", "ASR", "Transcribe_Success",
                               f"百炼实时 ASR 转写成功，产生 {len(processed_segments)} 个文本片段",
                               duration=duration)

            return processed_segments

        except Exception as e:
            logger.error(f"百炼实时 ASR 识别失败: {e}", exc_info=True)
            db_manager.add_log("ERROR", "ASR", "Transcribe_Failure", str(e))
            raise
