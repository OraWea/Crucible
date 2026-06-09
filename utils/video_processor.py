import cv2
import json
import os
import logging
import numpy as np
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self):
        logger.info("VideoProcessor initialized.")

    def extract_frame_at_time(self, video_path: str, timestamp: float) -> Optional[np.ndarray]:
        """
        从视频的指定时间戳（秒）提取一帧（RGB 格式）
        
        Args:
            video_path: 视频文件路径
            timestamp: 目标时间戳 (秒)
            
        Returns:
            RGB 格式的 numpy array，提取失败返回 None
        """
        if not video_path or not os.path.exists(video_path):
            logger.error(f"视频文件不存在: {video_path}")
            return None

        cap = None
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"视频无法打开: {video_path}。请检查编解码器和 FFmpeg 路径。")
                return None

            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = total_frames / fps if fps > 0 else 0

            # 校验时间范围
            if timestamp < 0 or timestamp > duration:
                logger.warning(f"指定时间戳 {timestamp}s 超出视频范围 (0 - {duration:.2f}s)。回退到中间帧。")
                timestamp = max(0.0, duration / 2.0)

            # 定位并读取帧
            frame_idx = int(timestamp * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            
            if not ret or frame is None:
                logger.error(f"在 {timestamp:.2f}s (帧索引 {frame_idx}) 读取关键帧失败。")
                return None

            # OpenCV 读取的默认为 BGR，需转换为 RGB 以供 VLM 大模型读取
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            logger.info(f"成功提取视频帧: {video_path} 在 {timestamp:.2f}s (索引 {frame_idx})")
            return rgb_frame

        except Exception as e:
            logger.error(f"视频帧提取失败: {e}", exc_info=True)
            return None
        finally:
            if cap is not None:
                cap.release()

    def get_video_metadata(self, video_path: str) -> dict:
        """读取视频流元数据；优先 ffprobe，失败时回退 OpenCV。"""
        metadata = {
            "resolution": "",
            "width": None,
            "height": None,
            "fps": None,
            "audio_streams": 0,
            "subtitle_streams": 0,
        }
        if not video_path or not os.path.exists(video_path):
            return metadata

        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_streams",
                    "-show_format",
                    "-of",
                    "json",
                    video_path,
                ],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                streams = data.get("streams", [])
                video_stream = next((item for item in streams if item.get("codec_type") == "video"), None)
                if video_stream:
                    width = video_stream.get("width")
                    height = video_stream.get("height")
                    metadata["width"] = width
                    metadata["height"] = height
                    metadata["resolution"] = f"{width}x{height}" if width and height else ""
                    metadata["fps"] = self._parse_rate(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate"))
                metadata["audio_streams"] = len([item for item in streams if item.get("codec_type") == "audio"])
                metadata["subtitle_streams"] = len([item for item in streams if item.get("codec_type") == "subtitle"])
                if data.get("format", {}).get("duration"):
                    metadata["duration"] = float(data["format"]["duration"])
                return metadata
        except Exception as e:
            logger.warning(f"ffprobe 读取视频元数据失败，回退 OpenCV: {video_path}, {e}")

        cap = None
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return metadata
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            metadata["width"] = width or None
            metadata["height"] = height or None
            metadata["resolution"] = f"{width}x{height}" if width and height else ""
            metadata["fps"] = round(float(fps), 3) if fps else None
        except Exception as e:
            logger.warning(f"OpenCV 读取视频元数据失败: {video_path}, {e}")
        finally:
            if cap is not None:
                cap.release()
        return metadata

    def save_frame_jpeg(self, frame: np.ndarray, output_path: str) -> bool:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return bool(cv2.imwrite(output_path, bgr_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88]))
        except Exception as e:
            logger.error(f"保存关键帧失败: {output_path}, {e}")
            return False

    def _parse_rate(self, value: str):
        if not value or value == "0/0":
            return None
        if "/" not in value:
            try:
                return round(float(value), 3)
            except ValueError:
                return None
        numerator, denominator = value.split("/", 1)
        try:
            denominator_value = float(denominator)
            if denominator_value == 0:
                return None
            return round(float(numerator) / denominator_value, 3)
        except ValueError:
            return None

# 实例化单例
video_processor = VideoProcessor()
