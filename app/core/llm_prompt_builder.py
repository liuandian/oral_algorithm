# -*- coding: utf-8 -*-
"""
LLM Prompt 构建器 - 增强版
基于扩展 EvidencePack 结构构建详细、有帮助的提示词
"""
from typing import List, Optional
from datetime import datetime

from app.models.database import ASession
from app.models.evidence_pack import (
    EvidencePack, KeyframeData, FrameMetaTags,
    UserHistorySummary, UserEventData, ConcernPointData,
    BaselineReference, ToothSide, ToothType, Region, DetectedIssue,
    ZONE_DISPLAY_NAMES
)


class PromptBuilder:
    """Prompt 构建器"""

    # 严重程度中文映射
    SEVERITY_MAP = {
        "mild": "轻度",
        "moderate": "中度", 
        "severe": "重度"
    }

    # 状态中文映射
    STATUS_MAP = {
        "active": "需处理",
        "monitoring": "监控中",
        "resolved": "已解决"
    }

    @classmethod
    def build_prompt(cls, session: ASession, evidence_pack: EvidencePack) -> str:
        """
        根据 Session 类型构建对应的 Prompt
        
        Args:
            session: Session 对象
            evidence_pack: 增强版 EvidencePack
            
        Returns:
            完整 Prompt 字符串
        """
        session_type = session.session_type
        
        # 构建通用上下文信息
        context = cls._build_context_section(evidence_pack)
        
        # 构建用户历史信息（新增）
        history = cls._build_history_section(evidence_pack.user_history)
        
        # 构建关键帧分析信息
        frames_analysis = cls._build_frames_analysis(evidence_pack.frames)
        
        # 根据类型构建具体提示
        if session_type == "quick_check":
            if evidence_pack.baseline_reference and evidence_pack.baseline_reference.has_baseline:
                specific_prompt = cls._build_comparison_prompt(evidence_pack, context, history, frames_analysis)
            else:
                specific_prompt = cls._build_standalone_quick_check_prompt(evidence_pack, context, history, frames_analysis)
        else:  # baseline
            specific_prompt = cls._build_baseline_prompt(session, evidence_pack, context, history, frames_analysis)
        
        return specific_prompt

    @classmethod
    def _build_context_section(cls, evidence_pack: EvidencePack) -> str:
        """构建基础上下文信息"""
        lines = ["## 基础信息"]
        lines.append(f"- 检查时间：{evidence_pack.created_at}")
        lines.append(f"- 关键帧数量：{evidence_pack.total_frames} 帧")
        
        # 基线信息
        if evidence_pack.baseline_reference:
            br = evidence_pack.baseline_reference
            if br.has_baseline:
                lines.append(f"- 基线对比：{cls._get_comparison_mode_display(br.comparison_mode)}")
                if br.matched_baseline_frames:
                    zones = sorted(set(f.baseline_zone_id for f in br.matched_baseline_frames))
                    zone_names = [ZONE_DISPLAY_NAMES.get(z, f"区域{z}") for z in zones]
                    lines.append(f"- 覆盖分区：{', '.join(zone_names)}")
        
        return "\n".join(lines)

    @classmethod
    def _build_history_section(cls, user_history: Optional[UserHistorySummary]) -> str:
        """构建用户历史信息段落（核心增强）"""
        if not user_history:
            return "## 用户历史\n- 无历史记录\n"
        
        lines = ["## 用户历史背景"]
        
        # 时间信息
        time_infos = []
        if user_history.days_since_last_check is not None:
            time_infos.append(f"距上次检查：{user_history.days_since_last_check} 天")
        if user_history.days_since_last_event is not None:
            time_infos.append(f"距上次就诊：{user_history.days_since_last_event} 天")
        
        if time_infos:
            lines.append("- " + " | ".join(time_infos))
        
        # 近期事件
        if user_history.recent_events:
            lines.append(f"\n### 近期就诊记录（共 {user_history.total_events} 次）")
            for i, event in enumerate(user_history.recent_events[:3], 1):  # 最多显示3次
                desc = f"{event.event_type_display}"
                if event.days_since_event is not None:
                    desc += f"（{event.days_since_event} 天前）"
                if event.event_description:
                    desc += f" - {event.event_description}"
                lines.append(f"{i}. {desc}")
        
        # 关注点
        if user_history.active_concerns:
            lines.append(f"\n### 当前关注点（共 {len(user_history.active_concerns)} 个活跃）")
            
            for concern in user_history.active_concerns:
                # 构建关注点描述
                parts = []
                
                # 位置信息
                location = concern.zone_display_name or ""
                if concern.location_description:
                    location += f"·{concern.location_description}"
                if location:
                    parts.append(f"【{location}】")
                
                # 类型和状态
                type_desc = concern.concern_type
                status = cls.STATUS_MAP.get(concern.status, concern.status)
                severity = cls.SEVERITY_MAP.get(concern.severity, concern.severity)
                parts.append(f"{type_desc}（{severity}，{status}）")
                
                # 时间信息
                if concern.days_since_first is not None:
                    parts.append(f"发现于 {concern.days_since_first} 天前")
                
                # 关联检查次数
                if concern.related_sessions_count > 0:
                    parts.append(f"已追踪 {concern.related_sessions_count} 次检查")
                
                # 详细描述
                lines.append(f"- {' | '.join(parts)}")
                if concern.concern_description:
                    lines.append(f"  详情：{concern.concern_description}")
        
        # 已解决问题统计
        if user_history.resolved_concerns_count > 0:
            lines.append(f"\n- 已解决问题：{user_history.resolved_concerns_count} 个")
        
        return "\n".join(lines)

    @classmethod
    def _build_frames_analysis(cls, frames: List[KeyframeData]) -> str:
        """构建关键帧分析摘要"""
        lines = ["## 本次检查关键帧分析"]
        
        if not frames:
            lines.append("- 无关键帧数据")
            return "\n".join(lines)
        
        # 统计信息
        strategies = {}
        sides = {}
        regions = {}
        issues = {}
        
        for frame in frames:
            # 策略统计
            strategy = frame.extraction_strategy
            strategies[strategy] = strategies.get(strategy, 0) + 1
            
            # 侧别统计
            if frame.meta_tags:
                side = frame.meta_tags.side.value
                if side != "unknown":
                    sides[side] = sides.get(side, 0) + 1
                
                # 区域统计
                region = frame.meta_tags.region.value
                if region != "unknown":
                    regions[region] = regions.get(region, 0) + 1
                
                # 问题统计
                for issue in frame.meta_tags.detected_issues:
                    if issue.value != "unknown" and issue.value != "none":
                        issues[issue.value] = issues.get(issue.value, 0) + 1
        
        # 输出统计
        if strategies:
            strat_desc = []
            if "rule_triggered" in strategies:
                strat_desc.append(f"{strategies['rule_triggered']} 帧规则触发")
            if "uniform_sampled" in strategies:
                strat_desc.append(f"{strategies['uniform_sampled']} 帧均匀采样")
            lines.append(f"- 抽帧策略：{', '.join(strat_desc)}")
        
        if sides:
            side_names = {
                "upper": "上颌", "lower": "下颌",
                "left": "左侧", "right": "右侧"
            }
            side_desc = [f"{side_names.get(s, s)}{count}帧" for s, count in sides.items()]
            lines.append(f"- 拍摄角度：{', '.join(side_desc)}")
        
        if regions:
            region_names = {
                "occlusal": "咬合面", "interproximal": "牙缝",
                "gum": "龈缘", "lingual": "舌侧", "buccal": "颊侧"
            }
            region_desc = [f"{region_names.get(r, r)}{count}帧" for r, count in regions.items()]
            lines.append(f"- 覆盖区域：{', '.join(region_desc)}")
        
        if issues:
            issue_names = {
                "dark_deposit": "深色沉积",
                "yellow_plaque": "黄色牙菌斑",
                "gum_issue": "牙龈问题",
                "structural_defect": "结构缺损"
            }
            issue_desc = [f"{issue_names.get(i, i)}{count}帧" for i, count in issues.items()]
            lines.append(f"- 检测到问题：{', '.join(issue_desc)}")
        
        # 异常分数范围
        scores = [f.anomaly_score for f in frames if f.anomaly_score > 0]
        if scores:
            lines.append(f"- 异常分数范围：{min(scores):.2f} - {max(scores):.2f}")
        
        return "\n".join(lines)

    @classmethod
    def _build_standalone_quick_check_prompt(
        cls, 
        evidence_pack: EvidencePack,
        context: str,
        history: str,
        frames_analysis: str
    ) -> str:
        """构建独立 Quick Check Prompt（无基线）"""
        
        prompt = f"""你是一位专业的口腔健康分析师，正在为一位用户进行口腔健康评估。请基于以下信息，结合图像数据，提供详细、专业且易于理解的分析报告。

{context}

{history}

{frames_analysis}

---

## 你的分析任务

### 1. 综合评估
请基于关键帧图像，评估以下方面：
- **牙齿整体状况**：颜色、光泽、排列整齐度
- **清洁度评估**：牙菌斑、牙结石的分布和程度
- **牙龈健康**：颜色、肿胀、出血迹象
- **结构性问题**：龋齿、缺损、裂纹等
- **与历史关注点的关联**：当前图像中是否看到之前记录的问题？状态如何？

### 2. 重点关注（基于用户历史）
"""
        
        # 如果有关注点，添加专门分析指令
        if evidence_pack.user_history and evidence_pack.user_history.active_concerns:
            prompt += """
用户有以下正在关注的问题，请特别检查：
"""
            for concern in evidence_pack.user_history.active_concerns:
                location = concern.zone_display_name or ""
                if concern.location_description:
                    location += f"·{concern.location_description}"
                prompt += f"- {location} 的 {concern.concern_type}（{concern.status}）\n"
            
            prompt += """
请评估：
- 这些问题在当前的图像中是否可见？
- 相比之前记录，是改善、恶化还是保持稳定？
- 是否需要调整处理建议？
"""
        
        prompt += f"""
### 3. 输出格式要求

请按以下结构输出报告（使用中文）：

# 口腔健康评估报告

## 总体评分：[0-100分]
**评分依据**：[简要说明评分的理由，参考最近的检查或事件]

## 详细发现

### 牙齿状况
- [具体发现]

### 牙龈健康  
- [具体发现]

### 清洁度评估
- [具体发现]

### 其他异常
- [如有]

## 与历史对比
"""
        
        if evidence_pack.user_history and evidence_pack.user_history.days_since_last_check:
            prompt += f"- 距上次检查 {evidence_pack.user_history.days_since_last_check} 天，"
            prompt += "对比来看：\n  - [变化描述]\n"
        
        prompt += """
## 风险提示
- [高/中/低风险项及说明]

## 个性化建议

### 即时行动
1. [最紧急的1-2项建议]

### 日常护理
- [刷牙、牙线、漱口水等具体建议]

### 后续检查
- [建议下次检查时间，基于当前状况和历史频率]
- [需要特别关注的区域]

### 就医建议（如需要）
- [如果发现问题需要专业治疗，请说明]

---

**特别提醒**：
- 如果用户有正在监控的问题，请说明当前状态
- 如果距上次洁牙已超过6个月，建议提醒用户考虑洁牙
- 建议应具体、可操作，避免过于笼统

请基于以上信息，结合你看到的图像，生成专业、友善且实用的报告。"""

        return prompt

    @classmethod
    def _build_comparison_prompt(
        cls,
        evidence_pack: EvidencePack,
        context: str,
        history: str,
        frames_analysis: str
    ) -> str:
        """构建对比分析 Prompt（有基线）"""
        
        baseline_ref = evidence_pack.baseline_reference
        matched_count = len(baseline_ref.matched_baseline_frames) if baseline_ref.matched_baseline_frames else 0
        
        prompt = f"""你是一位专业的口腔健康分析师，正在为一位老用户进行对比检查分析。请基于本次检查图像、基线数据以及用户历史，提供详细的对比分析报告。

{context}

{history}

{frames_analysis}

---

## 对比分析任务

### 基线信息
- 基线对比模式：{cls._get_comparison_mode_display(baseline_ref.comparison_mode)}
- 匹配基线帧数：{matched_count} 帧
"""
        
        if baseline_ref.baseline_completion_date:
            prompt += f"- 基线建立时间：{baseline_ref.baseline_completion_date}\n"
        
        prompt += f"""
### 分析重点

#### 1. 变化检测（与基线对比）
请逐区域对比分析：
- **新增问题**：本次出现但基线没有的问题
- **原有变化**：基线中存在的问题，现在的状态如何？
  - 改善/恶化/稳定？
  - 变化程度？
- **消失问题**：基线中有但本次未见到的问题

#### 2. 与关注点的关联分析
"""
        
        # 添加关注点关联分析
        if evidence_pack.user_history and evidence_pack.user_history.active_concerns:
            prompt += """
用户当前有以下关注点，请结合基线评估其演变：
"""
            for concern in evidence_pack.user_history.active_concerns:
                location = concern.zone_display_name or ""
                prompt += f"- {location} 的 {concern.concern_type}\n"
                prompt += f"  - 首次发现：{concern.days_since_first} 天前\n"
                prompt += f"  - 当前状态：[请基于图像和基线对比描述]\n"
        
        prompt += f"""
#### 3. 健康趋势评估
- 整体口腔健康趋势：改善/稳定/下降
- 各区域健康度评分变化（与基线对比）

---

## 输出格式要求

请按以下结构输出报告（使用中文）：

# 口腔健康对比分析报告

## 总体评估
- **当前评分**：[0-100分]
- **基线评分**：[参考基线时的评分，如未知则估算]
- **评分变化**：[+/- X分]
- **健康趋势**：[改善/稳定/需关注]

## 分区域对比
"""
        
        # 添加各区域分析框架
        if baseline_ref.matched_baseline_frames:
            for frame_ref in sorted(baseline_ref.matched_baseline_frames, key=lambda x: x.baseline_zone_id)[:7]:
                zone_name = ZONE_DISPLAY_NAMES.get(frame_ref.baseline_zone_id, f"区域{frame_ref.baseline_zone_id}")
                prompt += f"""
### {zone_name}
- **基线状态**：[基线时的描述]
- **当前状态**：[本次检查描述]
- **变化**：改善/恶化/稳定
- **具体变化点**：[详细说明]
"""
        
        prompt += """
## 关注点追踪

### 正在监控的问题
| 问题 | 位置 | 基线状态 | 当前状态 | 趋势 |
|-----|------|---------|---------|------|
| [问题1] | [位置] | [描述] | [描述] | 改善/恶化/稳定 |

### 新问题
- [如有，请列出]

### 已解决问题
- [如有，请列出]

## 风险评估
- **高风险**：[如有]
- **中风险**：[需要持续关注]
- **低风险**：[轻微问题]

## 个性化建议

### 立即行动
1. [最紧急的建议]

### 持续监控
- [需要持续关注的问题及检查频率]

### 预防措施
- [防止问题恶化的建议]

### 下次检查建议
- **时间**：[基于当前状况建议]
- **重点**：[建议重点检查的区域或问题]

---

**分析提示**：
- 对比分析应具体、量化，避免模糊的描述
- 如有恶化趋势，请明确指出并建议就医
- 如有改善，请给予正面反馈，鼓励用户保持良好习惯
- 考虑用户的就诊历史，建议应与近期事件关联（如刚洁牙后不久发现的问题）

请基于图像、基线数据和用户历史，生成专业、客观的对比分析报告。"""

        return prompt

    @classmethod
    def _build_baseline_prompt(
        cls,
        session: ASession,
        evidence_pack: EvidencePack,
        context: str,
        history: str,
        frames_analysis: str
    ) -> str:
        """构建基线采集 Prompt"""
        
        zone_id = session.zone_id
        zone_name = ZONE_DISPLAY_NAMES.get(zone_id, f"区域{zone_id}")
        
        prompt = f"""你是一位专业的口腔健康分析师，正在为一位用户建立口腔健康基线档案。这是第 {zone_id} 分区（{zone_name}）的基线数据采集。

{context}

{history}

{frames_analysis}

---

## 基线采集任务

请基于关键帧图像，为该区域建立详细的基线档案。

### 1. 区域基本信息
- **分区编号**：{zone_id}
- **分区名称**：{zone_name}
- **包含牙齿**：[根据图像判断，如前磨牙、磨牙等]

### 2. 详细记录要求

#### 牙齿清单
请识别并记录该区域可见的牙齿：
- 牙齿位置编号（如适用）
- 每颗牙齿的状态描述
- 颜色、形态、完整性

#### 当前状态描述
- **整体清洁度**：[优秀/良好/一般/需改善]
- **牙齿颜色**：正常/偏黄/有色素沉着
- **牙龈状态**：健康/轻微红肿/红肿
- **可见问题**：[龋齿、牙结石、缺损等]

#### 图像质量评估
- 拍摄角度是否合适
- 光线是否充足
- 是否有遮挡或模糊
- 是否建议重拍某些角度

### 3. 与历史关联（如有）
"""
        
        # 如果有历史关注点在这个区域
        if evidence_pack.user_history and evidence_pack.user_history.active_concerns:
            zone_concerns = [c for c in evidence_pack.user_history.active_concerns if c.zone_id == zone_id]
            if zone_concerns:
                prompt += f"""
用户此前在该区域有以下关注点，请在基线中特别标注：
"""
                for concern in zone_concerns:
                    prompt += f"- {concern.concern_type}（{concern.location_description}）\n"
        
        prompt += f"""
---

## 输出格式要求

请按以下结构输出基线报告（使用中文）：

# 口腔健康基线档案 - 第{zone_id}分区（{zone_name}）

## 分区信息
- **建立日期**：{evidence_pack.created_at}
- **包含牙齿**：[牙齿清单]
- **图像质量**：[评估结果]

## 牙齿状态清单

### 牙齿1（位置）
- **编号**：[如16号牙]
- **类型**：[前磨牙/磨牙]
- **状态**：正常/有填充/有龋齿/其他
- **颜色**：正常/偏黄/有色素沉着
- **表面**：光滑/有沟槽/有缺损
- **备注**：

### 牙齿2...
[继续列出其他可见牙齿]

## 牙龈状态
- **颜色**：粉红色/偏红/红肿
- **边缘**：清晰/模糊/有退缩
- **出血点**：无/有（位置）
- **肿胀**：无/轻微/明显

## 清洁度评估
- **整体评分**：[0-100分]
- **牙菌斑**：无/轻微/明显（位置）
- **牙结石**：无/轻微/明显（位置）
- **色素沉着**：无/轻微/明显（位置）

## 现有问题记录
- **问题1**：[描述、位置、严重程度]
- **问题2**：...

## 特别关注（基于历史）
- [如有历史关注点，请说明当前基线中的状态]

## 基线建议
- **日常护理重点**：[该区域特别需要注意的事项]
- **监控要点**：[需要持续关注的变化]
- **下次检查建议**：[建议的检查频率]

---

**建立提示**：
- 基线应尽可能详细，作为未来对比的基准
- 如有不确定的地方，请标注"需确认"
- 如果图像质量不佳影响判断，请明确指出
- 记录的问题应具体、可量化，便于后续对比

请基于图像建立详尽、专业的基线档案。"""

        return prompt

    @classmethod
    def _get_comparison_mode_display(cls, mode: str) -> str:
        """获取对比模式显示名称"""
        mode_map = {
            "none": "无基线对比",
            "minimal": "最小对比（<3区域）",
            "partial": "部分对比（3-5区域）",
            "full": "完整对比（6-7区域）"
        }
        return mode_map.get(mode, mode)
