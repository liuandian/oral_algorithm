# -*- coding: utf-8 -*-
"""
文件存储服务
管理 A/B/C 数据流的文件存储
"""
import shutil
from pathlib import Path
from typing import Optional
from app.config import settings


class StorageService:
    """文件存储服务"""

    def __init__(self):
        """初始化存储服务，确保目录存在"""
        self.b_stream_path = settings.B_STREAM_PATH
        self.a_stream_path = settings.A_STREAM_PATH
        self.c_stream_path = settings.C_STREAM_PATH

        # 确保目录存在
        self.b_stream_path.mkdir(parents=True, exist_ok=True)
        self.a_stream_path.mkdir(parents=True, exist_ok=True)
        self.c_stream_path.mkdir(parents=True, exist_ok=True)

    # ========================================
    # B 数据流（原始视频存储）
    # ========================================

    def save_to_b_stream(self, source_path: str, user_id: str, file_hash: str, extension: str = ".mp4") -> Path:
        """
        保存文件到 B 数据流（只读资产库）

        Args:
            source_path: 源文件路径
            user_id: 用户ID
            file_hash: 文件哈希值
            extension: 文件扩展名

        Returns:
            保存后的文件路径

        注意：文件一旦保存将被设为只读
        """
        # 创建用户目录
        user_dir = self.b_stream_path / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        # 文件路径：{user_id}/{file_hash}.mp4
        target_path = user_dir / f"{file_hash}{extension}"

        # 如果文件已存在（去重）
        if target_path.exists():
            print(f"[B流] 文件已存在，跳过存储: {target_path}")
            return target_path

        # 复制文件到 B 流
        shutil.copy2(source_path, target_path)

        # 设置为只读权限（444）
        target_path.chmod(0o444)

        print(f"[B流] 文件保存成功（只读）: {target_path}")
        return target_path

    def get_b_stream_path(self, user_id: str, file_hash: str, extension: str = ".mp4") -> Optional[Path]:
        """
        获取 B 流文件路径

        Args:
            user_id: 用户ID
            file_hash: 文件哈希值
            extension: 文件扩展名

        Returns:
            文件路径或 None
        """
        file_path = self.b_stream_path / user_id / f"{file_hash}{extension}"
        return file_path if file_path.exists() else None

    # ========================================
    # A 数据流（关键帧存储）
    # ========================================

    def save_to_a_stream(self, source_path: str, session_id: str, frame_name: str) -> Path:
        """
        保存关键帧到 A 数据流

        Args:
            source_path: 源文件路径
            session_id: Session ID
            frame_name: 帧文件名（如 frame_001.jpg）

        Returns:
            保存后的文件路径
        """
        # 创建 Session 目录
        session_dir = self.a_stream_path / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # 目标路径
        target_path = session_dir / frame_name

        # 复制文件
        shutil.copy2(source_path, target_path)

        print(f"[A流] 关键帧保存: {target_path}")
        return target_path

    def get_a_stream_session_dir(self, session_id: str) -> Path:
        """
        获取 A 流 Session 目录路径

        Args:
            session_id: Session ID

        Returns:
            Session 目录路径
        """
        session_dir = self.a_stream_path / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def get_a_stream_file_path(self, session_id: str, frame_name: str) -> Optional[Path]:
        """
        获取 A 流文件路径

        Args:
            session_id: Session ID
            frame_name: 帧文件名

        Returns:
            文件路径或 None
        """
        file_path = self.a_stream_path / session_id / frame_name
        return file_path if file_path.exists() else None

    def delete_a_stream_session(self, session_id: str) -> bool:
        """
        删除 A 流 Session 的所有数据

        Args:
            session_id: Session ID

        Returns:
            是否成功

        注意：此操作会删除整个目录
        """
        session_dir = self.a_stream_path / session_id
        if session_dir.exists():
            shutil.rmtree(session_dir)
            print(f"[A流] Session 目录已删除: {session_dir}")
            return True
        return False

    # ========================================
    # C 数据流（训练数据存储，预留）
    # ========================================

    def save_to_c_stream(self, source_path: str, snapshot_id: str, purpose: str = "training") -> Path:
        """
        保存文件到 C 数据流（训练沙盒）

        Args:
            source_path: 源文件路径
            snapshot_id: 快照ID
            purpose: 用途（annotation/augmentation/training）

        Returns:
            保存后的文件路径
        """
        # 创建用途目录
        purpose_dir = self.c_stream_path / purpose
        purpose_dir.mkdir(parents=True, exist_ok=True)

        # 目标路径
        source_file = Path(source_path)
        target_path = purpose_dir / f"{snapshot_id}{source_file.suffix}"

        # 复制文件
        shutil.copy2(source_path, target_path)

        print(f"[C流] 训练数据保存: {target_path}")
        return target_path

    # ========================================
    # 通用工具方法
    # ========================================

    def get_file_size_mb(self, file_path: Path) -> float:
        """
        获取文件大小（MB）

        Args:
            file_path: 文件路径

        Returns:
            文件大小（MB）
        """
        if file_path.exists():
            return file_path.stat().st_size / (1024 * 1024)
        return 0.0

    def list_b_stream_files(self, user_id: str) -> list:
        """
        列出用户的所有 B 流文件

        Args:
            user_id: 用户ID

        Returns:
            文件路径列表
        """
        user_dir = self.b_stream_path / user_id
        if not user_dir.exists():
            return []

        return list(user_dir.glob("*.mp4"))

    def list_a_stream_sessions(self) -> list:
        """
        列出所有 A 流 Session 目录

        Returns:
            Session ID 列表
        """
        if not self.a_stream_path.exists():
            return []

        return [d.name for d in self.a_stream_path.iterdir() if d.is_dir()]


# ========================================
# 全局单例实例
# ========================================
storage_service = StorageService()
