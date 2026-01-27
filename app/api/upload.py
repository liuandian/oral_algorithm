# -*- coding: utf-8 -*-
from fastapi import APIRouter, File, UploadFile, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import shutil
import tempfile
import os
from pathlib import Path

from app.models.database import get_db
from app.models.schemas import UploadResponse
from app.core.ingestion import VideoIngestionService
from app.core.keyframe_extractor import KeyframeExtractor
from app.core.evidence_pack import EvidencePackGenerator
from app.core.profile_manager import ProfileManager

router = APIRouter()

@router.post("/upload/quick-check", response_model=UploadResponse)
async def upload_quick_check(
    video_file: UploadFile = File(...),
    user_id: str = Form(...),
    user_text: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    上传每日检查视频 (Quick Check)
    """
    suffix = Path(video_file.filename).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(video_file.file, tmp)
        tmp_path = tmp.name

    session_id = None
    try:
        # 1. 摄取视频
        ingestion = VideoIngestionService(db)
        b_video, a_session = ingestion.ingest_video(
            video_file_data=None, 
            temp_file_path=tmp_path, 
            user_id=user_id,
            session_type="quick_check",
            user_description=user_text
        )
        session_id = str(a_session.id)
        ingestion.update_session_status(session_id, "processing")
        
        # 2. 智能抽帧
        print(f"[抽帧] 开始处理 Session: {session_id}")
        extractor = KeyframeExtractor(db)
        extractor.extract_keyframes(session_id, b_video.file_path)
        
        # 3. 生成证据包
        pack_gen = EvidencePackGenerator(db)
        pack_gen.generate_evidence_pack(session_id)
        
        # 4. 更新状态
        ingestion.update_session_status(session_id, "completed")
        
        # 5. 更新用户档案
        profile_mgr = ProfileManager(db)
        profile_mgr.record_quick_check(user_id)

        return UploadResponse(
            session_id=session_id,
            status="completed",
            message="Quick check processed successfully"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        
        # [关键修正] 遇到错误必须先回滚，否则后续 DB 操作会报 PendingRollbackError
        db.rollback()
        
        if session_id:
            try:
                ingestion = VideoIngestionService(db)
                ingestion.update_session_status(session_id, "failed", str(e))
            except Exception as e2:
                print(f"[严重] 无法更新 Session 失败状态: {e2}")
        
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/upload/baseline", response_model=UploadResponse)
async def upload_baseline(
    video_file: UploadFile = File(...),
    user_id: str = Form(...),
    zone_id: int = Form(..., ge=1, le=7),
    db: Session = Depends(get_db)
):
    """
    上传基线视频 (Baseline)
    """
    suffix = Path(video_file.filename).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(video_file.file, tmp)
        tmp_path = tmp.name

    session_id = None
    try:
        ingestion = VideoIngestionService(db)
        b_video, a_session = ingestion.ingest_video(
            video_file_data=None,
            temp_file_path=tmp_path,
            user_id=user_id,
            session_type="baseline",
            zone_id=zone_id
        )
        session_id = str(a_session.id)
        ingestion.update_session_status(session_id, "processing")
        
        print(f"[抽帧] 开始处理 Baseline Session: {session_id}")
        extractor = KeyframeExtractor(db)
        extractor.extract_keyframes(session_id, b_video.file_path)
        
        pack_gen = EvidencePackGenerator(db)
        pack_gen.generate_evidence_pack(session_id)
        
        ingestion.update_session_status(session_id, "completed")

        profile_mgr = ProfileManager(db)
        profile_mgr.mark_baseline_completed(user_id, zone_id, session_id)
        
        profile = profile_mgr.get_or_create_profile(user_id)
        completed_count = len(profile.baseline_zone_map or {})

        return UploadResponse(
            session_id=session_id,
            status="completed",
            message=f"Baseline zone {zone_id} processed",
            baseline_progress=f"{completed_count}/7"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        db.rollback() # 回滚
        if session_id:
            try:
                ingestion = VideoIngestionService(db)
                ingestion.update_session_status(session_id, "failed", str(e))
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)