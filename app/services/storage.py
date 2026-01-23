# -*- coding: utf-8 -*-
"""
本地存储服务 - 修正版
管理 A/B/C 三层数据流的物理存储
"""
import os
import shutil
from pathlib import Path
from typing import Union
import cv2
import numpy as np

from app.config import settings

class StorageService:
    def __init__(self):
        self.root = settings.DATA_ROOT_PATH
                
        self.b_stream = self.root / "b_stream"
        self.a_stream = self.root / "a_stream" 
        self.c_stream = self.root / "c_stream"
        
        # 确保目录结构存在
        self._ensure_dirs()

    def _ensure_dirs(self):
        for p in [self.b_stream, self.a_stream, self.c_stream]:
            p.mkdir(parents=True, exist_ok=True)

    def save_to_b_stream(self, source_path: str, user_id: str, file_hash: str) -> Path:
        """
        保存原始视频到 B 流 (Write-once)
        结构: data/b_stream/{user_id}/{hash}.mp4
        """
        user_dir = self.b_stream / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # 统一使用 mp4 后缀 (V1简化)
        target_path = user_dir / f"{file_hash}.mp4"
        
        if not target_path.exists():
            shutil.copy2(source_path, target_path)
            # 设置为只读 (Linux/Mac)
            try:
                os.chmod(target_path, 0o444)
            except:
                pass
                
        return target_path

    def save_keyframe(self, session_id: str, filename: str, image_data: np.ndarray) -> Path:
        """
        保存关键帧到 A 流
        结构: data/a_stream/{session_id}/keyframes/{filename}
        """
        # 1. 构造路径
        session_dir = self.a_stream / str(session_id) / "keyframes"
        session_dir.mkdir(parents=True, exist_ok=True)
        
        target_path = session_dir / filename
        
        # 2. 保存图片 (使用 OpenCV)
        # 确保目录存在
        if not cv2.imwrite(str(target_path), image_data):
            raise IOError(f"Failed to save image to {target_path}")
            
        return target_path

    def get_keyframe_path(self, session_id: str, filename: str) -> Path:
        """获取关键帧绝对路径"""
        return self.a_stream / str(session_id) / "keyframes" / filename

    def create_c_stream_snapshot(self, b_video_path: Path, experiment_id: str) -> Path:
        """
        从 B 流复制数据到 C 流 (用于训练实验)
        """
        target_dir = self.c_stream / experiment_id
        target_dir.mkdir(parents=True, exist_ok=True)
        
        target_path = target_dir / b_video_path.name
        shutil.copy2(b_video_path, target_path)
        return target_path

# 单例模式
storage_service = StorageService()