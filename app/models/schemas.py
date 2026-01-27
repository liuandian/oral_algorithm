# -*- coding: utf-8 -*-
"""
API 请求/响应数据模型
"""
from datetime import datetime
from typing import Optional, Dict, List
from pydantic import BaseModel, Field


# ========================================
# 上传相关 Schemas
# ========================================

class UploadQuickCheckRequest(BaseModel):
    """快速检查视频上传请求（multipart/form-data）"""
    user_id: str = Field(..., description="用户ID")
    user_text: Optional[str] = Field(None, description="用户文字描述")
    device_info: Optional[Dict] = Field(default_factory=dict, description="设备信息")


class UploadBaselineRequest(BaseModel):
    """基线视频上传请求（multipart/form-data）"""
    user_id: str = Field(..., description="用户ID")
    zone_id: int = Field(..., ge=1, le=7, description="分区ID（1-7）")
    device_info: Optional[Dict] = Field(default_factory=dict, description="设备信息")


class UploadResponse(BaseModel):
    """上传响应"""
    session_id: str = Field(..., description="会话ID")
    status: str = Field(..., description="处理状态：pending/processing/completed/failed")
    message: str = Field(..., description="返回消息")
    estimated_time: Optional[int] = Field(None, description="预计处理时间（秒）")
    baseline_progress: Optional[str] = Field(None, description="基线完成进度（如：3/7）")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "status": "completed",
                "message": "视频处理完成",
                "estimated_time": None,
                "baseline_progress": None
            }
        }


# ========================================
# 用户档案相关 Schemas
# ========================================

class BaselineZoneInfo(BaseModel):
    """基线分区信息"""
    zone_id: int = Field(..., description="分区ID（1-7）")
    session_id: str = Field(..., description="对应的Session ID")
    completed_at: str = Field(..., description="完成时间")


class UserProfileResponse(BaseModel):
    """用户档案响应"""
    user_id: str = Field(..., description="用户ID")
    baseline_completed: bool = Field(..., description="基线是否完成")
    baseline_completion_date: Optional[str] = Field(None, description="基线完成日期")
    baseline_zones: List[BaselineZoneInfo] = Field(default_factory=list, description="基线分区列表")
    total_quick_checks: int = Field(..., description="快速检查总次数")
    last_check_date: Optional[str] = Field(None, description="最后检查日期")
    created_at: str = Field(..., description="档案创建时间")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_12345",
                "baseline_completed": False,
                "baseline_completion_date": None,
                "baseline_zones": [],
                "total_quick_checks": 5,
                "last_check_date": "2025-01-23T09:00:00Z",
                "created_at": "2025-01-15T08:00:00Z"
            }
        }


# ========================================
# Session 相关 Schemas
# ========================================

class SessionStatusResponse(BaseModel):
    """Session 状态响应"""
    session_id: str = Field(..., description="会话ID")
    user_id: str = Field(..., description="用户ID")
    session_type: str = Field(..., description="会话类型：quick_check / baseline")
    zone_id: Optional[int] = Field(None, description="分区ID（仅baseline）")
    processing_status: str = Field(..., description="处理状态")
    created_at: str = Field(..., description="创建时间")
    completed_at: Optional[str] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "user_id": "user_12345",
                "session_type": "quick_check",
                "zone_id": None,
                "processing_status": "completed",
                "created_at": "2025-01-23T10:00:00Z",
                "completed_at": "2025-01-23T10:00:15Z",
                "error_message": None
            }
        }


# ========================================
# 报告相关 Schemas
# ========================================

class GenerateReportRequest(BaseModel):
    """生成报告请求"""
    session_id: str = Field(..., description="会话ID")


class ReportResponse(BaseModel):
    """报告响应"""
    report_id: str = Field(..., description="报告ID")
    session_id: str = Field(..., description="会话ID")
    report_text: str = Field(..., description="生成的健康报告")
    llm_model: str = Field(..., description="使用的LLM模型")
    tokens_used: Optional[int] = Field(None, description="消耗的Token数量")
    generated_at: str = Field(..., description="生成时间")

    class Config:
        json_schema_extra = {
            "example": {
                "report_id": "report_xyz123",
                "session_id": "session_abc456",
                "report_text": "根据您的口腔视频分析，我们检测到以下情况：...",
                "llm_model": "qwen-vl-max",
                "tokens_used": 1500,
                "generated_at": "2025-01-23T10:05:00Z"
            }
        }


# ========================================
# 错误响应 Schemas
# ========================================

class ErrorResponse(BaseModel):
    """错误响应"""
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误描述")
    detail: Optional[str] = Field(None, description="详细信息")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "请求参数错误",
                "detail": "zone_id 必须在 1-7 之间"
            }
        }


# ========================================
# 通用响应 Schemas
# ========================================

class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str = Field(..., description="消息内容")
    data: Optional[Dict] = Field(None, description="附加数据")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "操作成功",
                "data": {"session_id": "abc123"}
            }
        }


# ========================================
# 用户事件相关 Schemas
# ========================================

class UserEventCreateRequest(BaseModel):
    """创建用户事件请求"""
    event_type: str = Field(..., description="事件类型：dental_cleaning/scaling/filling/extraction/crown/orthodontic/whitening/checkup/other")
    event_date: str = Field(..., description="事件日期（ISO 8601格式）")
    event_description: Optional[str] = Field(None, description="事件描述")
    related_session_id: Optional[str] = Field(None, description="关联的Session ID")
    metadata: Optional[Dict] = Field(default_factory=dict, description="附加元数据")

    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "dental_cleaning",
                "event_date": "2025-01-15T10:00:00Z",
                "event_description": "常规洁牙",
                "related_session_id": None,
                "metadata": {"clinic": "XX口腔医院"}
            }
        }


class UserEventResponse(BaseModel):
    """用户事件响应"""
    id: str = Field(..., description="事件ID")
    user_id: str = Field(..., description="用户ID")
    event_type: str = Field(..., description="事件类型")
    event_date: str = Field(..., description="事件日期")
    event_description: Optional[str] = Field(None, description="事件描述")
    related_session_id: Optional[str] = Field(None, description="关联的Session ID")
    metadata: Dict = Field(default_factory=dict, description="附加元数据")
    created_at: str = Field(..., description="创建时间")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user_12345",
                "event_type": "dental_cleaning",
                "event_date": "2025-01-15T10:00:00Z",
                "event_description": "常规洁牙",
                "related_session_id": None,
                "metadata": {"clinic": "XX口腔医院"},
                "created_at": "2025-01-15T10:30:00Z"
            }
        }


class UserEventListResponse(BaseModel):
    """用户事件列表响应"""
    events: List[UserEventResponse] = Field(..., description="事件列表")
    total: int = Field(..., description="总数量")


# ========================================
# 关注点相关 Schemas
# ========================================

class ConcernPointCreateRequest(BaseModel):
    """创建关注点请求"""
    source_type: str = Field(default="user_reported", description="来源类型：user_reported/system_detected")
    zone_id: Optional[int] = Field(None, ge=1, le=7, description="分区ID（1-7）")
    location_description: Optional[str] = Field(None, max_length=200, description="位置描述")
    concern_type: str = Field(..., description="关注点类型")
    concern_description: Optional[str] = Field(None, description="详细描述")
    severity: str = Field(default="mild", description="严重程度：mild/moderate/severe")

    class Config:
        json_schema_extra = {
            "example": {
                "source_type": "user_reported",
                "zone_id": 2,
                "location_description": "上门牙右侧",
                "concern_type": "dark_spot",
                "concern_description": "发现一个小黑点",
                "severity": "mild"
            }
        }


class ConcernPointResponse(BaseModel):
    """关注点响应"""
    id: str = Field(..., description="关注点ID")
    user_id: str = Field(..., description="用户ID")
    source_type: str = Field(..., description="来源类型")
    zone_id: Optional[int] = Field(None, description="分区ID")
    location_description: Optional[str] = Field(None, description="位置描述")
    concern_type: str = Field(..., description="关注点类型")
    concern_description: Optional[str] = Field(None, description="详细描述")
    severity: str = Field(..., description="严重程度")
    status: str = Field(..., description="状态：active/resolved/monitoring")
    first_detected_at: str = Field(..., description="首次检测时间")
    last_observed_at: str = Field(..., description="最后观察时间")
    resolved_at: Optional[str] = Field(None, description="解决时间")
    related_sessions: List[str] = Field(default_factory=list, description="相关Session ID列表")
    evidence_frame_ids: List[str] = Field(default_factory=list, description="证据帧ID列表")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user_12345",
                "source_type": "user_reported",
                "zone_id": 2,
                "location_description": "上门牙右侧",
                "concern_type": "dark_spot",
                "concern_description": "发现一个小黑点",
                "severity": "mild",
                "status": "active",
                "first_detected_at": "2025-01-15T10:00:00Z",
                "last_observed_at": "2025-01-20T15:00:00Z",
                "resolved_at": None,
                "related_sessions": [],
                "evidence_frame_ids": [],
                "created_at": "2025-01-15T10:30:00Z",
                "updated_at": "2025-01-20T15:00:00Z"
            }
        }


class ConcernPointListResponse(BaseModel):
    """关注点列表响应"""
    concerns: List[ConcernPointResponse] = Field(..., description="关注点列表")
    total: int = Field(..., description="总数量")


class ConcernStatusUpdateRequest(BaseModel):
    """更新关注点状态请求"""
    status: str = Field(..., description="新状态：active/resolved/monitoring")
    related_session_id: Optional[str] = Field(None, description="关联的Session ID")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "resolved",
                "related_session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
            }
        }


# ========================================
# 时间轴相关 Schemas
# ========================================

class TimelineEventItem(BaseModel):
    """时间轴事件项"""
    event_type: str = Field(..., description="事件类型：session/user_event/concern_update")
    event_id: str = Field(..., description="事件ID")
    event_date: str = Field(..., description="事件日期")
    title: str = Field(..., description="事件标题")
    description: Optional[str] = Field(None, description="事件描述")
    metadata: Dict = Field(default_factory=dict, description="附加信息")


class TimelineResponse(BaseModel):
    """时间轴响应"""
    user_id: str = Field(..., description="用户ID")
    period: str = Field(..., description="查询周期：week/month/quarter/year/all")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    events: List[TimelineEventItem] = Field(..., description="事件列表")
    total: int = Field(..., description="事件总数")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_12345",
                "period": "month",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-01-31T23:59:59Z",
                "events": [],
                "total": 0
            }
        }


# ========================================
# 扩展档案相关 Schemas
# ========================================

class ExtendedUserProfileResponse(BaseModel):
    """扩展用户档案响应"""
    user_id: str = Field(..., description="用户ID")
    baseline_completed: bool = Field(..., description="基线是否完成")
    baseline_completion_date: Optional[str] = Field(None, description="基线完成日期")
    baseline_zones: List[BaselineZoneInfo] = Field(default_factory=list, description="基线分区列表")
    total_quick_checks: int = Field(..., description="快速检查总次数")
    last_check_date: Optional[str] = Field(None, description="最后检查日期")
    total_baseline_updates: int = Field(default=0, description="基线更新总次数")
    last_baseline_update_date: Optional[str] = Field(None, description="最后基线更新日期")
    active_concerns_count: int = Field(default=0, description="活跃关注点数量")
    recent_events_count: int = Field(default=0, description="近期事件数量（30天内）")
    created_at: str = Field(..., description="档案创建时间")
    updated_at: str = Field(..., description="档案更新时间")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_12345",
                "baseline_completed": True,
                "baseline_completion_date": "2025-01-10T10:00:00Z",
                "baseline_zones": [],
                "total_quick_checks": 5,
                "last_check_date": "2025-01-23T09:00:00Z",
                "total_baseline_updates": 1,
                "last_baseline_update_date": "2025-01-10T10:00:00Z",
                "active_concerns_count": 2,
                "recent_events_count": 1,
                "created_at": "2025-01-01T08:00:00Z",
                "updated_at": "2025-01-23T09:00:00Z"
            }
        }
