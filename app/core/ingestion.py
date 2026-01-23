# -*- coding: utf-8 -*-
"""
视频摄取管道
负责视频上传、验证、Hash 计算、B 流存储
"""
from pathlib import Path
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from tempfile import NamedTemporaryFile

from app.models.database import BRawVideo, ASession
from app.utils.hash import calculate_file_hash
from app.utils.video import validate_video
from app.services.storage import storage_service
from app.config import settings


class VideoIngestionError(Exception):
    """视频摄取异常"""
    pass


class VideoIngestionService:
    """视频摄取服务"""

    def __init__(self, db: Session):
        """
        初始化摄取服务

        Args:
            db: 数据库会话
        """
        self.db = db

    def ingest_video(
        self,
        video_file_data: bytes,
        user_id: str,
        session_type: str,
        zone_id: Optional[int] = None,
        user_description: Optional[str] = None
    ) -> Tuple[BRawVideo, ASession]:
        """
        完整的视频摄取流程

        Args:
            video_file_data: 视频文件二进制数据
            user_id: 用户ID
            session_type: Session 类型（quick_check 或 baseline）
            zone_id: 区域ID（1-7，仅 baseline 需要）
            user_description: 用户文本描述（可选）

        Returns:
            (BRawVideo, ASession) 元组

        Raises:
            VideoIngestionError: 摄取过程出错

        流程：
        1. 验证视频文件
        2. 计算 Hash 去重
        3. 存储到 B 流
        4. 创建 B 流数据库记录
        5. 创建 A 流 Session 记录
        """
        print(f"[摄取] 开始摄取视频: user_id={user_id}, type={session_type}")

        # 第一步：验证 Session 类型
        if session_type not in ["quick_check", "baseline"]:
            raise VideoIngestionError(f"无效的 Session 类型: {session_type}")

        # 第二步：验证 Zone ID
        if session_type == "baseline":
            if zone_id is None or not (1 <= zone_id <= 7):
                raise VideoIngestionError(f"Baseline 模式需要提供有效的 zone_id (1-7), 当前: {zone_id}")
        else:
            zone_id = None  # quick_check 不需要 zone_id

        # 第三步：将数据写入临时文件进行验证
        with NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
            temp_file.write(video_file_data)
            temp_path = temp_file.name

        try:
            # 第四步：验证视频文件
            is_valid, error_message = validate_video(
                temp_path,
                max_duration=settings.MAX_VIDEO_DURATION,
                max_size_mb=settings.MAX_VIDEO_SIZE_MB
            )

            if not is_valid:
                raise VideoIngestionError(f"视频验证失败: {error_message}")

            print(f"[摄取] 视频验证通过")

            # 第五步：计算 Hash
            file_hash = calculate_file_hash(temp_path, algorithm="sha256")
            print(f"[摄取] Hash 计算完成: {file_hash[:16]}...")

            # 第六步：检查去重（B 流数据库）
            existing_b_video = self.db.query(BRawVideo).filter_by(file_hash=file_hash).first()

            if existing_b_video:
                print(f"[摄取] 检测到重复视频，复用已有 B 流记录: {existing_b_video.id}")
                b_video = existing_b_video
            else:
                # 第七步：存储到 B 流（物理文件）
                b_stream_path = storage_service.save_to_b_stream(
                    source_path=temp_path,
                    user_id=user_id,
                    file_hash=file_hash,
                    extension=".mp4"
                )

                # 第八步：创建 B 流数据库记录
                file_size_bytes = Path(temp_path).stat().st_size

                b_video = BRawVideo(
                    user_id=user_id,
                    file_hash=file_hash,
                    file_path=str(b_stream_path),
                    file_size_bytes=file_size_bytes,
                    session_type=session_type,
                    zone_id=zone_id,
                    user_text_description=user_description,
                    is_locked=True  # 强制锁定
                )

                self.db.add(b_video)
                self.db.commit()
                self.db.refresh(b_video)

                print(f"[摄取] B 流记录创建成功: {b_video.id}")

            # 第九步：创建 A 流 Session 记录
            a_session = ASession(
                user_id=user_id,
                b_video_id=b_video.id,
                session_type=session_type,
                zone_id=zone_id,
                processing_status="pending"
            )

            self.db.add(a_session)
            self.db.commit()
            self.db.refresh(a_session)

            print(f"[摄取] A 流 Session 创建成功: {a_session.id}")
            print(f"[摄取] 摄取完成！")

            return b_video, a_session

        finally:
            # 清理临时文件
            Path(temp_path).unlink(missing_ok=True)

    def get_video_path_by_session(self, session_id: str) -> Optional[str]:
        """
        根据 Session ID 获取原始视频路径

        Args:
            session_id: Session ID

        Returns:
            视频文件路径或 None
        """
        session = self.db.query(ASession).filter_by(id=session_id).first()
        if not session:
            return None

        b_video = self.db.query(BRawVideo).filter_by(id=session.b_video_id).first()
        return b_video.file_path if b_video else None
