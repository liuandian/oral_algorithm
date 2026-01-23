# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.database import get_db, ASession
from app.models.schemas import SessionStatusResponse
from app.core.evidence_pack import EvidencePackGenerator, EvidencePackError

router = APIRouter()

@router.get("/session/{session_id}/evidence-pack")
async def get_evidence_pack_data(session_id: str, db: Session = Depends(get_db)):
    """
    获取已生成的 EvidencePack JSON 数据
    """
    pack_gen = EvidencePackGenerator(db)
    try:
        pack = pack_gen.get_evidence_pack_by_session(session_id)
        return pack
    except EvidencePackError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/session/{session_id}/status", response_model=SessionStatusResponse)
async def get_session_status_info(session_id: str, db: Session = Depends(get_db)):
    """
    查询 Session 处理状态
    """
    session = db.query(ASession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return SessionStatusResponse(
        session_id=str(session.id),
        user_id=session.user_id,
        session_type=session.session_type,
        zone_id=session.zone_id,
        processing_status=session.processing_status,
        created_at=str(session.created_at),
        completed_at=str(session.completed_at) if session.completed_at else None,
        error_message=session.error_message
    )