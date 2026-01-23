# -*- coding: utf-8 -*-
"""
用户档案管理
管理用户的基线数据和 Quick Check 记录
"""
from datetime import datetime
from typing import Optional, Dict
from sqlalchemy.orm import Session

from app.models.database import AUserProfile, ASession


class ProfileManager:
    """用户档案管理器"""

    def __init__(self, db: Session):
        """
        初始化管理器

        Args:
            db: 数据库会话
        """
        self.db = db

    def get_or_create_profile(self, user_id: str) -> AUserProfile:
        """
        获取或创建用户档案

        Args:
            user_id: 用户ID

        Returns:
            用户档案对象
        """
        profile = self.db.query(AUserProfile).filter_by(user_id=user_id).first()

        if not profile:
            profile = AUserProfile(user_id=user_id)
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
            print(f"[档案] 创建新用户档案: {user_id}")

        return profile

    def mark_baseline_completed(self, user_id: str, zone_id: int, session_id: str):
        """
        标记用户的某个区域基线已完成

        Args:
            user_id: 用户ID
            zone_id: 区域ID (1-7)
            session_id: 基线 Session ID
        """
        profile = self.get_or_create_profile(user_id)

        # 更新基线映射
        baseline_map = profile.baseline_zone_map or {}
        baseline_map[str(zone_id)] = str(session_id)
        profile.baseline_zone_map = baseline_map

        # 检查是否所有7个区域都已完成
        if len(baseline_map) == 7:
            profile.baseline_completed = True
            profile.baseline_completion_date = datetime.utcnow()
            print(f"[档案] 用户 {user_id} 已完成所有7个区域的基线！")

        self.db.commit()
        print(f"[档案] 用户 {user_id} 区域 {zone_id} 基线已标记完成")

    def record_quick_check(self, user_id: str):
        """
        记录一次 Quick Check

        Args:
            user_id: 用户ID
        """
        profile = self.get_or_create_profile(user_id)
        profile.total_quick_checks += 1
        profile.last_check_date = datetime.utcnow()
        self.db.commit()

    def get_baseline_session(self, user_id: str, zone_id: int) -> Optional[str]:
        """
        获取用户某个区域的基线 Session ID

        Args:
            user_id: 用户ID
            zone_id: 区域ID

        Returns:
            基线 Session ID 或 None
        """
        profile = self.get_or_create_profile(user_id)
        baseline_map = profile.baseline_zone_map or {}
        return baseline_map.get(str(zone_id))

    def is_baseline_completed(self, user_id: str) -> bool:
        """
        检查用户是否已完成基线

        Args:
            user_id: 用户ID

        Returns:
            是否已完成基线
        """
        profile = self.get_or_create_profile(user_id)
        return profile.baseline_completed
