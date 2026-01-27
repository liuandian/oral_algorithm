# -*- coding: utf-8 -*-
"""
用户档案扩展 API
包含用户事件、关注点、时间轴等端点
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import (
    UserEventCreateRequest,
    UserEventResponse,
    UserEventListResponse,
    ConcernPointCreateRequest,
    ConcernPointResponse,
    ConcernPointListResponse,
    ConcernStatusUpdateRequest,
    TimelineResponse,
    ExtendedUserProfileResponse,
    BaselineZoneInfo,
    MessageResponse
)
from app.core.profile_manager import ProfileManager

router = APIRouter()


# ========================================
# 扩展档案
# ========================================

@router.get("/user/{user_id}/profile/extended", response_model=ExtendedUserProfileResponse)
async def get_extended_user_profile(user_id: str, db: Session = Depends(get_db)):
    """
    获取用户扩展档案

    包含基础档案信息、活跃关注点数量、近期事件数量等。
    """
    profile_mgr = ProfileManager(db)
    extended_profile = profile_mgr.get_extended_profile(user_id)

    # 转换基线信息
    baseline_zones = []
    baseline_zone_map = extended_profile.get("baseline_zone_map", {})
    for zone_id_str, session_id in baseline_zone_map.items():
        baseline_zones.append(
            BaselineZoneInfo(
                zone_id=int(zone_id_str),
                session_id=str(session_id),
                completed_at=extended_profile.get("updated_at", "")
            )
        )

    return ExtendedUserProfileResponse(
        user_id=extended_profile["user_id"],
        baseline_completed=extended_profile["baseline_completed"],
        baseline_completion_date=extended_profile.get("baseline_completion_date"),
        baseline_zones=baseline_zones,
        total_quick_checks=extended_profile["total_quick_checks"],
        last_check_date=extended_profile.get("last_check_date"),
        total_baseline_updates=extended_profile.get("total_baseline_updates", 0),
        last_baseline_update_date=extended_profile.get("last_baseline_update_date"),
        active_concerns_count=extended_profile.get("active_concerns_count", 0),
        recent_events_count=extended_profile.get("recent_events_count", 0),
        created_at=extended_profile["created_at"],
        updated_at=extended_profile.get("updated_at", extended_profile["created_at"])
    )


# ========================================
# 用户事件
# ========================================

@router.post("/user/{user_id}/events", response_model=UserEventResponse)
async def create_user_event(
    user_id: str,
    request: UserEventCreateRequest,
    db: Session = Depends(get_db)
):
    """
    记录用户事件

    事件类型包括：
    - dental_cleaning: 洁牙
    - scaling: 洗牙/龈下刮治
    - filling: 补牙
    - extraction: 拔牙
    - crown: 牙冠/烤瓷牙
    - orthodontic: 正畸调整
    - whitening: 美白
    - checkup: 口腔检查
    - other: 其他
    """
    profile_mgr = ProfileManager(db)

    try:
        event_date = datetime.fromisoformat(request.event_date.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的日期格式，请使用 ISO 8601 格式")

    event = profile_mgr.add_user_event(
        user_id=user_id,
        event_type=request.event_type,
        event_date=event_date,
        event_description=request.event_description,
        related_session_id=request.related_session_id,
        metadata=request.metadata
    )

    return UserEventResponse(
        id=str(event.id),
        user_id=event.user_id,
        event_type=event.event_type,
        event_date=str(event.event_date.isoformat()),
        event_description=event.event_description,
        related_session_id=str(event.related_session_id) if event.related_session_id else None,
        metadata=event.event_metadata or {},
        created_at=str(event.created_at.isoformat())
    )


@router.get("/user/{user_id}/events", response_model=UserEventListResponse)
async def get_user_events(
    user_id: str,
    start_date: Optional[str] = Query(None, description="开始日期（ISO 8601格式）"),
    end_date: Optional[str] = Query(None, description="结束日期（ISO 8601格式）"),
    event_type: Optional[str] = Query(None, description="事件类型过滤"),
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    db: Session = Depends(get_db)
):
    """
    获取用户事件列表

    支持按日期范围和事件类型过滤。
    """
    profile_mgr = ProfileManager(db)

    parsed_start = None
    parsed_end = None

    if start_date:
        try:
            parsed_start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的开始日期格式")

    if end_date:
        try:
            parsed_end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的结束日期格式")

    events = profile_mgr.get_user_events(
        user_id=user_id,
        start_date=parsed_start,
        end_date=parsed_end,
        event_type=event_type,
        limit=limit
    )

    events_response = [
        UserEventResponse(
            id=str(event.id),
            user_id=event.user_id,
            event_type=event.event_type,
            event_date=str(event.event_date.isoformat()),
            event_description=event.event_description,
            related_session_id=str(event.related_session_id) if event.related_session_id else None,
            metadata=event.event_metadata or {},
            created_at=str(event.created_at.isoformat())
        )
        for event in events
    ]

    return UserEventListResponse(
        events=events_response,
        total=len(events_response)
    )


@router.delete("/user/{user_id}/events/{event_id}", response_model=MessageResponse)
async def delete_user_event(
    user_id: str,
    event_id: str,
    db: Session = Depends(get_db)
):
    """
    删除用户事件
    """
    profile_mgr = ProfileManager(db)
    success = profile_mgr.delete_user_event(event_id)

    if not success:
        raise HTTPException(status_code=404, detail="事件不存在")

    return MessageResponse(message="事件已删除")


# ========================================
# 关注点
# ========================================

@router.post("/user/{user_id}/concerns", response_model=ConcernPointResponse)
async def create_concern_point(
    user_id: str,
    request: ConcernPointCreateRequest,
    db: Session = Depends(get_db)
):
    """
    上报用户关注点

    关注点可以是用户自己发现的口腔问题，也可以是系统检测到的。
    """
    profile_mgr = ProfileManager(db)

    concern = profile_mgr.add_concern_point(
        user_id=user_id,
        concern_type=request.concern_type,
        source_type=request.source_type,
        zone_id=request.zone_id,
        location_description=request.location_description,
        concern_description=request.concern_description,
        severity=request.severity
    )

    return ConcernPointResponse(
        id=str(concern.id),
        user_id=concern.user_id,
        source_type=concern.source_type,
        zone_id=concern.zone_id,
        location_description=concern.location_description,
        concern_type=concern.concern_type,
        concern_description=concern.concern_description,
        severity=concern.severity,
        status=concern.status,
        first_detected_at=str(concern.first_detected_at.isoformat()),
        last_observed_at=str(concern.last_observed_at.isoformat()),
        resolved_at=str(concern.resolved_at.isoformat()) if concern.resolved_at else None,
        related_sessions=concern.related_sessions or [],
        evidence_frame_ids=concern.evidence_frame_ids or [],
        created_at=str(concern.created_at.isoformat()),
        updated_at=str(concern.updated_at.isoformat()) if concern.updated_at else str(concern.created_at.isoformat())
    )


@router.get("/user/{user_id}/concerns", response_model=ConcernPointListResponse)
async def get_user_concerns(
    user_id: str,
    status: Optional[str] = Query(None, description="状态过滤：active/resolved/monitoring"),
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    db: Session = Depends(get_db)
):
    """
    获取用户关注点列表

    支持按状态过滤。
    """
    profile_mgr = ProfileManager(db)

    concerns = profile_mgr.get_all_concerns(
        user_id=user_id,
        status=status,
        limit=limit
    )

    concerns_response = [
        ConcernPointResponse(
            id=str(concern.id),
            user_id=concern.user_id,
            source_type=concern.source_type,
            zone_id=concern.zone_id,
            location_description=concern.location_description,
            concern_type=concern.concern_type,
            concern_description=concern.concern_description,
            severity=concern.severity,
            status=concern.status,
            first_detected_at=str(concern.first_detected_at.isoformat()),
            last_observed_at=str(concern.last_observed_at.isoformat()),
            resolved_at=str(concern.resolved_at.isoformat()) if concern.resolved_at else None,
            related_sessions=concern.related_sessions or [],
            evidence_frame_ids=concern.evidence_frame_ids or [],
            created_at=str(concern.created_at.isoformat()),
            updated_at=str(concern.updated_at.isoformat()) if concern.updated_at else str(concern.created_at.isoformat())
        )
        for concern in concerns
    ]

    return ConcernPointListResponse(
        concerns=concerns_response,
        total=len(concerns_response)
    )


@router.patch("/user/{user_id}/concerns/{concern_id}/status", response_model=ConcernPointResponse)
async def update_concern_status(
    user_id: str,
    concern_id: str,
    request: ConcernStatusUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    更新关注点状态

    可将状态更新为：
    - active: 活跃
    - resolved: 已解决
    - monitoring: 持续监控中
    """
    profile_mgr = ProfileManager(db)

    concern = profile_mgr.update_concern_status(
        concern_id=concern_id,
        new_status=request.status,
        session_id=request.related_session_id
    )

    if not concern:
        raise HTTPException(status_code=404, detail="关注点不存在")

    return ConcernPointResponse(
        id=str(concern.id),
        user_id=concern.user_id,
        source_type=concern.source_type,
        zone_id=concern.zone_id,
        location_description=concern.location_description,
        concern_type=concern.concern_type,
        concern_description=concern.concern_description,
        severity=concern.severity,
        status=concern.status,
        first_detected_at=str(concern.first_detected_at.isoformat()),
        last_observed_at=str(concern.last_observed_at.isoformat()),
        resolved_at=str(concern.resolved_at.isoformat()) if concern.resolved_at else None,
        related_sessions=concern.related_sessions or [],
        evidence_frame_ids=concern.evidence_frame_ids or [],
        created_at=str(concern.created_at.isoformat()),
        updated_at=str(concern.updated_at.isoformat()) if concern.updated_at else str(concern.created_at.isoformat())
    )


# ========================================
# 时间轴
# ========================================

@router.get("/user/{user_id}/timeline", response_model=TimelineResponse)
async def get_user_timeline(
    user_id: str,
    period: str = Query("month", description="查询周期：week/month/quarter/year/all"),
    start_date: Optional[str] = Query(None, description="自定义开始日期（ISO 8601格式）"),
    end_date: Optional[str] = Query(None, description="自定义结束日期（ISO 8601格式）"),
    db: Session = Depends(get_db)
):
    """
    获取用户时间轴

    时间轴整合了用户的所有活动，包括：
    - 检查记录（Quick Check / 基线采集）
    - 用户事件（洁牙、治疗等）
    - 关注点变化（发现、解决）
    """
    profile_mgr = ProfileManager(db)

    parsed_start = None
    parsed_end = None

    if start_date:
        try:
            parsed_start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的开始日期格式")

    if end_date:
        try:
            parsed_end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的结束日期格式")

    timeline_data = profile_mgr.get_timeline(
        user_id=user_id,
        period=period,
        start_date=parsed_start,
        end_date=parsed_end
    )

    return TimelineResponse(
        user_id=timeline_data["user_id"],
        period=timeline_data["period"],
        start_date=timeline_data["start_date"],
        end_date=timeline_data["end_date"],
        events=timeline_data["events"],
        total=timeline_data["total"]
    )
