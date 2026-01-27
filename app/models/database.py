# -*- coding: utf-8 -*-
"""
数据库 ORM 模型
基于 SQLAlchemy
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, Text, BigInteger, TIMESTAMP, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import uuid

from app.config import settings

# 创建基类
Base = declarative_base()


# ========================================
# B 数据流：原始资产库
# ========================================

class BRawVideo(Base):
    """B流：原始视频表"""
    __tablename__ = "b_raw_videos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(64), nullable=False, index=True)
    file_hash = Column(String(64), unique=True, nullable=False, index=True)
    file_path = Column(Text, nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    duration_seconds = Column(Float)
    uploaded_at = Column(TIMESTAMP, default=func.now())

    # 原始元数据
    device_info = Column(JSONB, default={})
    user_text_description = Column(Text)
    session_type = Column(String(20), nullable=False)
    zone_id = Column(Integer)

    # 物理隔离保护
    is_locked = Column(Boolean, default=True, nullable=False)

    # 关系
    sessions = relationship("ASession", back_populates="b_video")

    __table_args__ = (
        CheckConstraint("session_type IN ('quick_check', 'baseline')", name="check_b_session_type"),
        CheckConstraint("zone_id BETWEEN 1 AND 7", name="check_b_zone_id"),
    )


# ========================================
# A 数据流：业务应用层
# ========================================

class ASession(Base):
    """A流：Session 记录表"""
    __tablename__ = "a_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(64), nullable=False, index=True)
    b_video_id = Column(UUID(as_uuid=True), ForeignKey("b_raw_videos.id", ondelete="RESTRICT"), nullable=False)
    session_type = Column(String(20), nullable=False)
    zone_id = Column(Integer)
    processing_status = Column(String(20), default="pending", index=True)
    error_message = Column(Text)
    created_at = Column(TIMESTAMP, default=func.now())
    completed_at = Column(TIMESTAMP)

    # 关系
    b_video = relationship("BRawVideo", back_populates="sessions")
    keyframes = relationship("AKeyframe", back_populates="session", cascade="all, delete-orphan")
    evidence_pack = relationship("AEvidencePack", back_populates="session", uselist=False, cascade="all, delete-orphan")
    reports = relationship("AReport", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("session_type IN ('quick_check', 'baseline')", name="check_a_session_type"),
        CheckConstraint("zone_id BETWEEN 1 AND 7", name="check_a_zone_id"),
        CheckConstraint("processing_status IN ('pending', 'processing', 'completed', 'failed')", name="check_processing_status"),
    )


class AKeyframe(Base):
    """A流：关键帧表"""
    __tablename__ = "a_keyframes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("a_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    frame_index = Column(Integer, nullable=False)
    timestamp_in_video = Column(String(10), nullable=False)
    extraction_strategy = Column(String(20), nullable=False)
    extraction_reason = Column(String(50), nullable=True)
    
    # 图像存储
    image_path = Column(Text, nullable=False)
    image_thumbnail_path = Column(Text)

    # 结构化元数据
    meta_tags = Column(JSONB, nullable=False, default={})

    # 检测得分
    anomaly_score = Column(Float, default=0.0)

    created_at = Column(TIMESTAMP, default=func.now())

    # 关系
    session = relationship("ASession", back_populates="keyframes")

    __table_args__ = (
        UniqueConstraint("session_id", "frame_index", name="uq_session_frame_index"),
        CheckConstraint("extraction_strategy IN ('rule_triggered', 'uniform_sampled')", name="check_extraction_strategy"),
        CheckConstraint("anomaly_score >= 0 AND anomaly_score <= 1", name="check_anomaly_score"),
    )


class AEvidencePack(Base):
    """A流：证据包表"""
    __tablename__ = "a_evidence_packs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("a_sessions.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    pack_json = Column(JSONB, nullable=False)
    total_frames = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, default=func.now())

    # 关系
    session = relationship("ASession", back_populates="evidence_pack")
    reports = relationship("AReport", back_populates="evidence_pack", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("total_frames > 0 AND total_frames <= 25", name="check_total_frames"),
    )


class AUserProfile(Base):
    """A流：用户档案表"""
    __tablename__ = "a_user_profiles"

    user_id = Column(String(64), primary_key=True)
    baseline_completed = Column(Boolean, default=False, index=True)
    baseline_completion_date = Column(TIMESTAMP)

    # 基线映射
    baseline_zone_map = Column(JSONB, default={})

    # 统计信息
    total_quick_checks = Column(Integer, default=0)
    last_check_date = Column(TIMESTAMP)

    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())


class AReport(Base):
    """A流：LLM 报告表"""
    __tablename__ = "a_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("a_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_pack_id = Column(UUID(as_uuid=True), ForeignKey("a_evidence_packs.id", ondelete="CASCADE"), nullable=False)

    report_text = Column(Text, nullable=False)
    llm_model = Column(String(50))
    tokens_used = Column(Integer)

    created_at = Column(TIMESTAMP, default=func.now())

    # 关系
    session = relationship("ASession", back_populates="reports")
    evidence_pack = relationship("AEvidencePack", back_populates="reports")


# ========================================
# C 数据流：训练沙盒（预留）
# ========================================

class CTrainingSnapshot(Base):
    """C流：训练快照表"""
    __tablename__ = "c_training_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    b_video_id = Column(UUID(as_uuid=True), ForeignKey("b_raw_videos.id", ondelete="RESTRICT"), nullable=False)
    snapshot_path = Column(Text, nullable=False)
    purpose = Column(String(50))
    created_at = Column(TIMESTAMP, default=func.now())

    # 关系
    annotations = relationship("CAnnotation", back_populates="snapshot", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("purpose IN ('annotation', 'augmentation', 'training')", name="check_c_purpose"),
    )


class CAnnotation(Base):
    """C流：注释表"""
    __tablename__ = "c_annotations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey("c_training_snapshots.id", ondelete="CASCADE"), nullable=False)
    annotation_data = Column(JSONB, default={})
    annotator_id = Column(String(64))
    created_at = Column(TIMESTAMP, default=func.now())

    # 关系
    snapshot = relationship("CTrainingSnapshot", back_populates="annotations")


# ========================================
# 数据库连接与会话管理
# ========================================

# 创建引擎
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # 自动重连
    echo=settings.DEBUG,  # Debug 模式显示 SQL
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """获取数据库会话（FastAPI 依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库（创建所有表）"""
    Base.metadata.create_all(bind=engine)
    print("[数据库] 表初始化完成")


def drop_all_tables():
    """删除所有表（危险操作，仅用于开发）"""
    Base.metadata.drop_all(bind=engine)
    print("[数据库] 所有表已删除")
