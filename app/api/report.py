# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.schemas import ReportResponse
from app.core.llm_client import LLMReportGenerator, LLMClientError
from app.core.evidence_pack import EvidencePackGenerator

router = APIRouter()

@router.post("/session/{session_id}/report", response_model=ReportResponse)
async def generate_health_report(session_id: str, db: Session = Depends(get_db)):
    """
    触发 LLM 生成报告 (同步调用，生产环境建议异步)
    """
    try:
        # 1. 获取证据包
        pack_gen = EvidencePackGenerator(db)
        evidence_pack = pack_gen.get_evidence_pack_by_session(session_id)
        
        # 2. 生成报告
        llm_gen = LLMReportGenerator(db)
        # 检查是否已有报告
        existing_report = llm_gen.get_report_by_session(session_id)
        if existing_report:
            return ReportResponse(
                report_id=str(existing_report.id),
                session_id=str(existing_report.session_id),
                report_text=existing_report.report_text,
                llm_model=existing_report.llm_model or "unknown",
                tokens_used=existing_report.tokens_used,
                generated_at=str(existing_report.created_at)
            )

        report = llm_gen.generate_report(session_id, evidence_pack)
        
        return ReportResponse(
            report_id=str(report.id),
            session_id=str(report.session_id),
            report_text=report.report_text,
            llm_model=report.llm_model,
            tokens_used=report.tokens_used,
            generated_at=str(report.created_at)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))