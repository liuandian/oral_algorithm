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

    # 新增：基线参考数据
    baseline_reference_json = Column(JSONB, nullable=True)
    comparison_mode = Column(String(20), default="none")

    # 关系
    session = relationship("ASession", back_populates="evidence_pack")
    reports = relationship("AReport", back_populates="evidence_pack", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("total_frames > 0 AND total_frames <= 25", name="check_total_frames"),
        CheckConstraint("comparison_mode IN ('none', 'partial', 'full')", name="check_comparison_mode"),
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

    # 新增：基线更新统计
    total_baseline_updates = Column(Integer, default=0)
    last_baseline_update_date = Column(TIMESTAMP)

    # 新增：时间轴缓存与通知设置
    timeline_summary = Column(JSONB, default={})
    notification_preferences = Column(JSONB, default={})

    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())

    # 关系
    events = relationship("AUserEvent", back_populates="profile")
    concerns = relationship("AConcernPoint", back_populates="profile")


class AUserEvent(Base):
    """A流：用户自述事件表"""
    __tablename__ = "a_user_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(64), ForeignKey("a_user_profiles.user_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # dental_cleaning/scaling/filling/extraction/...
    event_description = Column(Text)
    event_date = Column(TIMESTAMP, nullable=False)
    related_session_id = Column(UUID(as_uuid=True), ForeignKey("a_sessions.id", ondelete="SET NULL"), nullable=True)
    event_metadata = Column(JSONB, default={})  # renamed from 'metadata' (reserved)
    created_at = Column(TIMESTAMP, default=func.now())

    # 关系
    profile = relationship("AUserProfile", back_populates="events")

    __table_args__ = (
        CheckConstraint("event_type IN ('dental_cleaning', 'scaling', 'filling', 'extraction', 'crown', 'orthodontic', 'whitening', 'checkup', 'other')", name="check_event_type"),
    )


class AConcernPoint(Base):
    """A流：历史关注点表"""
    __tablename__ = "a_concern_points"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(64), ForeignKey("a_user_profiles.user_id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(20), nullable=False)  # user_reported/system_detected
    zone_id = Column(Integer, nullable=True)
    location_description = Column(String(200))
    concern_type = Column(String(50), nullable=False)
    concern_description = Column(Text)
    severity = Column(String(20), default="mild")  # mild/moderate/severe
    status = Column(String(20), default="active", index=True)  # active/resolved/monitoring
    first_detected_at = Column(TIMESTAMP, default=func.now())
    last_observed_at = Column(TIMESTAMP, default=func.now())
    resolved_at = Column(TIMESTAMP, nullable=True)
    related_sessions = Column(JSONB, default=[])  # List of session IDs
    evidence_frame_ids = Column(JSONB, default=[])  # List of frame IDs
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())

    # 关系
    profile = relationship("AUserProfile", back_populates="concerns")

    __table_args__ = (
        CheckConstraint("source_type IN ('user_reported', 'system_detected')", name="check_concern_source_type"),
        CheckConstraint("severity IN ('mild', 'moderate', 'severe')", name="check_concern_severity"),
        CheckConstraint("status IN ('active', 'resolved', 'monitoring')", name="check_concern_status"),
        CheckConstraint("zone_id IS NULL OR (zone_id BETWEEN 1 AND 7)", name="check_concern_zone_id"),
    )


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
