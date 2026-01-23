# -*- coding: utf-8 -*-
"""
视频处理工具类 - 修正版
封装 OpenCV 操作，提供统一的读取和属性获取接口
"""
import cv2
import os
from pathlib import Path
from typing import Tuple, Optional
import numpy as np

class VideoProcessor:
    def __init__(self, video_path: str):
        """
        初始化视频处理器
        :param video_path: 视频文件路径
        """
        self.video_path = str(video_path)
        if not os.path.exists(self.video_path):
            raise FileNotFoundError(f"Video file not found: {self.video_path}")
            
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            raise ValueError(f"Failed to open video: {self.video_path}")

    def get_duration(self) -> float:
        """获取视频时长（秒）"""
        fps = self.get_fps()
        if fps <= 0:
            return 0.0
        frame_count = self.get_frame_count()
        return frame_count / fps

    def get_fps(self) -> float:
        """获取帧率"""
        return self.cap.get(cv2.CAP_PROP_FPS)

    def get_frame_count(self) -> int:
        """获取总帧数"""
        return int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

    def get_frame(self, frame_index: int) -> Optional[np.ndarray]:
        """
        获取指定索引的帧
        """
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = self.cap.read()
        if ret:
            return frame
        return None

    def release(self):
        """释放资源"""
        if self.cap:
            self.cap.release()

def validate_video(file_path: str, max_duration: int = 30, max_size_mb: int = 100) -> Tuple[bool, str]:
    """
    静态验证函数：检查视频是否符合上传规范
    """
    path = Path(file_path)
    
    # 1. 检查大小
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        return False, f"File size too large ({size_mb:.1f}MB > {max_size_mb}MB)"
        
    # 2. 检查时长 (使用 OpenCV)
    try:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return False, "Invalid video format or corrupted file"
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = frame_count / fps if fps > 0 else 0
        cap.release()
        
        if duration > max_duration + 2: # 允许2秒误差
            return False, f"Video too long ({duration:.1f}s > {max_duration}s)"
            
        return True, ""
    except Exception as e:
        return False, f"Validation error: {str(e)}"