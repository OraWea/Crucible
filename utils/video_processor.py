import cv2
import os
import logging
import numpy as np
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

# 实例化单例
video_processor = VideoProcessor()
