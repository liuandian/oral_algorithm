# -*- coding: utf-8 -*-
"""
EvidencePack 生成器 - 增强版
适配最新的 KeyframeData 模型，支持基线匹配、用户事件和关注点
"""
import json
from typing import List, Optional, Dict
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.database import (
    ASession, AKeyframe, AEvidencePack, 
    AUserEvent, AConcernPoint, AUserProfile
)
from app.models.evidence_pack import (
    EvidencePack, KeyframeData, FrameMetaTags, BaselineReference,
    UserEventData, ConcernPointData, UserHistorySummary,
    ZONE_DISPLAY_NAMES
)
from app.core.frame_matcher import FrameMatcherService


class EvidencePackError(Exception):
    """EvidencePack 生成异常"""
    pass


class EvidencePackGenerator:
    """EvidencePack 生成器"""

    # 事件类型显示名称映射
    EVENT_TYPE_DISPLAY_MAP: Dict[str, str] = {
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

    def __init__(self, db: Session):
        self.db = db
        self.frame_matcher = FrameMatcherService(db)

    def generate_evidence_pack(self, session_id: str) -> EvidencePack:
        """
        为指定 Session 生成 EvidencePack
        """
        print(f"[EvidencePack] 开始生成: session_id={session_id}")

        # 第一步：查询 Session
        session = self.db.query(ASession).filter_by(id=session_id).first()
        if not session:
            raise EvidencePackError(f"Session 不存在: {session_id}")

        # 第二步：查询所有关键帧（按帧索引排序）
        keyframes = (
            self.db.query(AKeyframe)
            .filter_by(session_id=session_id)
            .order_by(AKeyframe.frame_index)
            .all()
        )

        if not keyframes:
            raise EvidencePackError(f"Session 没有关键帧数据: {session_id}")

        print(f"[EvidencePack] 找到 {len(keyframes)} 个关键帧")

        # 第三步：转换为 KeyframeData
        frame_data_list: List[KeyframeData] = []

        for kf in keyframes:
            # 确认图像文件存在
            image_path = Path(kf.image_path)
            if not image_path.exists():
                print(f"[警告] 关键帧图像不存在: {image_path}")
                # 即使文件临时缺失，只要数据库有记录，我们仍生成元数据，但标记警告
            
            # 构建 FrameMetaTags
            # 数据库中 meta_tags 可能是 dict 或 JSON 字符串，需处理
            tags_source = kf.meta_tags
            if isinstance(tags_source, str):
                try:
                    tags_dict = json.loads(tags_source)
                except:
                    tags_dict = {}
            elif isinstance(tags_source, dict):
                tags_dict = tags_source
            else:
                tags_dict = {}

            meta_tags = FrameMetaTags(**tags_dict)

            # 构建 KeyframeData
            # 修正：使用 kf.id (UUID) 作为 frame_id
            # 修正：使用 kf.image_path 作为 image_url (本地路径)
            # 修正：timestamp 格式现已兼容 00:00.00
            frame_data = KeyframeData(
                frame_id=str(kf.id),
                timestamp=kf.timestamp_in_video,
                image_url=str(kf.image_path),
                extraction_strategy=kf.extraction_strategy,
                extraction_reason=kf.extraction_reason,
                anomaly_score=kf.anomaly_score,
                meta_tags=meta_tags
            )

            frame_data_list.append(frame_data)

        if not frame_data_list:
            raise EvidencePackError("没有有效的关键帧数据")

        # 第四步：如果是 Quick Check，构建基线参考（使用简化方法：每区域取中间帧）
        baseline_reference: Optional[BaselineReference] = None
        comparison_mode = "none"

        if session.session_type == "quick_check":
            # 使用简化方法：每个区域选择中间帧作为基线
            baseline_reference, middle_frames = self.frame_matcher.build_baseline_reference_simple(
                user_id=session.user_id
            )
            comparison_mode = baseline_reference.comparison_mode if baseline_reference else "none"
            print(f"[EvidencePack] 基线参考构建完成: comparison_mode={comparison_mode}, "
                  f"覆盖 {len(middle_frames) if middle_frames else 0}/7 区域")

        # 第五步：构建用户历史摘要（事件和关注点）
        user_history = self._build_user_history(session.user_id, session_id)
        print(f"[EvidencePack] 用户历史摘要: {user_history.total_events} 个事件, "
              f"{len(user_history.active_concerns)} 个活跃关注点")

        # 第六步：构建 EvidencePack
        evidence_pack = EvidencePack(
            session_id=str(session.id),
            user_id=session.user_id,
            session_type=session.session_type,
            zone_id=session.zone_id,
            created_at=str(session.created_at.isoformat()),
            total_frames=len(frame_data_list),
            frames=frame_data_list,
            baseline_reference=baseline_reference,
            user_history=user_history
        )

        print(f"[EvidencePack] EvidencePack 构建完成，包含 {len(frame_data_list)} 帧")

        # 第六步：保存到数据库
        # 检查是否已存在
        existing_pack = self.db.query(AEvidencePack).filter_by(session_id=session.id).first()
        baseline_ref_json = baseline_reference.model_dump() if baseline_reference else None

        if existing_pack:
            print(f"[EvidencePack] 更新已存在的 EvidencePack: {existing_pack.id}")
            existing_pack.pack_json = evidence_pack.model_dump()
            existing_pack.total_frames = len(frame_data_list)
            existing_pack.baseline_reference_json = baseline_ref_json
            existing_pack.comparison_mode = comparison_mode
            self.db.add(existing_pack)
        else:
            db_evidence_pack = AEvidencePack(
                session_id=session.id,
                pack_json=evidence_pack.model_dump(),
                total_frames=len(frame_data_list),
                baseline_reference_json=baseline_ref_json,
                comparison_mode=comparison_mode
            )
            self.db.add(db_evidence_pack)
            print(f"[EvidencePack] 创建新的 EvidencePack")

        self.db.commit()

        return evidence_pack

    def get_evidence_pack_by_session(self, session_id: str) -> EvidencePack:
        """
        从数据库获取已生成的 EvidencePack
        """
        db_pack = (
            self.db.query(AEvidencePack)
            .filter_by(session_id=session_id)
            .first()
        )

        if not db_pack:
            raise EvidencePackError(f"EvidencePack 不存在: {session_id}")

        return EvidencePack(**db_pack.pack_json)

    def export_evidence_pack_json(self, session_id: str, output_path: str) -> Path:
        """
        导出 EvidencePack 为 JSON 文件
        """
        evidence_pack = self.get_evidence_pack_by_session(session_id)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(evidence_pack.model_dump_json(indent=2))

        print(f"[EvidencePack] 已导出 JSON: {output_path}")
        return output_path

    def _build_user_history(self, user_id: str, current_session_id: str) -> UserHistorySummary:
        """
        构建用户历史摘要（事件和关注点）
        
        Args:
            user_id: 用户ID
            current_session_id: 当前Session ID（用于计算距上次检查天数）
            
        Returns:
            UserHistorySummary 对象
        """
        now = datetime.now()
        year_ago = now - timedelta(days=360)
        
        # 1. 查询近期事件（最近12个月）
        recent_events = (
            self.db.query(AUserEvent)
            .filter_by(user_id=user_id)
            .filter(AUserEvent.event_date >= year_ago)
            .order_by(AUserEvent.event_date.desc())
            .all()
        )
        
        # 2. 查询所有关注点
        all_concerns = (
            self.db.query(AConcernPoint)
            .filter_by(user_id=user_id)
            .all()
        )
        
        # 3. 构建事件数据列表
        event_data_list: List[UserEventData] = []
        for event in recent_events:
            event_date = event.event_date
            if isinstance(event_date, str):
                event_date = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
            
            days_since = (now - event_date).days
            
            event_data = UserEventData(
                event_id=str(event.id),
                event_type=event.event_type,
                event_type_display=self.EVENT_TYPE_DISPLAY_MAP.get(event.event_type, event.event_type),
                event_date=event_date.isoformat(),
                event_description=event.event_description,
                related_session_id=str(event.related_session_id) if event.related_session_id else None,
                metadata=event.event_metadata or {},
                days_since_event=days_since
            )
            event_data_list.append(event_data)
        
        # 4. 构建关注点数据列表（只包含活跃的）
        active_concerns: List[ConcernPointData] = []
        resolved_count = 0
        monitoring_count = 0
        
        for concern in all_concerns:
            # 统计各状态数量
            if concern.status == "resolved":
                resolved_count += 1
            elif concern.status == "monitoring":
                monitoring_count += 1
            
            # 只将活跃和监控中的关注点加入列表
            if concern.status in ["active", "monitoring"]:
                first_detected = concern.first_detected_at
                if isinstance(first_detected, str):
                    first_detected = datetime.fromisoformat(first_detected.replace('Z', '+00:00'))
                
                days_since_first = (now - first_detected).days
                
                concern_data = ConcernPointData(
                    concern_id=str(concern.id),
                    source_type=concern.source_type,
                    zone_id=concern.zone_id,
                    zone_display_name=ZONE_DISPLAY_NAMES.get(concern.zone_id) if concern.zone_id else None,
                    location_description=concern.location_description,
                    concern_type=concern.concern_type,
                    concern_description=concern.concern_description,
                    severity=concern.severity,
                    status=concern.status,
                    first_detected_at=first_detected.isoformat(),
                    last_observed_at=concern.last_observed_at.isoformat() if concern.last_observed_at else first_detected.isoformat(),
                    days_since_first=days_since_first,
                    related_sessions_count=len(concern.related_sessions) if concern.related_sessions else 0
                )
                active_concerns.append(concern_data)
        
        # 5. 计算距上次检查天数
        days_since_last_check = None
        last_session = (
            self.db.query(ASession)
            .filter_by(user_id=user_id)
            .filter(ASession.id != current_session_id)
            .filter(ASession.processing_status == "completed")
            .order_by(ASession.created_at.desc())
            .first()
        )
        if last_session and last_session.created_at:
            last_check = last_session.created_at
            if isinstance(last_check, str):
                last_check = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
            days_since_last_check = (now - last_check).days
        
        # 6. 计算距上次事件天数
        days_since_last_event = None
        if recent_events and recent_events[0].event_date:
            last_event_date = recent_events[0].event_date
            if isinstance(last_event_date, str):
                last_event_date = datetime.fromisoformat(last_event_date.replace('Z', '+00:00'))
            days_since_last_event = (now - last_event_date).days
        
        return UserHistorySummary(
            total_events=len(recent_events),
            recent_events=event_data_list,
            active_concerns=active_concerns,
            resolved_concerns_count=resolved_count,
            monitoring_concerns_count=monitoring_count,
            days_since_last_check=days_since_last_check,
            days_since_last_event=days_since_last_event
        )

    def _build_baseline_reference(
        self,
        user_id: str,
        quick_check_keyframes: List[AKeyframe],
        frame_data_list: List[KeyframeData]
    ) -> Optional[BaselineReference]:
        """
        构建基线参考数据

        Args:
            user_id: 用户ID
            quick_check_keyframes: Quick Check 关键帧（数据库对象）
            frame_data_list: 帧数据列表（Pydantic对象）

        Returns:
            BaselineReference 对象
        """
        # 使用 FrameMatcherService 进行匹配
        baseline_ref = self.frame_matcher.build_baseline_reference(
            user_id=user_id,
            quick_check_frames=quick_check_keyframes
        )

        # 更新 frame_data_list 中的 matched_baseline_frame_id
        if baseline_ref.has_baseline and baseline_ref.matched_baseline_frames:
            # 通过 FrameMatcherService 获取详细匹配
            matches = self.frame_matcher.match_frames_to_baseline(
                quick_check_frames=quick_check_keyframes,
                user_id=user_id
            )

            # 更新每个帧的 matched_baseline_frame_id
            for frame_data in frame_data_list:
                if frame_data.frame_id in matches:
                    frame_data.matched_baseline_frame_id = matches[frame_data.frame_id].baseline_frame_id

        return baseline_ref