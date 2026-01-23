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
