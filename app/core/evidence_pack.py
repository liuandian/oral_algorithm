# -*- coding: utf-8 -*-
"""
EvidencePack 生成器
将关键帧数据转换为结构化的 EvidencePack
"""
import base64
from typing import List
from pathlib import Path
from sqlalchemy.orm import Session

from app.models.database import ASession, AKeyframe, AEvidencePack
from app.models.evidence_pack import EvidencePack, KeyframeData, FrameMetaTags
from app.services.storage import storage_service


class EvidencePackError(Exception):
    """EvidencePack 生成异常"""
    pass


class EvidencePackGenerator:
    """EvidencePack 生成器"""

    def __init__(self, db: Session):
        """
        初始化生成器

        Args:
            db: 数据库会话
        """
        self.db = db

    def generate_evidence_pack(self, session_id: str) -> EvidencePack:
        """
        为指定 Session 生成 EvidencePack

        Args:
            session_id: Session ID

        Returns:
            EvidencePack 对象

        Raises:
            EvidencePackError: 生成过程出错

        流程：
        1. 查询 Session 和关键帧
        2. 加载关键帧图像
        3. 编码为 Base64
        4. 构建 EvidencePack
        5. 保存到数据库
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
            # 加载图像文件
            image_path = Path(kf.image_path)
            if not image_path.exists():
                print(f"[警告] 关键帧图像不存在: {image_path}")
                continue

            # 读取并编码为 Base64
            with open(image_path, "rb") as f:
                image_bytes = f.read()
                image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            # 构建 FrameMetaTags
            meta_tags = FrameMetaTags(**kf.meta_tags) if kf.meta_tags else FrameMetaTags()

            # 构建 KeyframeData
            frame_data = KeyframeData(
                frame_index=kf.frame_index,
                timestamp=kf.timestamp_in_video,
                image_base64=image_base64,
                extraction_strategy=kf.extraction_strategy,
                anomaly_score=kf.anomaly_score,
                meta_tags=meta_tags
            )

            frame_data_list.append(frame_data)

        if not frame_data_list:
            raise EvidencePackError("没有有效的关键帧图像数据")

        # 第四步：构建 EvidencePack
        evidence_pack = EvidencePack(
            session_id=str(session.id),
            session_type=session.session_type,
            zone_id=session.zone_id,
            frames=frame_data_list
        )

        print(f"[EvidencePack] EvidencePack 构建完成，包含 {len(frame_data_list)} 帧")

        # 第五步：保存到数据库
        db_evidence_pack = AEvidencePack(
            session_id=session.id,
            pack_json=evidence_pack.model_dump(),
            total_frames=len(frame_data_list)
        )

        self.db.add(db_evidence_pack)
        self.db.commit()
        self.db.refresh(db_evidence_pack)

        print(f"[EvidencePack] 已保存到数据库: {db_evidence_pack.id}")

        return evidence_pack

    def get_evidence_pack_by_session(self, session_id: str) -> EvidencePack:
        """
        从数据库获取已生成的 EvidencePack

        Args:
            session_id: Session ID

        Returns:
            EvidencePack 对象

        Raises:
            EvidencePackError: 未找到 EvidencePack
        """
        db_pack = (
            self.db.query(AEvidencePack)
            .filter_by(session_id=session_id)
            .first()
        )

        if not db_pack:
            raise EvidencePackError(f"EvidencePack 不存在: {session_id}")

        # 从 JSON 反序列化
        return EvidencePack(**db_pack.pack_json)

    def export_evidence_pack_json(self, session_id: str, output_path: str) -> Path:
        """
        导出 EvidencePack 为 JSON 文件

        Args:
            session_id: Session ID
            output_path: 输出文件路径

        Returns:
            输出文件路径
        """
        evidence_pack = self.get_evidence_pack_by_session(session_id)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入 JSON
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(evidence_pack.model_dump_json(indent=2))

        print(f"[EvidencePack] 已导出 JSON: {output_path}")
        return output_path
