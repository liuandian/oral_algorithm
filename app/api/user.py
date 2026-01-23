# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.schemas import UserProfileResponse, BaselineZoneInfo
from app.core.profile_manager import ProfileManager

router = APIRouter()

@router.get("/user/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(user_id: str, db: Session = Depends(get_db)):
    """
    获取用户完整档案
    """
    profile_mgr = ProfileManager(db)
    profile = profile_mgr.get_or_create_profile(user_id)

    # 转换基线信息格式
    baseline_zones = []
    if profile.baseline_zone_map:
        for zone_id_str, session_id in profile.baseline_zone_map.items():
            # 这里简化处理，实际可以通过session_id查具体的完成时间
            # V1阶段使用profile更新时间或session创建时间
            baseline_zones.append(
                BaselineZoneInfo(
                    zone_id=int(zone_id_str),
                    session_id=session_id,
                    completed_at=str(profile.updated_at) 
                )
            )

    return UserProfileResponse(
        user_id=profile.user_id,
        baseline_completed=profile.baseline_completed,
        baseline_completion_date=str(profile.baseline_completion_date) if profile.baseline_completion_date else None,
        baseline_zones=baseline_zones,
        total_quick_checks=profile.total_quick_checks,
        last_check_date=str(profile.last_check_date) if profile.last_check_date else None,
        created_at=str(profile.created_at)
    )