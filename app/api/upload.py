# -*- coding: utf-8 -*-
from fastapi import APIRouter, File, UploadFile, Form, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
import shutil
import tempfile
import os
from pathlib import Path

from app.models.database import get_db
from app.models.schemas import UploadResponse
from app.core.ingestion import VideoIngestionService
from app.core.evidence_pack import EvidencePackGenerator
from app.core.profile_manager import ProfileManager

router = APIRouter()

def process_video_task(session_id: str, db: Session):
    """
    后台任务：处理视频生成 EvidencePack
    注意：在实际生产中，这应该由 Celery 完成，V1 使用 BackgroundTasks
    """
    # 由于 db session 在请求结束后会关闭，这里需要小心处理
    # V1 简化版本：同步调用（或在此处重新创建 session，略复杂，建议 V1 先保持同步或简单异步）
    pass 

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
    # 1. 保存到临时文件
    suffix = Path(video_file.filename).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(video_file.file, tmp)
        tmp_path = tmp.name

    try:
        # 2. 视频摄取 (Ingestion) -> B流 & A流Session
        ingestion = VideoIngestionService(db)
        b_video, a_session = ingestion.ingest_video(
            video_file_data=None, # 我们传路径，不传bytes以节省内存
            temp_file_path=tmp_path, # 修改 ingestion 接口支持路径
            user_id=user_id,
            session_type="quick_check",
            user_description=user_text
        )

        session_id = str(a_session.id)
        
        # 3. 立即生成 EvidencePack (V1 阶段同步执行以确保流程跑通)
        # 标记为处理中
        ingestion.update_session_status(session_id, "processing")
        
        pack_gen = EvidencePackGenerator(db)
        pack_gen.generate_evidence_pack(session_id)
        
        # 标记完成
        ingestion.update_session_status(session_id, "completed")
        
        # 记录到用户档案
        profile_mgr = ProfileManager(db)
        profile_mgr.record_quick_check(user_id)

        return UploadResponse(
            session_id=session_id,
            status="completed",
            message="Quick check processed successfully"
        )

    except Exception as e:
        # 错误处理
        if 'session_id' in locals():
            ingestion.update_session_status(session_id, "failed", str(e))
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # 清理临时文件
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
        
        pack_gen = EvidencePackGenerator(db)
        pack_gen.generate_evidence_pack(session_id)
        
        ingestion.update_session_status(session_id, "completed")

        # 标记档案基线
        profile_mgr = ProfileManager(db)
        profile_mgr.mark_baseline_completed(user_id, zone_id, session_id)
        
        # 获取当前进度
        profile = profile_mgr.get_or_create_profile(user_id)
        completed_count = len(profile.baseline_zone_map or {})

        return UploadResponse(
            session_id=session_id,
            status="completed",
            message=f"Baseline zone {zone_id} processed",
            baseline_progress=f"{completed_count}/7"
        )

    except Exception as e:
        if 'session_id' in locals():
            ingestion.update_session_status(session_id, "failed", str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)