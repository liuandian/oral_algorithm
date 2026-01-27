# -*- coding: utf-8 -*-
"""
视频摄取管道
"""
from pathlib import Path
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.database import BRawVideo, ASession
from app.utils.hash import calculate_file_hash
from app.utils.video import validate_video
from app.services.storage import storage_service
from app.config import settings

class VideoIngestionService:
    def __init__(self, db: Session):
        self.db = db

    def ingest_video(
        self,
        video_file_data: Optional[bytes], # 废弃，保留兼容
        temp_file_path: str, # 新增：直接处理临时文件路径
        user_id: str,
        session_type: str,
        zone_id: Optional[int] = None,
        user_description: Optional[str] = None
    ) -> Tuple[BRawVideo, ASession]:
        
        print(f"[摄取] 开始处理: user={user_id}, type={session_type}")
        
        # 1. 基础验证
        if session_type not in ["quick_check", "baseline"]:
            raise ValueError(f"无效 Session 类型: {session_type}")
            
        # 2. 视频物理验证
        is_valid, err = validate_video(
            temp_file_path, 
            max_duration=settings.MAX_VIDEO_DURATION_SEC,
            max_size_mb=settings.MAX_VIDEO_SIZE_MB
        )
        if not is_valid:
            raise ValueError(f"视频验证失败: {err}")

        # 3. 计算 Hash (使用临时文件)
        file_hash = calculate_file_hash(temp_file_path)
        
        # 4. B流处理 (Check or Create)
        b_video = self.db.query(BRawVideo).filter_by(file_hash=file_hash).first()
        
        if not b_video:
            # 存入 B 流
            b_path = storage_service.save_to_b_stream(
                source_path=temp_file_path,
                user_id=user_id,
                file_hash=file_hash
            )
            
            file_size = Path(temp_file_path).stat().st_size
            
            b_video = BRawVideo(
                user_id=user_id,
                file_hash=file_hash,
                file_path=str(b_path),
                file_size_bytes=file_size,
                session_type=session_type,
                zone_id=zone_id,
                user_text_description=user_description,
                is_locked=True
            )
            self.db.add(b_video)
            self.db.commit()
            self.db.refresh(b_video)
            print(f"[摄取] B流归档完成: {b_video.id}")
        else:
            print(f"[摄取] 视频已存在，复用 B流: {b_video.id}")

        # 5. 创建 A 流 Session
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
        
        return b_video, a_session

    def update_session_status(self, session_id: str, status: str, error_msg: str = None):
        """更新 Session 状态的辅助方法"""
        session = self.db.query(ASession).filter_by(id=session_id).first()
        if session:
            session.processing_status = status
            if error_msg:
                session.error_message = error_msg
            if status == "completed":
                session.completed_at = datetime.utcnow()
            self.db.commit()
            print(f"[状态] Session {session_id} -> {status}")