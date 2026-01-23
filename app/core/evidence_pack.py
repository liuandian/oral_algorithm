# -*- coding: utf-8 -*-
"""
EvidencePack 生成器 - 修正版
适配最新的 KeyframeData 模型
"""
import json
from typing import List
from pathlib import Path
from sqlalchemy.orm import Session

from app.models.database import ASession, AKeyframe, AEvidencePack
from app.models.evidence_pack import EvidencePack, KeyframeData, FrameMetaTags


class EvidencePackError(Exception):
    """EvidencePack 生成异常"""
    pass


class EvidencePackGenerator:
    """EvidencePack 生成器"""

    def __init__(self, db: Session):
        self.db = db

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
                anomaly_score=kf.anomaly_score,
                meta_tags=meta_tags
            )

            frame_data_list.append(frame_data)

        if not frame_data_list:
            raise EvidencePackError("没有有效的关键帧数据")

        # 第四步：构建 EvidencePack
        evidence_pack = EvidencePack(
            session_id=str(session.id),
            user_id=session.user_id,
            session_type=session.session_type,
            zone_id=session.zone_id,
            created_at=str(session.created_at.isoformat()),
            total_frames=len(frame_data_list),
            frames=frame_data_list
        )

        print(f"[EvidencePack] EvidencePack 构建完成，包含 {len(frame_data_list)} 帧")

        # 第五步：保存到数据库
        # 检查是否已存在
        existing_pack = self.db.query(AEvidencePack).filter_by(session_id=session.id).first()
        if existing_pack:
            print(f"[EvidencePack] 更新已存在的 EvidencePack: {existing_pack.id}")
            existing_pack.pack_json = evidence_pack.model_dump()
            existing_pack.total_frames = len(frame_data_list)
            self.db.add(existing_pack)
        else:
            db_evidence_pack = AEvidencePack(
                session_id=session.id,
                pack_json=evidence_pack.model_dump(),
                total_frames=len(frame_data_list)
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