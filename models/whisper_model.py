import whisper
import os
import logging
import torch
from typing import Dict, Any, List
from Crucible.config import Config
from Crucible.utils.db_manager import db_manager

logger = logging.getLogger(__name__)

class WhisperTranscriber:
    def __init__(self, model_name: str = Config.WHISPER_MODEL_NAME, device: str = Config.WHISPER_DEVICE):
        self.model_name = model_name
        self.device = "cuda" if device == "cuda" and torch.cuda.is_available() else "cpu"
        self.model = None
        self.load_model()

    def load_model(self):
        """加载 Whisper 模型"""
        try:
            logger.info(f"正在加载 Whisper ASR 模型: {self.model_name} (设备: {self.device})")
            db_manager.add_log("INFO", "ASR", "Model_Load_Start", f"加载 Whisper {self.model_name} 到 {self.device}")
            
            self.model = whisper.load_model(self.model_name, device=self.device)
            logger.info(f"Whisper {self.model_name} 模型加载成功。")
            db_manager.add_log("INFO", "ASR", "Model_Load_Success", f"成功加载 Whisper {self.model_name}")
        except Exception as e:
            logger.error(f"Whisper 模型加载失败: {e}", exc_info=True)
            db_manager.add_log("ERROR", "ASR", "Model_Load_Failure", str(e))
            raise e

    def transcribe(self, audio_path: str, language: str = "auto") -> List[Dict[str, Any]]:
        """
        对音频文件进行转写，输出带精准时间戳的片段列表
        
        Args:
            audio_path: 本地已转换的 WAV 音频路径
            language: 语言代码 (如 'zh', 'en', 'auto')
            
        Returns:
            List[Dict]: 每个元素包含 'start', 'end', 'text' 键的字典列表
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"未找到音频转录输入文件: {audio_path}")

        try:
            import time
            start_time = time.time()
            logger.info(f"开始 Whisper 转写: {audio_path}")
            db_manager.add_log("INFO", "ASR", "Transcribe_Start", f"开始处理音频: {os.path.basename(audio_path)}")

            # 配置转载选项
            options = {
                "beam_size": 5,
                "fp16": True if self.device == "cuda" else False
            }
            if language and language.lower() != "auto":
                options["language"] = language

            # 运行转录
            result = self.model.transcribe(audio_path, **options)
            
            raw_segments = result.get("segments", [])
            processed_segments = []
            
            # 提炼出干净的字级/句级时间戳格式
            for seg in raw_segments:
                processed_segments.append({
                    "start": round(seg["start"], 2),
                    "end": round(seg["end"], 2),
                    "text": seg["text"].strip()
                })

            duration = time.time() - start_time
            logger.info(f"Whisper 转写完成，共生成 {len(processed_segments)} 个片段，用时 {duration:.2f}s")
            db_manager.add_log("INFO", "ASR", "Transcribe_Success", 
                               f"转写成功，产生 {len(processed_segments)} 个文本片段", 
                               duration=duration)
            
            return processed_segments

        except Exception as e:
            logger.error(f"Whisper 转录失败: {e}", exc_info=True)
            db_manager.add_log("ERROR", "ASR", "Transcribe_Failure", str(e))
            raise e
