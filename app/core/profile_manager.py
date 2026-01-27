# -*- coding: utf-8 -*-
"""
用户档案管理
管理用户的基线数据、Quick Check 记录、事件和关注点
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import and_, or_

from app.models.database import AUserProfile, ASession, AUserEvent, AConcernPoint


class ProfileManagerError(Exception):
    """档案管理器异常"""
    pass


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

        # 更新基线映射 - 创建新字典副本以确保 SQLAlchemy 检测到变化
        baseline_map = dict(profile.baseline_zone_map or {})
        baseline_map[str(zone_id)] = str(session_id)
        profile.baseline_zone_map = baseline_map

        # 显式标记 JSONB 字段已修改
        flag_modified(profile, "baseline_zone_map")

        # 检查是否所有7个区域都已完成
        if len(baseline_map) == 7:
            profile.baseline_completed = True
            profile.baseline_completion_date = datetime.now()
            print(f"[档案] 用户 {user_id} 已完成所有7个区域的基线！")

        self.db.commit()
        print(f"[档案] 用户 {user_id} 区域 {zone_id} 基线已标记完成, 当前进度: {len(baseline_map)}/7")

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

    # ========================================
    # 用户事件管理
    # ========================================

    def add_user_event(
        self,
        user_id: str,
        event_type: str,
        event_date: datetime,
        event_description: Optional[str] = None,
        related_session_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> AUserEvent:
        """
        添加用户事件

        Args:
            user_id: 用户ID
            event_type: 事件类型
            event_date: 事件日期
            event_description: 事件描述
            related_session_id: 关联的Session ID
            metadata: 附加元数据

        Returns:
            创建的事件对象
        """
        # 确保用户档案存在
        self.get_or_create_profile(user_id)

        event = AUserEvent(
            user_id=user_id,
            event_type=event_type,
            event_date=event_date,
            event_description=event_description,
            related_session_id=related_session_id,
            event_metadata=metadata or {}
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        print(f"[档案] 用户 {user_id} 添加事件: {event_type}")
        return event

    def get_user_events(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_type: Optional[str] = None,
        limit: int = 50
    ) -> List[AUserEvent]:
        """
        获取用户事件列表

        Args:
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期
            event_type: 事件类型过滤
            limit: 返回数量限制

        Returns:
            事件列表
        """
        query = self.db.query(AUserEvent).filter_by(user_id=user_id)

        if start_date:
            query = query.filter(AUserEvent.event_date >= start_date)
        if end_date:
            query = query.filter(AUserEvent.event_date <= end_date)
        if event_type:
            query = query.filter(AUserEvent.event_type == event_type)

        return query.order_by(AUserEvent.event_date.desc()).limit(limit).all()

    def delete_user_event(self, event_id: str) -> bool:
        """
        删除用户事件

        Args:
            event_id: 事件ID

        Returns:
            是否删除成功
        """
        event = self.db.query(AUserEvent).filter_by(id=event_id).first()
        if event:
            self.db.delete(event)
            self.db.commit()
            return True
        return False

    # ========================================
    # 关注点管理
    # ========================================

    def add_concern_point(
        self,
        user_id: str,
        concern_type: str,
        source_type: str = "user_reported",
        zone_id: Optional[int] = None,
        location_description: Optional[str] = None,
        concern_description: Optional[str] = None,
        severity: str = "mild",
        session_id: Optional[str] = None,
        frame_ids: Optional[List[str]] = None
    ) -> AConcernPoint:
        """
        添加关注点

        Args:
            user_id: 用户ID
            concern_type: 关注点类型
            source_type: 来源类型 (user_reported/system_detected)
            zone_id: 分区ID
            location_description: 位置描述
            concern_description: 详细描述
            severity: 严重程度 (mild/moderate/severe)
            session_id: 关联的Session ID
            frame_ids: 证据帧ID列表

        Returns:
            创建的关注点对象
        """
        # 确保用户档案存在
        self.get_or_create_profile(user_id)

        now = datetime.now()
        concern = AConcernPoint(
            user_id=user_id,
            source_type=source_type,
            zone_id=zone_id,
            location_description=location_description,
            concern_type=concern_type,
            concern_description=concern_description,
            severity=severity,
            status="active",
            first_detected_at=now,
            last_observed_at=now,
            related_sessions=[session_id] if session_id else [],
            evidence_frame_ids=frame_ids or []
        )
        self.db.add(concern)
        self.db.commit()
        self.db.refresh(concern)

        print(f"[档案] 用户 {user_id} 添加关注点: {concern_type}")
        return concern

    def update_concern_status(
        self,
        concern_id: str,
        new_status: str,
        session_id: Optional[str] = None
    ) -> Optional[AConcernPoint]:
        """
        更新关注点状态

        Args:
            concern_id: 关注点ID
            new_status: 新状态 (active/resolved/monitoring)
            session_id: 关联的Session ID

        Returns:
            更新后的关注点对象，如果不存在返回 None
        """
        concern = self.db.query(AConcernPoint).filter_by(id=concern_id).first()
        if not concern:
            return None

        concern.status = new_status
        concern.last_observed_at = datetime.now()

        if new_status == "resolved":
            concern.resolved_at = datetime.now()

        if session_id:
            sessions = concern.related_sessions or []
            if session_id not in sessions:
                sessions.append(session_id)
                concern.related_sessions = sessions

        self.db.commit()
        self.db.refresh(concern)

        print(f"[档案] 更新关注点 {concern_id} 状态为: {new_status}")
        return concern

    def get_active_concerns(self, user_id: str) -> List[AConcernPoint]:
        """
        获取用户活跃的关注点

        Args:
            user_id: 用户ID

        Returns:
            活跃关注点列表
        """
        return (
            self.db.query(AConcernPoint)
            .filter_by(user_id=user_id)
            .filter(AConcernPoint.status.in_(["active", "monitoring"]))
            .order_by(AConcernPoint.last_observed_at.desc())
            .all()
        )

    def get_all_concerns(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[AConcernPoint]:
        """
        获取用户所有关注点

        Args:
            user_id: 用户ID
            status: 状态过滤
            limit: 返回数量限制

        Returns:
            关注点列表
        """
        query = self.db.query(AConcernPoint).filter_by(user_id=user_id)

        if status:
            query = query.filter(AConcernPoint.status == status)

        return query.order_by(AConcernPoint.last_observed_at.desc()).limit(limit).all()

    def update_concern_observation(
        self,
        concern_id: str,
        session_id: Optional[str] = None,
        frame_ids: Optional[List[str]] = None
    ) -> Optional[AConcernPoint]:
        """
        更新关注点的观察记录

        Args:
            concern_id: 关注点ID
            session_id: Session ID
            frame_ids: 帧ID列表

        Returns:
            更新后的关注点对象
        """
        concern = self.db.query(AConcernPoint).filter_by(id=concern_id).first()
        if not concern:
            return None

        concern.last_observed_at = datetime.now()

        if session_id:
            sessions = concern.related_sessions or []
            if session_id not in sessions:
                sessions.append(session_id)
                concern.related_sessions = sessions

        if frame_ids:
            existing_frames = concern.evidence_frame_ids or []
            for fid in frame_ids:
                if fid not in existing_frames:
                    existing_frames.append(fid)
            concern.evidence_frame_ids = existing_frames

        self.db.commit()
        self.db.refresh(concern)

        return concern

    # ========================================
    # 时间轴查询
    # ========================================

    def get_timeline(
        self,
        user_id: str,
        period: str = "month",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        获取用户时间轴

        Args:
            user_id: 用户ID
            period: 查询周期 (week/month/quarter/year/all)
            start_date: 自定义开始日期
            end_date: 自定义结束日期

        Returns:
            时间轴数据字典
        """
        now = datetime.now()

        # 计算日期范围
        if start_date is None or end_date is None:
            if period == "week":
                start_date = now - timedelta(days=7)
            elif period == "month":
                start_date = now - timedelta(days=30)
            elif period == "quarter":
                start_date = now - timedelta(days=90)
            elif period == "year":
                start_date = now - timedelta(days=365)
            else:  # all
                start_date = datetime(2020, 1, 1)
            end_date = now

        events_list = []

        # 获取 Sessions
        sessions = (
            self.db.query(ASession)
            .filter_by(user_id=user_id)
            .filter(ASession.created_at >= start_date)
            .filter(ASession.created_at <= end_date)
            .order_by(ASession.created_at.desc())
            .all()
        )

        for session in sessions:
            session_type_display = "快速检查" if session.session_type == "quick_check" else f"基线采集 Zone {session.zone_id}"
            events_list.append({
                "event_type": "session",
                "event_id": str(session.id),
                "event_date": str(session.created_at.isoformat()),
                "title": session_type_display,
                "description": f"状态: {session.processing_status}",
                "metadata": {
                    "session_type": session.session_type,
                    "zone_id": session.zone_id,
                    "processing_status": session.processing_status
                }
            })

        # 获取用户事件
        user_events = self.get_user_events(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )

        for event in user_events:
            events_list.append({
                "event_type": "user_event",
                "event_id": str(event.id),
                "event_date": str(event.event_date.isoformat()),
                "title": self._get_event_type_display(event.event_type),
                "description": event.event_description,
                "metadata": event.event_metadata or {}
            })

        # 获取关注点变更
        concerns = (
            self.db.query(AConcernPoint)
            .filter_by(user_id=user_id)
            .filter(
                or_(
                    and_(AConcernPoint.first_detected_at >= start_date, AConcernPoint.first_detected_at <= end_date),
                    and_(AConcernPoint.resolved_at >= start_date, AConcernPoint.resolved_at <= end_date)
                )
            )
            .all()
        )

        for concern in concerns:
            # 首次发现
            if concern.first_detected_at and start_date <= concern.first_detected_at <= end_date:
                events_list.append({
                    "event_type": "concern_detected",
                    "event_id": str(concern.id),
                    "event_date": str(concern.first_detected_at.isoformat()),
                    "title": f"发现问题: {concern.concern_type}",
                    "description": concern.location_description or concern.concern_description,
                    "metadata": {
                        "severity": concern.severity,
                        "zone_id": concern.zone_id
                    }
                })

            # 解决
            if concern.resolved_at and start_date <= concern.resolved_at <= end_date:
                events_list.append({
                    "event_type": "concern_resolved",
                    "event_id": str(concern.id),
                    "event_date": str(concern.resolved_at.isoformat()),
                    "title": f"问题解决: {concern.concern_type}",
                    "description": concern.location_description,
                    "metadata": {
                        "zone_id": concern.zone_id
                    }
                })

        # 按日期排序
        events_list.sort(key=lambda x: x["event_date"], reverse=True)

        return {
            "user_id": user_id,
            "period": period,
            "start_date": str(start_date.isoformat()),
            "end_date": str(end_date.isoformat()),
            "events": events_list,
            "total": len(events_list)
        }

    def _get_event_type_display(self, event_type: str) -> str:
        """获取事件类型的显示名称"""
        display_map = {
            "dental_cleaning": "洁牙",
            "scaling": "洗牙/龈下刮治",
            "filling": "补牙",
            "extraction": "拔牙",
            "crown": "牙冠/烤瓷牙",
            "orthodontic": "正畸调整",
            "whitening": "美白",
            "checkup": "口腔检查",
            "other": "其他"
        }
        return display_map.get(event_type, event_type)

    def get_extended_profile(self, user_id: str) -> Dict:
        """
        获取扩展用户档案信息

        Args:
            user_id: 用户ID

        Returns:
            扩展档案信息字典
        """
        profile = self.get_or_create_profile(user_id)

        # 统计活跃关注点
        active_concerns_count = (
            self.db.query(AConcernPoint)
            .filter_by(user_id=user_id)
            .filter(AConcernPoint.status.in_(["active", "monitoring"]))
            .count()
        )

        # 统计近30天事件
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_events_count = (
            self.db.query(AUserEvent)
            .filter_by(user_id=user_id)
            .filter(AUserEvent.event_date >= thirty_days_ago)
            .count()
        )

        return {
            "user_id": profile.user_id,
            "baseline_completed": profile.baseline_completed,
            "baseline_completion_date": str(profile.baseline_completion_date.isoformat()) if profile.baseline_completion_date else None,
            "baseline_zone_map": profile.baseline_zone_map or {},
            "total_quick_checks": profile.total_quick_checks,
            "last_check_date": str(profile.last_check_date.isoformat()) if profile.last_check_date else None,
            "total_baseline_updates": profile.total_baseline_updates or 0,
            "last_baseline_update_date": str(profile.last_baseline_update_date.isoformat()) if profile.last_baseline_update_date else None,
            "active_concerns_count": active_concerns_count,
            "recent_events_count": recent_events_count,
            "created_at": str(profile.created_at.isoformat()),
            "updated_at": str(profile.updated_at.isoformat()) if profile.updated_at else None
        }
