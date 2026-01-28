# -*- coding: utf-8 -*-
"""
帧匹配服务
基于结构化标签匹配 Quick Check 帧与基线帧
"""
from typing import List, Dict, Optional, Tuple
import json
from sqlalchemy.orm import Session

from app.models.database import AKeyframe, ASession, AUserProfile
from app.models.evidence_pack import (
    FrameMetaTags,
    BaselineFrameReference,
    BaselineReference,
    ToothSide,
    ToothType,
    Region,
    ZONE_ID_MAP,
    ZONE_DISPLAY_NAMES
)


class FrameMatcherError(Exception):
    """帧匹配服务异常"""
    pass


class FrameMatcherService:
    """帧匹配服务：匹配 Quick Check 帧与基线帧"""

    # 结构化标签匹配权重
    WEIGHT_SIDE = 0.35
    WEIGHT_TOOTH_TYPE = 0.35
    WEIGHT_REGION = 0.30

    # 匹配阈值
    MIN_MATCH_SCORE = 0.5

    def __init__(self, db: Session):
        """
        初始化服务

        Args:
            db: 数据库会话
        """
        self.db = db

    def match_frames_to_baseline(
        self,
        quick_check_frames: List[AKeyframe],
        user_id: str
    ) -> Dict[str, BaselineFrameReference]:
        """
        基于 meta_tags 结构化匹配 Quick Check 帧与基线帧

        Args:
            quick_check_frames: Quick Check 关键帧列表
            user_id: 用户ID

        Returns:
            匹配结果字典：{quick_check_frame_id: BaselineFrameReference}
        """
        print(f"[FrameMatcher] 开始匹配帧: user_id={user_id}, qc_frames={len(quick_check_frames)}")

        # 获取用户所有基线帧
        baseline_frames_by_zone = self._get_user_baseline_frames(user_id)

        if not baseline_frames_by_zone:
            print(f"[FrameMatcher] 用户没有基线帧数据")
            return {}

        matches: Dict[str, BaselineFrameReference] = {}

        for qc_frame in quick_check_frames:
            best_match = self._find_best_baseline_match(qc_frame, baseline_frames_by_zone)
            if best_match:
                matches[str(qc_frame.id)] = best_match

        print(f"[FrameMatcher] 匹配完成: 匹配到 {len(matches)}/{len(quick_check_frames)} 帧")
        return matches

    def build_baseline_reference(
        self,
        user_id: str,
        quick_check_frames: List[AKeyframe]
    ) -> BaselineReference:
        """
        构建基线参考数据

        Args:
            user_id: 用户ID
            quick_check_frames: Quick Check 关键帧列表

        Returns:
            BaselineReference 对象
        """
        # 获取用户档案
        profile = self.db.query(AUserProfile).filter_by(user_id=user_id).first()

        if not profile or not profile.baseline_completed:
            return BaselineReference(
                has_baseline=False,
                comparison_mode="none"
            )

        # 匹配帧
        matches = self.match_frames_to_baseline(quick_check_frames, user_id)

        # 确定对比模式
        if not matches:
            comparison_mode = "none"
        elif len(matches) < len(quick_check_frames) // 2:
            comparison_mode = "partial"
        else:
            comparison_mode = "full"

        return BaselineReference(
            has_baseline=True,
            baseline_completion_date=str(profile.baseline_completion_date.isoformat()) if profile.baseline_completion_date else None,
            matched_baseline_frames=list(matches.values()),
            comparison_mode=comparison_mode
        )

    def _get_user_baseline_frames(self, user_id: str) -> Dict[int, List[AKeyframe]]:
        """
        获取用户所有基线帧，按 zone_id 分组

        Args:
            user_id: 用户ID

        Returns:
            按 zone_id 分组的基线帧字典
        """
        # 查询所有基线 session
        baseline_sessions = (
            self.db.query(ASession)
            .filter_by(user_id=user_id, session_type="baseline")
            .filter(ASession.processing_status == "completed")
            .all()
        )

        if not baseline_sessions:
            return {}

        # 按 zone_id 分组
        frames_by_zone: Dict[int, List[AKeyframe]] = {}

        for session in baseline_sessions:
            zone_id = session.zone_id
            if zone_id is None:
                continue

            # 查询该 session 的所有关键帧
            keyframes = (
                self.db.query(AKeyframe)
                .filter_by(session_id=session.id)
                .order_by(AKeyframe.frame_index)
                .all()
            )

            if zone_id not in frames_by_zone:
                frames_by_zone[zone_id] = []

            frames_by_zone[zone_id].extend(keyframes)

        return frames_by_zone

    def _find_best_baseline_match(
        self,
        qc_frame: AKeyframe,
        baseline_frames_by_zone: Dict[int, List[AKeyframe]]
    ) -> Optional[BaselineFrameReference]:
        """
        为单个 Quick Check 帧找到最佳匹配的基线帧

        Args:
            qc_frame: Quick Check 关键帧
            baseline_frames_by_zone: 按 zone_id 分组的基线帧

        Returns:
            最佳匹配的 BaselineFrameReference，如果没有匹配返回 None
        """
        qc_tags = self._parse_meta_tags(qc_frame.meta_tags)
        best_score = 0.0
        best_match: Optional[Tuple[AKeyframe, int]] = None

        for zone_id, baseline_frames in baseline_frames_by_zone.items():
            for bl_frame in baseline_frames:
                bl_tags = self._parse_meta_tags(bl_frame.meta_tags)
                score = self._calculate_structural_match_score(qc_tags, bl_tags)

                if score > best_score and score >= self.MIN_MATCH_SCORE:
                    best_score = score
                    best_match = (bl_frame, zone_id)

        if not best_match:
            return None

        bl_frame, zone_id = best_match

        # 获取基线 session 信息
        bl_session = self.db.query(ASession).filter_by(id=bl_frame.session_id).first()

        return BaselineFrameReference(
            baseline_frame_id=str(bl_frame.id),
            baseline_session_id=str(bl_frame.session_id),
            baseline_zone_id=zone_id,
            baseline_timestamp=bl_frame.timestamp_in_video,
            baseline_image_url=bl_frame.image_path,
            baseline_created_at=str(bl_session.created_at.isoformat()) if bl_session else "",
            matching_score=best_score
        )

    def _parse_meta_tags(self, meta_tags_data) -> FrameMetaTags:
        """
        解析 meta_tags 数据

        Args:
            meta_tags_data: 数据库中的 meta_tags (dict 或 JSON 字符串)

        Returns:
            FrameMetaTags 对象
        """
        import json

        if isinstance(meta_tags_data, str):
            try:
                tags_dict = json.loads(meta_tags_data)
            except:
                tags_dict = {}
        elif isinstance(meta_tags_data, dict):
            tags_dict = meta_tags_data
        else:
            tags_dict = {}

        return FrameMetaTags(**tags_dict)

    def _calculate_structural_match_score(
        self,
        qc_tags: FrameMetaTags,
        baseline_tags: FrameMetaTags
    ) -> float:
        """
        计算结构化标签匹配得分

        Args:
            qc_tags: Quick Check 帧的标签
            baseline_tags: 基线帧的标签

        Returns:
            匹配得分 (0.0 - 1.0)
        """
        score = 0.0

        # 匹配 side
        if qc_tags.side == baseline_tags.side and qc_tags.side != ToothSide.UNKNOWN:
            score += self.WEIGHT_SIDE
        elif qc_tags.side == ToothSide.UNKNOWN or baseline_tags.side == ToothSide.UNKNOWN:
            # 如果任一方未知，给予部分分数
            score += self.WEIGHT_SIDE * 0.3

        # 匹配 tooth_type
        if qc_tags.tooth_type == baseline_tags.tooth_type and qc_tags.tooth_type != ToothType.UNKNOWN:
            score += self.WEIGHT_TOOTH_TYPE
        elif qc_tags.tooth_type == ToothType.UNKNOWN or baseline_tags.tooth_type == ToothType.UNKNOWN:
            score += self.WEIGHT_TOOTH_TYPE * 0.3

        # 匹配 region
        if qc_tags.region == baseline_tags.region and qc_tags.region != Region.UNKNOWN:
            score += self.WEIGHT_REGION
        elif qc_tags.region == Region.UNKNOWN or baseline_tags.region == Region.UNKNOWN:
            score += self.WEIGHT_REGION * 0.3

        return min(score, 1.0)

    def get_zone_coverage(self, user_id: str) -> Dict[int, bool]:
        """
        获取用户的分区覆盖情况

        Args:
            user_id: 用户ID

        Returns:
            分区覆盖字典 {zone_id: has_baseline}
        """
        baseline_frames = self._get_user_baseline_frames(user_id)

        coverage = {}
        for zone_id in range(1, 8):
            coverage[zone_id] = zone_id in baseline_frames and len(baseline_frames[zone_id]) > 0

        return coverage

    def get_zone_display_name(self, zone_id: int) -> str:
        """
        获取分区显示名称

        Args:
            zone_id: 分区ID

        Returns:
            分区显示名称
        """
        return ZONE_DISPLAY_NAMES.get(zone_id, f"未知分区 {zone_id}")

    def get_zone_middle_frames(self, user_id: str) -> Dict[int, AKeyframe]:
        """
        获取用户每个基线区域的中间帧

        策略：每个区域选择帧列表中间位置的帧作为代表

        Args:
            user_id: 用户ID

        Returns:
            按 zone_id 映射的中间帧 {zone_id: AKeyframe}
        """
        print(f"[FrameMatcher] 获取用户基线中间帧: user_id={user_id}")

        # 获取所有区域的帧
        frames_by_zone = self._get_user_baseline_frames(user_id)

        if not frames_by_zone:
            print(f"[FrameMatcher] 用户没有基线帧数据")
            return {}

        middle_frames: Dict[int, AKeyframe] = {}

        for zone_id in range(1, 8):  # 1-7 区域
            if zone_id not in frames_by_zone or not frames_by_zone[zone_id]:
                continue

            zone_frames = frames_by_zone[zone_id]
            # 选择中间帧
            middle_idx = len(zone_frames) // 2
            middle_frames[zone_id] = zone_frames[middle_idx]

            print(f"[FrameMatcher] 区域 {zone_id} ({self.get_zone_display_name(zone_id)}): "
                  f"共 {len(zone_frames)} 帧, 选择第 {middle_idx + 1} 帧")

        print(f"[FrameMatcher] 获取到 {len(middle_frames)}/7 个区域的中间帧")
        return middle_frames

    def build_baseline_reference_simple(self, user_id: str) -> Tuple[BaselineReference, Dict[int, AKeyframe]]:
        """
        构建简化版基线参考（每区域取中间帧）

        Args:
            user_id: 用户ID

        Returns:
            (BaselineReference, 中间帧字典)
        """
        # 获取用户档案
        profile = self.db.query(AUserProfile).filter_by(user_id=user_id).first()

        if not profile or not profile.baseline_completed:
            return BaselineReference(
                has_baseline=False,
                comparison_mode="none"
            ), {}

        # 获取每个区域的中间帧
        middle_frames = self.get_zone_middle_frames(user_id)

        if not middle_frames:
            return BaselineReference(
                has_baseline=True,
                baseline_completion_date=str(profile.baseline_completion_date.isoformat()) if profile.baseline_completion_date else None,
                comparison_mode="none"
            ), {}

        # 构建基线帧引用列表
        baseline_frame_refs = []
        for zone_id, frame in middle_frames.items():
            bl_session = self.db.query(ASession).filter_by(id=frame.session_id).first()
            ref = BaselineFrameReference(
                baseline_frame_id=str(frame.id),
                baseline_session_id=str(frame.session_id),
                baseline_zone_id=zone_id,
                baseline_timestamp=frame.timestamp_in_video,
                baseline_image_url=frame.image_path,
                baseline_created_at=str(bl_session.created_at.isoformat()) if bl_session else "",
                matching_score=1.0  # 直接选取，无需匹配分数
            )
            baseline_frame_refs.append(ref)

        # 确定对比模式
        if len(middle_frames) >= 6:
            comparison_mode = "full"
        elif len(middle_frames) >= 3:
            comparison_mode = "partial"
        else:
            comparison_mode = "minimal"

        return BaselineReference(
            has_baseline=True,
            baseline_completion_date=str(profile.baseline_completion_date.isoformat()) if profile.baseline_completion_date else None,
            matched_baseline_frames=baseline_frame_refs,
            comparison_mode=comparison_mode
        ), middle_frames
