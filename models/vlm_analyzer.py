import os
import cv2
import logging
import torch
import base64
import time
import requests
from typing import Dict, Any, List, Optional
from PIL import Image
import numpy as np
from Crucible.config import Config
from Crucible.utils.video_processor import video_processor
from Crucible.utils.db_manager import db_manager

logger = logging.getLogger(__name__)

class VLMAnalyzer:
    def __init__(self):
        self.model_id = Config.VLM_MODEL_ID
        self.device = "cuda" if Config.VLM_DEVICE == "cuda" and torch.cuda.is_available() else "cpu"
        self.local_model = None
        self.processor = None
        
        # 尝试初始化本地模型，若硬件不支持或失败，则自动启用 API 模式
        self.use_api = True
        if Config.LLM_API_KEY == 'your-api-key' or not Config.LLM_API_KEY:
            self.use_api = False
            
        if not self.use_api:
            self._init_local_model()

    def _init_local_model(self):
        """加载本地 Qwen-VL 视觉大模型"""
        try:
            logger.info(f"正在加载本地 VLM 模型: {self.model_id} (设备: {self.device})")
            db_manager.add_log("INFO", "VLM", "Model_Load_Start", f"加载本地 VLM {self.model_id} 到 {self.device}")
            
            from transformers import AutoProcessor, AutoModelForVision2Seq
            
            self.processor = AutoProcessor.from_pretrained(self.model_id)
            self.local_model = AutoModelForVision2Seq.from_pretrained(
                self.model_id,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map=self.device
            )
            logger.info("本地 VLM 模型加载成功。")
            db_manager.add_log("INFO", "VLM", "Model_Load_Success", "成功加载本地 VLM 模型")
        except Exception as e:
            logger.warning(f"本地 VLM 加载失败 ({e})，系统将自动降级为 API 模式运行。")
            db_manager.add_log("WARNING", "VLM", "Model_Load_Downgrade", f"本地加载失败 ({e})，降级为 API 模式")
            self.use_api = True

    def analyze_video(self, video_path: str, timestamps: List[float]) -> Dict[float, Dict[str, Any]]:
        """
        核心分析入口：对指定时间戳的关键帧进行视觉与 OCR 分析
        
        Args:
            video_path: 本地视频绝对路径
            timestamps: 需要提取关键帧的时间戳列表（秒）
            
        Returns:
            Dict[float, Dict]: 时间戳映射到 {'ocr': str, 'description': str} 的结果字典
        """
        results = {}
        if not os.path.exists(video_path):
            return results

        logger.info(f"开始分析视频关键帧 (共 {len(timestamps)} 个时间点)...")
        db_manager.add_log("INFO", "VLM", "Analyze_Start", f"开始抽帧分析，共 {len(timestamps)} 帧")
        
        start_time = time.time()
        for ts in timestamps:
            # 1. 抽帧
            frame = video_processor.extract_frame_at_time(video_path, ts)
            if frame is None:
                continue
            
            # 2. 推理
            try:
                if self.use_api:
                    ocr_res, desc_res = self._analyze_frame_api(frame)
                else:
                    ocr_res, desc_res = self._analyze_frame_local(frame)
                
                results[ts] = {
                    "ocr": ocr_res,
                    "description": desc_res
                }
                logger.info(f"时间轴 {ts}s 分析完成:\nOCR: {ocr_res[:100]}...\n描述: {desc_res[:100]}...")
            except Exception as e:
                logger.error(f"分析时间点 {ts}s 处的帧失败: {e}")
                db_manager.add_log("ERROR", "VLM", "Frame_Analyze_Failure", f"时间点 {ts}s 错误: {e}")

        duration = time.time() - start_time
        db_manager.add_log("INFO", "VLM", "Analyze_Success", f"抽帧分析完成，成功解析 {len(results)} 帧", duration=duration)
        return results

    def _analyze_frame_api(self, frame: np.ndarray) -> tuple:
        """使用 OpenAI 兼容的多模态 API 接口进行在线推理"""
        # 将 opencv 的 RGB 帧转为 jpg 二进制数据并做 base64 编码
        _, buffer = cv2.imencode('.jpg', cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        base64_image = base64.b64encode(buffer).decode('utf-8')
        
        # 针对阿里云 DashScope qwen-vl-max/plus 进行模型名称适配，
        # 如果用户配了别的平台，可自行在 .env 中覆盖
        model_name = Config.LLM_MODEL_NAME
        if "dashscope" in Config.LLM_API_BASE:
            model_name = "qwen-vl-plus" # 默认选用 Qwen-VL 专业版 API
            
        headers = {
            "Authorization": f"Bearer {Config.LLM_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # 多模态 payload
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "请分析这张视频画面。你的任务必须分为两部分：\n"
                                    "1. [OCR]: 提取画面中可见的所有文字、代码块、或数学公式（公式必须使用 LaTeX 格式输出，代码必须用标准 markdown 代码块包裹）。若无文字，则输出'无'。\n"
                                    "2. [DESCRIPTION]: 详细描述画面的场景、主要物体、演示内容及发生的动作。\n"
                                    "请严格按照 'OCR: [提取内容]\nDESCRIPTION: [描述内容]' 的格式回答。"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.1
        }
        
        response = requests.post(Config.LLM_API_BASE + "/chat/completions", json=payload, headers=headers, timeout=30)
        
        if response.status_code != 200:
            raise RuntimeError(f"VLM API 请求失败 ({response.status_code}): {response.text}")
            
        resp_json = response.json()
        content = resp_json['choices'][0]['message']['content'].strip()
        
        return self._parse_vlm_output(content)

    def _analyze_frame_local(self, frame: np.ndarray) -> tuple:
        """使用本地模型进行 Vision 推理"""
        pil_image = Image.fromarray(frame)
        prompt = ("OCR: Extract all text, code blocks, or LaTeX formulas on the screen.\n"
                  "DESCRIPTION: Describe the scene activity and objects.")
                  
        # 针对本地 Qwen2-VL 或 LLaVA pipeline 构造输入
        inputs = self.processor(
            text=[prompt],
            images=[pil_image],
            padding=True,
            return_tensors="pt"
        ).to(self.device)
        
        with torch.no_grad():
            generated_ids = self.local_model.generate(**inputs, max_new_tokens=250)
            
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = self.processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]
        
        return self._parse_vlm_output(output_text)

    def _parse_vlm_output(self, raw_text: str) -> tuple:
        """解析 VLM 输出内容，拆分为 OCR 和 描述"""
        ocr = "无"
        description = "未检测到详细视觉描述。"
        
        try:
            # 使用正则拆分
            if "OCR:" in raw_text and "DESCRIPTION:" in raw_text:
                parts = raw_text.split("DESCRIPTION:")
                ocr = parts[0].replace("OCR:", "").strip()
                description = parts[1].strip()
            elif "ocr:" in raw_text.lower() and "description:" in raw_text.lower():
                # 兼容大小写
                lower_text = raw_text.lower()
                idx_ocr = lower_text.find("ocr:")
                idx_desc = lower_text.find("description:")
                if idx_ocr < idx_desc:
                    ocr = raw_text[idx_ocr + 4 : idx_desc].strip()
                    description = raw_text[idx_desc + 12 :].strip()
                else:
                    description = raw_text[idx_desc + 12 : idx_ocr].strip()
                    ocr = raw_text[idx_ocr + 4 :].strip()
            else:
                # 默认保底
                description = raw_text
        except Exception:
            description = raw_text
            
        return ocr, description

# 实例化单例
vlm_analyzer = VLMAnalyzer()
