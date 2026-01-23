# -*- coding: utf-8 -*-
"""
LLM 客户端
负责调用千问 API 生成口腔健康报告
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.models.database import ASession, AReport
from app.models.evidence_pack import EvidencePack
from app.services.qianwen_vision import QianwenVisionClient
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
            model=settings.QIANWEN_MODEL
        )

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
        2. 调用千问 Vision API
        3. 解析返回结果
        4. 保存报告到数据库
        """
        print(f"[LLM] 开始生成报告: session_id={session_id}")

        # 第一步：查询 Session
        session = self.db.query(ASession).filter_by(id=session_id).first()
        if not session:
            raise LLMClientError(f"Session 不存在: {session_id}")

        # 第二步：构建 Prompt
        prompt = self._build_prompt(session, evidence_pack)

        # 第三步：调用千问 Vision API
        try:
            llm_response = self.qianwen_client.analyze_evidence_pack(
                evidence_pack=evidence_pack,
                prompt=prompt
            )
        except Exception as e:
            raise LLMClientError(f"千问 API 调用失败: {str(e)}")

        print(f"[LLM] 千问 API 调用成功，生成报告长度: {len(llm_response)} 字符")

        # 第四步：保存报告到数据库
        report = AReport(
            session_id=session_id,
            report_text=llm_response,
            llm_model=settings.QIANWEN_MODEL
        )

        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        # 第五步：更新 Session 状态
        session.processing_status = "completed"
        self.db.commit()

        print(f"[LLM] 报告已保存: {report.id}")

        return report

    def _build_prompt(self, session: ASession, evidence_pack: EvidencePack) -> str:
        """
        构建 LLM Prompt

        Args:
            session: Session 对象
            evidence_pack: EvidencePack 对象

        Returns:
            Prompt 字符串
        """
        session_type = session.session_type
        zone_id = session.zone_id

        if session_type == "quick_check":
            prompt = f"""你是一位专业的口腔健康分析师。请分析以下口腔视频的关键帧图像（共 {len(evidence_pack.frames)} 帧），并给出健康评估报告。

**分析要点：**
1. 牙齿颜色和清洁度
2. 牙龈健康状况（红肿、出血等）
3. 是否有明显的牙结石或牙菌斑
4. 是否有龋齿或其他异常
5. 整体口腔卫生评分（0-100分）

**输出格式：**
- 健康评分：[分数]
- 主要发现：[列表]
- 建议：[具体建议]

请提供专业、友好的分析报告。"""

        else:  # baseline
            prompt = f"""你是一位专业的口腔健康分析师。这是用户口腔第 {zone_id} 区域的基线数据采集视频（共 {len(evidence_pack.frames)} 帧）。

**任务：**
1. 详细记录该区域的当前状态作为基线参考
2. 识别牙齿类型、位置和数量
3. 记录颜色、形态、排列等特征
4. 标注任何现有的问题（如龋齿、牙石、牙龈问题等）

**输出格式：**
- 区域编号：{zone_id}
- 牙齿清单：[列表]
- 当前状态描述：[详细描述]
- 已有问题：[列表]
- 基线建立日期：[当前日期]

这份基线数据将用于后续的对比分析。"""

        return prompt

    def get_report_by_session(self, session_id: str) -> Optional[AReport]:
        """
        获取 Session 的报告

        Args:
            session_id: Session ID

        Returns:
            报告对象或 None
        """
        return self.db.query(AReport).filter_by(session_id=session_id).first()
