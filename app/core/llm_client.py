# -*- coding: utf-8 -*-
"""
LLM 客户端
负责调用千问 API 生成口腔健康报告
"""
from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from app.models.database import ASession, AReport, AEvidencePack, AKeyframe
from app.models.evidence_pack import EvidencePack, KeyframeData, FrameMetaTags
from app.services.qianwen_vision import QianwenVisionClient, LLMResponse
from app.core.frame_matcher import FrameMatcherService
from app.core.llm_prompt_builder import PromptBuilder
from app.config import settings


class LLMClientError(Exception):
    """LLM 客户端异常"""
    pass


class LLMReportGenerator:
    """LLM 报告生成器"""

    def __init__(self, db: Session):
        """
        初始化生成器

        Args:
            db: 数据库会话
        """
        self.db = db
        self.qianwen_client = QianwenVisionClient(
            api_key=settings.QIANWEN_API_KEY,
            model=settings.QIANWEN_VISION_MODEL
        )
        self.frame_matcher = FrameMatcherService(db)

    def generate_report(self, session_id: str, evidence_pack: EvidencePack) -> AReport:
        """
        使用 LLM 生成口腔健康报告

        Args:
            session_id: Session ID
            evidence_pack: EvidencePack 证据包

        Returns:
            报告对象

        Raises:
            LLMClientError: 报告生成失败

        流程：
        1. 构建 Prompt
        2. 获取基线中间帧（如果是 Quick Check）
        3. 调用千问 Vision API
        4. 解析返回结果（含 token 统计）
        5. 保存报告到数据库
        """
        print(f"[LLM] 开始生成报告: session_id={session_id}")

        # 第一步：查询 Session
        session = self.db.query(ASession).filter_by(id=session_id).first()
        if not session:
            raise LLMClientError(f"Session 不存在: {session_id}")

        # 第二步：构建 Prompt
        prompt = self._build_prompt(session, evidence_pack)

        # 第三步：获取基线中间帧（如果是 Quick Check 且有基线）
        baseline_frames: List[KeyframeData] = []
        if session.session_type == "quick_check":
            baseline_frames = self._get_baseline_middle_frames(session.user_id)
            if baseline_frames:
                print(f"[LLM] 获取到 {len(baseline_frames)} 个区域的基线中间帧进行对比")

        # 第四步：调用千问 Vision API
        try:
            llm_result: LLMResponse = self.qianwen_client.analyze_evidence_pack(
                evidence_pack=evidence_pack,
                prompt=prompt,
                baseline_frames=baseline_frames if baseline_frames else None
            )
        except Exception as e:
            raise LLMClientError(f"千问 API 调用失败: {str(e)}")

        print(f"[LLM] 千问 API 调用成功，生成报告长度: {len(llm_result.text)} 字符")
        print(f"[LLM] Token 消耗: input={llm_result.input_tokens}, output={llm_result.output_tokens}, total={llm_result.total_tokens}")

        # 第五步：查询数据库中的 EvidencePack 以获取 evidence_pack_id
        db_evidence_pack = self.db.query(AEvidencePack).filter_by(session_id=session_id).first()
        if not db_evidence_pack:
            raise LLMClientError(f"EvidencePack 不存在: {session_id}")

        # 第六步：保存报告到数据库（含 token 统计）
        report = AReport(
            session_id=session_id,
            evidence_pack_id=db_evidence_pack.id,
            report_text=llm_result.text,
            llm_model=settings.QIANWEN_VISION_MODEL,
            tokens_used=llm_result.total_tokens
        )

        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        # 第七步：更新 Session 状态
        session.processing_status = "completed"
        self.db.commit()

        print(f"[LLM] 报告已保存: {report.id}, tokens_used={llm_result.total_tokens}")

        return report

    def _get_baseline_middle_frames(self, user_id: str) -> List[KeyframeData]:
        """
        获取用户基线每个区域的中间帧，转换为 KeyframeData 格式

        Args:
            user_id: 用户ID

        Returns:
            KeyframeData 列表（按 zone_id 排序，最多7帧）
        """
        import json

        middle_frames_dict = self.frame_matcher.get_zone_middle_frames(user_id)

        if not middle_frames_dict:
            return []

        keyframe_data_list: List[KeyframeData] = []

        # 按 zone_id 排序
        for zone_id in sorted(middle_frames_dict.keys()):
            db_frame: AKeyframe = middle_frames_dict[zone_id]

            # 解析 meta_tags
            tags_source = db_frame.meta_tags
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
            kf_data = KeyframeData(
                frame_id=str(db_frame.id),
                timestamp=db_frame.timestamp_in_video,
                image_url=str(db_frame.image_path),
                extraction_strategy=db_frame.extraction_strategy or "uniform_sampled",
                extraction_reason=db_frame.extraction_reason or f"baseline_zone_{zone_id}",
                anomaly_score=db_frame.anomaly_score or 0.0,
                meta_tags=meta_tags
            )

            keyframe_data_list.append(kf_data)

        return keyframe_data_list

    def _build_prompt(self, session: ASession, evidence_pack: EvidencePack) -> str:
        """
        构建 LLM Prompt（使用增强版 PromptBuilder）

        Args:
            session: Session 对象
            evidence_pack: EvidencePack 对象

        Returns:
            Prompt 字符串
        """
        # 使用新的 PromptBuilder 构建增强版 Prompt
        return PromptBuilder.build_prompt(session, evidence_pack)

    def get_report_by_session(self, session_id: str) -> Optional[AReport]:
        """
        获取 Session 的报告

        Args:
            session_id: Session ID

        Returns:
            报告对象或 None
        """
        return self.db.query(AReport).filter_by(session_id=session_id).first()
