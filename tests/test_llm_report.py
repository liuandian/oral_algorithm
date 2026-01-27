# -*- coding: utf-8 -*-
"""
LLM 报告生成测试脚本
测试千问 API 调用和各种报告生成场景
"""
import sys
import os
import base64
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.models.database import SessionLocal, ASession, AKeyframe, AEvidencePack
from app.models.evidence_pack import (
    EvidencePack, KeyframeData, FrameMetaTags,
    BaselineReference, BaselineFrameReference,
    ToothSide, ToothType, Region, DetectedIssue
)
from app.core.llm_client import LLMReportGenerator
from app.core.evidence_pack import EvidencePackGenerator
from app.services.qianwen_vision import QianwenVisionClient


def check_api_key():
    """检查 API Key 是否配置"""
    if not settings.QIANWEN_API_KEY:
        print("=" * 60)
        print("错误: 未配置 QIANWEN_API_KEY")
        print("请在 .env 文件中设置:")
        print("  QIANWEN_API_KEY=your_api_key_here")
        print("=" * 60)
        return False
    print(f"[OK] API Key 已配置 (前8位: {settings.QIANWEN_API_KEY[:8]}...)")
    return True


def test_api_connection():
    """测试 1: 千问 API 连接测试"""
    print("\n" + "=" * 60)
    print("测试 1: 千问 API 连接测试")
    print("=" * 60)

    if not check_api_key():
        return False

    client = QianwenVisionClient(
        api_key=settings.QIANWEN_API_KEY,
        model=settings.QIANWEN_VISION_MODEL
    )

    # 使用一个简单的文本请求测试连接
    try:
        import requests
        headers = {
            "Authorization": f"Bearer {settings.QIANWEN_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "qwen-max",
            "input": {
                "messages": [
                    {"role": "user", "content": "你好，请回复'API连接成功'"}
                ]
            }
        }
        response = requests.post(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            print(f"[OK] API 连接成功!")
            print(f"模型: {settings.QIANWEN_VISION_MODEL}")
            print(f"回复：{result}")
            return True
        else:
            print(f"[FAIL] API 返回错误: {response.status_code}")
            print(response.text)
            return False

    except Exception as e:
        print(f"[FAIL] API 连接失败: {e}")
        return False


def test_generate_report_from_session(session_id: str):
    """测试 2: 从真实 Session 生成报告"""
    print("\n" + "=" * 60)
    print(f"测试 2: 从 Session 生成报告")
    print(f"Session ID: {session_id}")
    print("=" * 60)

    if not check_api_key():
        return False

    db = SessionLocal()
    try:
        # 查询 Session
        session = db.query(ASession).filter_by(id=session_id).first()
        if not session:
            print(f"[FAIL] Session 不存在: {session_id}")
            return False

        print(f"[OK] 找到 Session: {session.session_type}, zone_id={session.zone_id}")

        # 生成/获取 EvidencePack
        pack_gen = EvidencePackGenerator(db)
        try:
            evidence_pack = pack_gen.get_evidence_pack_by_session(session_id)
            print(f"[OK] 获取已有 EvidencePack: {evidence_pack.total_frames} 帧")
        except:
            evidence_pack = pack_gen.generate_evidence_pack(session_id)
            print(f"[OK] 生成新 EvidencePack: {evidence_pack.total_frames} 帧")

        # 显示基线参考信息
        if evidence_pack.baseline_reference:
            br = evidence_pack.baseline_reference
            print(f"[INFO] 基线参考: has_baseline={br.has_baseline}, mode={br.comparison_mode}")
            if br.matched_baseline_frames:
                print(f"[INFO] 匹配基线帧数: {len(br.matched_baseline_frames)}")

        # 生成报告
        print("\n正在调用千问 API 生成报告...")
        llm_gen = LLMReportGenerator(db)
        report = llm_gen.generate_report(session_id, evidence_pack)

        print("\n" + "-" * 40)
        print("生成的报告:")
        print("-" * 40)
        print(report.report_text)
        print("-" * 40)
        print(f"\n[OK] 报告生成成功! 报告ID: {report.id}")

        return True

    except Exception as e:
        import traceback
        print(f"[FAIL] 报告生成失败: {e}")
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_mock_quick_check_report():
    """测试 3: 模拟 Quick Check 报告 (无需真实图像)"""
    print("\n" + "=" * 60)
    print("测试 3: 模拟 Quick Check 报告 (纯文本，无图像)")
    print("=" * 60)

    if not check_api_key():
        return False

    try:
        import requests

        # 构建模拟的分析请求（纯文本）
        prompt = """你是一位专业的口腔健康分析师。请根据以下模拟的检查数据给出健康评估报告。

**模拟检查数据：**
- 检查类型：Quick Check（快速检查）
- 关键帧数量：5帧
- 帧1：上前区，未检测到明显问题
- 帧2：下前区，发现轻微黄色附着
- 帧3：上左后区咬合面，发现深色沟槽
- 帧4：下右后区，牙龈略红
- 帧5：上右后区，正常

**输出格式：**
- 健康评分：[分数]
- 主要发现：[列表]
- 建议：[具体建议]

请提供专业、友好的分析报告。"""

        headers = {
            "Authorization": f"Bearer {settings.QIANWEN_API_KEY}",
            "Content-Type": "application/json"
        }
        # 纯文本请求使用文本模型
        payload = {
            "model": settings.QIANWEN_TEXT_MODEL,
            "input": {
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            "parameters": {
                "max_tokens": 2000,
                "temperature": 0.7
            }
        }

        print(f"正在调用千问 API (模型: {settings.QIANWEN_TEXT_MODEL})...")
        response = requests.post(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            output = result.get("output", {})
            text = output.get("text", "")

            print("\n" + "-" * 40)
            print("生成的报告:")
            print("-" * 40)
            print(text)
            print("-" * 40)
            print("\n[OK] 模拟 Quick Check 报告生成成功!")
            return True
        else:
            print(f"[FAIL] API 返回错误: {response.status_code}")
            print(response.text)
            return False

    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        return False


def test_mock_comparison_report():
    """测试 4: 模拟对比分析报告"""
    print("\n" + "=" * 60)
    print("测试 4: 模拟对比分析报告 (Quick Check vs 基线)")
    print("=" * 60)

    if not check_api_key():
        return False

    try:
        import requests

        # 构建对比分析请求
        prompt = """你是一位专业的口腔健康分析师。请对比分析本次检查数据与用户的基线数据。

**本次检查信息：**
- 检查类型：快速检查 (Quick Check)
- 关键帧数量：6 帧
- 基线对比模式：full
- 匹配基线帧数：5
- 覆盖分区: 1, 2, 3, 5, 6

**本次检查发现：**
- 帧1（上左后区）：咬合面发现新的深色点，与基线相比新增
- 帧2（上前区）：牙齿清洁度良好，与基线一致
- 帧3（上右后区）：轻微牙石，与基线一致（未变化）
- 帧4（下前区）：牙龈颜色正常，相比基线有改善
- 帧5（下右后区）：发现黄色附着，与基线相比加重

**对比分析要点：**
1. **变化检测**：与基线相比，识别任何新出现的问题或变化
2. **改善情况**：记录相比基线有所改善的方面
3. **持续关注点**：基线中已存在且仍需关注的问题
4. **整体评估**：口腔健康趋势（改善/稳定/下降）

**输出格式：**
## 变化总结
- 新发现：[列表]
- 改善项：[列表]
- 持续关注：[列表]

## 健康趋势评估
- 趋势：[改善/稳定/需关注]
- 评分变化：[相比基线的分数变化，如 +5 或 -3]
- 当前评分：[0-100分]

## 个性化建议
- 优先事项：[最需要关注的1-2项]
- 护理建议：[具体建议]
- 复查建议：[下次检查时间建议]

请提供客观、专业的对比分析报告。"""

        headers = {
            "Authorization": f"Bearer {settings.QIANWEN_API_KEY}",
            "Content-Type": "application/json"
        }
        # 纯文本请求使用文本模型
        payload = {
            "model": settings.QIANWEN_TEXT_MODEL,
            "input": {
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            "parameters": {
                "max_tokens": 2000,
                "temperature": 0.7
            }
        }

        print(f"正在调用千问 API (模型: {settings.QIANWEN_TEXT_MODEL})...")
        response = requests.post(
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            output = result.get("output", {})
            text = output.get("text", "")

            print("\n" + "-" * 40)
            print("生成的对比分析报告:")
            print("-" * 40)
            print(text)
            print("-" * 40)
            print("\n[OK] 模拟对比分析报告生成成功!")
            return True
        else:
            print(f"[FAIL] API 返回错误: {response.status_code}")
            print(response.text)
            return False

    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        return False


def list_available_sessions():
    """列出可用的 Session 供测试"""
    print("\n" + "=" * 60)
    print("可用的 Session 列表")
    print("=" * 60)

    db = SessionLocal()
    try:
        sessions = db.query(ASession).filter(
            ASession.processing_status == "completed"
        ).order_by(ASession.created_at.desc()).limit(10).all()

        if not sessions:
            print("暂无已完成的 Session")
            return []

        print(f"找到 {len(sessions)} 个已完成的 Session:\n")
        for s in sessions:
            keyframe_count = db.query(AKeyframe).filter_by(session_id=s.id).count()
            print(f"  ID: {s.id}")
            print(f"  类型: {s.session_type}, Zone: {s.zone_id}")
            print(f"  用户: {s.user_id}")
            print(f"  关键帧数: {keyframe_count}")
            print(f"  创建时间: {s.created_at}")
            print("-" * 40)

        return [str(s.id) for s in sessions]

    finally:
        db.close()


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("千问 API 报告生成 - 完整测试")
    print("=" * 60)

    results = {}

    # 测试 1: API 连接
    results["API连接测试"] = test_api_connection()

    # 测试 2: 模拟 Quick Check
    results["模拟Quick Check"] = test_mock_quick_check_report()

    # 测试 3: 模拟对比分析
    results["模拟对比分析"] = test_mock_comparison_report()

    # 打印结果汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {test_name}: [{status}]")

    all_passed = all(results.values())
    print("\n" + ("所有测试通过!" if all_passed else "部分测试失败"))
    return all_passed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LLM 报告生成测试")
    parser.add_argument("--test", choices=["all", "api", "quick", "compare", "session", "list"],
                        default="all", help="选择测试类型")
    parser.add_argument("--session-id", type=str, help="指定 Session ID (用于 session 测试)")

    args = parser.parse_args()

    if args.test == "all":
        run_all_tests()
    elif args.test == "api":
        test_api_connection()
    elif args.test == "quick":
        test_mock_quick_check_report()
    elif args.test == "compare":
        test_mock_comparison_report()
    elif args.test == "session":
        if args.session_id:
            test_generate_report_from_session(args.session_id)
        else:
            print("请使用 --session-id 指定 Session ID")
            print("使用 --test list 查看可用的 Session")
    elif args.test == "list":
        list_available_sessions()
