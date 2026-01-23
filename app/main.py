"""
Oral Health Monitoring System - FastAPI Main Application
"""
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import tempfile
import shutil
from pathlib import Path
from typing import Optional

from app.config import settings
from app.models.database import get_db
from app.models.schemas import *
from app.core.ingestion import VideoIngestionService
from app.core.evidence_pack import EvidencePackGenerator
from app.core.profile_manager import ProfileManager
from app.core.llm_client import LLMReportGenerator

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Oral Health Monitoring System API",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========================================
# Health Check Endpoints
# ========================================

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


# ========================================
# Video Upload APIs
# ========================================

@app.post(f"{settings.API_PREFIX}/upload/quick-check", response_model=UploadResponse)
async def upload_quick_check(
    video_file: UploadFile = File(...),
    user_id: str = Form(...),
    user_text: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload quick check video"""
    # Save temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        shutil.copyfileobj(video_file.file, tmp)
        tmp_path = tmp.name

    try:
        # Video ingestion
        ingestion = VideoIngestionService(db)
        session_id, b_video_id = ingestion.ingest_video(
            video_path=tmp_path,
            user_id=user_id,
            session_type="quick_check",
            user_text=user_text
        )

        # Mark as processing
        ingestion.mark_session_processing(session_id)

        # Generate evidence pack (synchronous processing)
        pack_gen = EvidencePackGenerator(db)
        evidence_pack = pack_gen.generate_from_session(session_id)

        # Mark completed
        ingestion.mark_session_completed(session_id)

        return UploadResponse(
            session_id=session_id,
            status="completed",
            message="Video processing completed",
            estimated_time=None
        )

    except Exception as e:
        # Mark failed
        ingestion.mark_session_failed(session_id, str(e))
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Clean up temporary file
        Path(tmp_path).unlink(missing_ok=True)


@app.post(f"{settings.API_PREFIX}/upload/baseline", response_model=UploadResponse)
async def upload_baseline(
    video_file: UploadFile = File(...),
    user_id: str = Form(...),
    zone_id: int = Form(..., ge=1, le=7),
    db: Session = Depends(get_db)
):
    """Upload baseline video"""
    # Save temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        shutil.copyfileobj(video_file.file, tmp)
        tmp_path = tmp.name

    try:
        # Video ingestion
        ingestion = VideoIngestionService(db)
        session_id, b_video_id = ingestion.ingest_video(
            video_path=tmp_path,
            user_id=user_id,
            session_type="baseline",
            zone_id=zone_id
        )

        # Process video
        ingestion.mark_session_processing(session_id)
        pack_gen = EvidencePackGenerator(db)
        evidence_pack = pack_gen.generate_from_session(session_id)
        ingestion.mark_session_completed(session_id)

        # Get baseline progress
        profile_mgr = ProfileManager(db)
        progress = profile_mgr.get_baseline_progress(user_id)

        return UploadResponse(
            session_id=session_id,
            status="completed",
            message="Baseline video processing completed",
            baseline_progress=progress["progress"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ========================================
# User Profile APIs
# ========================================

@app.get(f"{settings.API_PREFIX}/user/{{user_id}}/profile", response_model=UserProfileResponse)
async def get_user_profile(user_id: str, db: Session = Depends(get_db)):
    """Get user profile"""
    profile_mgr = ProfileManager(db)
    profile = profile_mgr.get_profile(user_id)

    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")

    # Build baseline zone information
    baseline_zones = []
    if profile.baseline_zone_map:
        for zone_key, session_id in profile.baseline_zone_map.items():
            zone_id = int(zone_key.split("_")[1])
            baseline_zones.append(
                BaselineZoneInfo(
                    zone_id=zone_id,
                    session_id=session_id,
                    completed_at=profile.created_at.isoformat()
                )
            )

    return UserProfileResponse(
        user_id=profile.user_id,
        baseline_completed=profile.baseline_completed,
        baseline_completion_date=profile.baseline_completion_date.isoformat() if profile.baseline_completion_date else None,
        baseline_zones=baseline_zones,
        total_quick_checks=profile.total_quick_checks,
        last_check_date=profile.last_check_date.isoformat() if profile.last_check_date else None,
        created_at=profile.created_at.isoformat()
    )


# ========================================
# Session APIs
# ========================================

@app.get(f"{settings.API_PREFIX}/session/{{session_id}}/evidence-pack")
async def get_evidence_pack(session_id: str, db: Session = Depends(get_db)):
    """Get evidence pack"""
    pack_gen = EvidencePackGenerator(db)
    try:
        evidence_pack = pack_gen.get_evidence_pack(session_id)
        return evidence_pack
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get(f"{settings.API_PREFIX}/session/{{session_id}}/status", response_model=SessionStatusResponse)
async def get_session_status(session_id: str, db: Session = Depends(get_db)):
    """Get session status"""
    from app.models.database import ASession
    import uuid

    session = db.query(ASession).filter(ASession.id == uuid.UUID(session_id)).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionStatusResponse(
        session_id=str(session.id),
        user_id=session.user_id,
        session_type=session.session_type,
        zone_id=session.zone_id,
        processing_status=session.processing_status,
        created_at=session.created_at.isoformat(),
        completed_at=session.completed_at.isoformat() if session.completed_at else None,
        error_message=session.error_message
    )


# ========================================
# Report Generation APIs
# ========================================

@app.post(f"{settings.API_PREFIX}/session/{{session_id}}/report", response_model=ReportResponse)
async def generate_report(session_id: str, db: Session = Depends(get_db)):
    """Generate health report"""
    llm_gen = LLMReportGenerator(db)
    try:
        report = await llm_gen.generate_report_async(session_id)
        return ReportResponse(**report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(f"{settings.API_PREFIX}/session/{{session_id}}/report", response_model=ReportResponse)
async def get_report(session_id: str, db: Session = Depends(get_db)):
    """Get existing report"""
    llm_gen = LLMReportGenerator(db)
    try:
        report = llm_gen.get_report(session_id)
        return ReportResponse(**report)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ========================================
# Startup Events
# ========================================

@app.on_event("startup")
async def startup_event():
    """Execute on application startup"""
    print("=" * 60)
    print(f"{settings.APP_NAME} v{settings.APP_VERSION}")
    print("=" * 60)
    print("Application starting...")

    # Ensure data directories exist
    from app.config import ensure_directories
    ensure_directories()

    print("Application ready!")
    print(f"API Docs: http://localhost:8000/docs")
    print("=" * 60)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
