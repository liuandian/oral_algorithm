# -*- coding: utf-8 -*-
"""
Oral Health Monitoring System - FastAPI Main Application
Entry point for the application.
"""
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.config import ensure_directories
from app.api import upload, user, session, report

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup 逻辑
    print("=" * 60)
    print(f"{settings.APP_NAME} v{settings.APP_VERSION}")
    print("=" * 60)
    print("System initializing...")
    ensure_directories()
    print("System ready!")
    print(f"API Docs: http://localhost:8765/docs")
    print("=" * 60)
    yield
    # Shutdown 逻辑 (如有需要可以在这里添加)
    print("System shutting down...")

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Oral Health Monitoring System API (V1)",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
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
# Include Routers (Modular Design)
# ========================================
app.include_router(upload.router, prefix=settings.API_PREFIX, tags=["Upload"])
app.include_router(user.router, prefix=settings.API_PREFIX, tags=["User Profile"])
app.include_router(session.router, prefix=settings.API_PREFIX, tags=["Session & Evidence"])
app.include_router(report.router, prefix=settings.API_PREFIX, tags=["LLM Report"])


# ========================================
# Health Check
# ========================================
@app.get("/health", tags=["System"])
def health_check():
    """System health check endpoint"""
    return {"status": "healthy", "version": settings.APP_VERSION}



if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8765,
        reload=settings.DEBUG
    )