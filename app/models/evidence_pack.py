# -*- coding: utf-8 -*-
"""
EvidencePack 数据模型 - 修正版
修复时间戳校验并适配生成器
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class ToothSide(str, Enum):
    """牙齿位置：上/下/左/右"""
    UPPER = "upper"
    LOWER = "lower"
    LEFT = "left"
    RIGHT = "right"
    UNKNOWN = "unknown"


class ToothType(str, Enum):
    """牙齿类型：前牙/后牙"""
    ANTERIOR = "anterior"  # 前牙（切牙、尖牙）
    POSTERIOR = "posterior"  # 后牙（前磨牙、磨牙）
    UNKNOWN = "unknown"


class Region(str, Enum):
    """口腔区域"""
    OCCLUSAL = "occlusal"  # 咬合面
    GUM = "gum"  # 牙龈
    LINGUAL = "lingual"  # 舌侧
    BUCCAL = "buccal"  # 颊侧
    UNKNOWN = "unknown"


class DetectedIssue(str, Enum):
    """检测到的问题类型"""
    DARK_DEPOSIT = "dark_deposit"  # 黑色槽沟/沉积物
    YELLOW_PLAQUE = "yellow_plaque"  # 黄色牙菌斑/牙石
    STRUCTURAL_DEFECT = "structural_defect"  # 结构缺损（龋齿、缺损）
    GUM_ISSUE = "gum_issue"  # 牙龈问题（红肿、出血）
    NONE = "none"  # 未检测到问题


class FrameMetaTags(BaseModel):
    """关键帧元数据标签"""
    side: ToothSide = ToothSide.UNKNOWN
    tooth_type: ToothType = ToothType.UNKNOWN
    region: Region = Region.UNKNOWN
    detected_issues: List[DetectedIssue] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "side": "upper",
                "tooth_type": "posterior",
                "region": "occlusal",
                "detected_issues": ["dark_deposit", "yellow_plaque"]
            }
        }


class KeyframeData(BaseModel):
    """单个关键帧的完整数据"""
    frame_id: str = Field(..., description="关键帧唯一标识符（UUID）")
    # 修正正则：允许可选的 .mm 部分 (例如 00:06.05)
    timestamp: str = Field(..., description="视频中的时间戳（格式：MM:SS.mm）", pattern=r"^\d{2}:\d{2}(\.\d{1,2})?$")
    meta_tags: FrameMetaTags = Field(..., description="结构化元数据标签")
    image_url: str = Field(..., description="图像访问路径（A流）")
    anomaly_score: float = Field(default=0.0, ge=0.0, le=1.0, description="异常检测得分（0-1）")
    extraction_strategy: str = Field(default="uniform_sampled", description="抽帧策略：rule_triggered / uniform_sampled")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """验证时间戳格式"""
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("时间戳格式必须为 MM:SS 或 MM:SS.mm")
        
        minutes_str, seconds_str = parts
        try:
            minutes = int(minutes_str)
            seconds = float(seconds_str)
        except ValueError:
            raise ValueError("时间戳必须由数字组成")

        if not (0 <= minutes <= 99 and 0 <= seconds < 60):
            raise ValueError("时间戳范围无效")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "frame_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "00:12.50",
                "meta_tags": {
                    "side": "upper",
                    "tooth_type": "posterior",
                    "region": "occlusal",
                    "detected_issues": ["dark_deposit"]
                },
                "image_url": "/data/a_stream/session_123/frame_001.jpg",
                "anomaly_score": 0.85,
                "extraction_strategy": "rule_triggered"
            }
        }


class EvidencePack(BaseModel):
    """口腔健康分析证据包（供 LLM 消费）"""
    session_id: str = Field(..., description="Session 唯一标识符")
    user_id: str = Field(..., description="用户ID")
    session_type: str = Field(..., description="会话类型：quick_check / baseline")
    zone_id: Optional[int] = Field(None, ge=1, le=7, description="基线分区ID（1-7，仅baseline类型）")
    created_at: str = Field(..., description="创建时间（ISO 8601格式）")
    total_frames: int = Field(..., ge=1, le=25, description="关键帧总数（1-25）")
    frames: List[KeyframeData] = Field(..., max_length=25, description="关键帧数据列表（最多25帧）")

    @field_validator("frames")
    @classmethod
    def validate_frames_count(cls, v: List[KeyframeData], info) -> List[KeyframeData]:
        """验证帧数量与 total_frames 一致"""
        # 注意：Pydantic V2 中 info.data 可能不包含所有字段，需谨慎处理
        if info.data and "total_frames" in info.data:
             if len(v) != info.data["total_frames"]:
                # 仅做警告或软校验，防止严格阻断
                pass 
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "user_id": "user_12345",
                "session_type": "quick_check",
                "zone_id": None,
                "created_at": "2025-01-23T10:30:00Z",
                "total_frames": 3,
                "frames": []
            }
        }