#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
EvidencePack 功能测试脚本

测试 EvidencePack 的生成、基线匹配和导出功能
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.evidence_pack import EvidencePackGenerator, EvidencePackError
from app.core.frame_matcher import FrameMatcherService
from app.models.database import (
    SessionLocal, ASession, BRawVideo, AKeyframe, AEvidencePack,
    AUserProfile, init_db
)
from app.models.evidence_pack import (
    EvidencePack, KeyframeData, FrameMetaTags,
    BaselineReference, BaselineFrameReference,
    ToothSide, ToothType, Region, DetectedIssue
)
from app.services.storage import storage_service


# 测试配置
TEST_USER_ID = "test_user_evidence"
TEST_VIDEO_PATH = Path(__file__).parent / "video" / "test1.mp4"


def create_test_session(db, session_type="quick_check", zone_id=None):
    """创建测试Session"""
    try:
        # 创建B流记录
        import uuid
        b_video = BRawVideo(
            id=uuid.uuid4(),
            user_id=TEST_USER_ID,
            file_hash=f"test_hash_{uuid.uuid4().hex[:8]}",
            file_path=str(TEST_VIDEO_PATH) if TEST_VIDEO_PATH.exists() else "/tmp/test.mp4",
            file_size_bytes=1024*1024,
            duration_seconds=10.0,
            session_type=session_type,
            zone_id=zone_id
        )
        db.add(b_video)
        db.flush()

        # 创建Session
        session = ASession(
            user_id=TEST_USER_ID,
            b_video_id=b_video.id,
            session_type=session_type,
            zone_id=zone_id,
            processing_status="completed"
        )
        db.add(session)
        db.flush()

        return session

    except Exception as e:
        db.rollback()
        print(f"[错误] 创建测试Session失败: {e}")
        raise


def create_test_keyframes(db, session_id, count=5):
    """创建测试关键帧数据"""
    try:
        keyframes = []
        for i in range(count):
            # 创建不同的meta_tags以测试多样性
            side = [ToothSide.UPPER, ToothSide.LOWER, ToothSide.LEFT][i % 3]
            tooth_type = [ToothType.ANTERIOR, ToothType.POSTERIOR][i % 2]
            region = [Region.OCCLUSAL, Region.GUM, Region.INTERPROXIMAL][i % 3]
            issues = [[DetectedIssue.NONE], [DetectedIssue.DARK_DEPOSIT], [DetectedIssue.YELLOW_PLAQUE]][i % 3]

            meta_tags = {
                "side": side.value,
                "tooth_type": tooth_type.value,
                "region": region.value,
                "detected_issues": [issue.value for issue in issues],
                "confidence_score": 0.7 + (i * 0.05),
                "is_verified": False
            }

            kf = AKeyframe(
                session_id=session_id,
                frame_index=i * 30,
                timestamp_in_video=f"00:{10+i:02d}.00",
                extraction_strategy="uniform_sampled" if i % 2 == 0 else "rule_triggered",
                extraction_reason="test" if i % 2 == 0 else "anomaly_detected",
                image_path=f"/tmp/test_frame_{i}.jpg",
                anomaly_score=0.3 + (i * 0.1),
                meta_tags=meta_tags
            )
            db.add(kf)
            keyframes.append(kf)

        db.flush()
        return keyframes

    except Exception as e:
        db.rollback()
        print(f"[错误] 创建测试关键帧失败: {e}")
        raise


def test_evidence_pack_generation():
    """测试1: EvidencePack生成"""
    print("\n" + "="*60)
    print("测试 1: EvidencePack 生成")
    print("="*60)

    db = SessionLocal()
    try:
        # 清理旧数据
        old_sessions = db.query(ASession).filter_by(user_id=TEST_USER_ID).all()
        for s in old_sessions:
            db.query(AKeyframe).filter_by(session_id=s.id).delete()
            db.query(AEvidencePack).filter_by(session_id=s.id).delete()
            db.delete(s)
        db.commit()

        # 创建测试数据
        session = create_test_session(db, "quick_check")
        keyframes = create_test_keyframes(db, session.id, count=5)
        db.commit()

        print(f"[信息] 创建测试Session: {session.id}")
        print(f"[信息] 创建 {len(keyframes)} 个测试关键帧")

        # 生成EvidencePack
        generator = EvidencePackGenerator(db)
        evidence_pack = generator.generate_evidence_pack(str(session.id))

        # 验证结果
        assert evidence_pack.session_id == str(session.id), "Session ID不匹配"
        assert evidence_pack.user_id == TEST_USER_ID, "用户ID不匹配"
        assert evidence_pack.session_type == "quick_check", "Session类型不匹配"
        assert len(evidence_pack.frames) == 5, f"关键帧数量不匹配: {len(evidence_pack.frames)}"

        print(f"[OK] EvidencePack生成成功")
        print(f"  - Session ID: {evidence_pack.session_id}")
        print(f"  - 总帧数: {evidence_pack.total_frames}")
        print(f"  - 帧列表长度: {len(evidence_pack.frames)}")

        # 验证帧数据结构
        for i, frame in enumerate(evidence_pack.frames):
            assert isinstance(frame, KeyframeData), f"帧{i}类型错误"
            assert frame.frame_id is not None, f"帧{i}缺少ID"
            assert frame.meta_tags is not None, f"帧{i}缺少meta_tags"
            print(f"  - Frame {i}: {frame.timestamp}, {frame.meta_tags.side.value}, {frame.meta_tags.tooth_type.value}")

        # 验证数据库记录
        db_pack = db.query(AEvidencePack).filter_by(session_id=session.id).first()
        assert db_pack is not None, "数据库中没有EvidencePack记录"
        assert db_pack.total_frames == 5, "数据库中total_frames不匹配"

        print("[OK] EvidencePack数据库记录验证通过")
        return True

    except Exception as e:
        db.rollback()
        print(f"[错误] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_evidence_pack_retrieval():
    """测试2: EvidencePack获取"""
    print("\n" + "="*60)
    print("测试 2: EvidencePack 获取")
    print("="*60)

    db = SessionLocal()
    try:
        # 获取刚才创建的session
        session = db.query(ASession).filter_by(
            user_id=TEST_USER_ID,
            session_type="quick_check"
        ).first()

        if not session:
            print("[跳过] 没有可用的测试Session")
            return False

        # 获取EvidencePack
        generator = EvidencePackGenerator(db)
        evidence_pack = generator.get_evidence_pack_by_session(str(session.id))

        assert evidence_pack is not None, "无法获取EvidencePack"
        assert evidence_pack.session_id == str(session.id), "Session ID不匹配"

        print(f"[OK] 成功获取EvidencePack")
        print(f"  - Session ID: {evidence_pack.session_id}")
        print(f"  - 总帧数: {evidence_pack.total_frames}")

        return True

    except Exception as e:
        print(f"[错误] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_baseline_reference():
    """测试3: 基线参考功能"""
    print("\n" + "="*60)
    print("测试 3: 基线参考功能")
    print("="*60)

    db = SessionLocal()
    try:
        # 先创建完整的基线数据
        # 创建7个基线session（覆盖所有区域）
        for zone_id in range(1, 8):
            session = create_test_session(db, "baseline", zone_id=zone_id)
            create_test_keyframes(db, session.id, count=3)

        # 创建用户档案，标记基线已完成
        profile = AUserProfile(
            user_id=TEST_USER_ID,
            baseline_completed=True,
            baseline_completion_date=datetime.now(),
            baseline_zone_map={"1": str(session.id), "2": str(session.id)},
            total_quick_checks=0
        )
        db.add(profile)
        db.commit()

        print(f"[OK] 创建7个基线区域数据")

        # 测试FrameMatcherService
        matcher = FrameMatcherService(db)
        coverage = matcher.get_zone_coverage(TEST_USER_ID)

        print("[OK] 分区覆盖情况:")
        for zone_id, has_baseline in coverage.items():
            status = "✓" if has_baseline else "✗"
            print(f"  Zone {zone_id}: {status}")

        # 获取中间帧
        middle_frames = matcher.get_zone_middle_frames(TEST_USER_ID)
        print(f"[OK] 获取到 {len(middle_frames)}/7 个区域的中间帧")

        # 测试简化版基线参考构建
        baseline_ref, frames = matcher.build_baseline_reference_simple(TEST_USER_ID)

        print(f"[OK] 基线参考构建完成")
        print(f"  - 有基线: {baseline_ref.has_baseline}")
        print(f"  - 对比模式: {baseline_ref.comparison_mode}")
        print(f"  - 匹配帧数: {len(baseline_ref.matched_baseline_frames) if baseline_ref.matched_baseline_frames else 0}")

        return True

    except Exception as e:
        db.rollback()
        print(f"[错误] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_frame_matcher():
    """测试4: 帧匹配功能"""
    print("\n" + "="*60)
    print("测试 4: 帧匹配功能")
    print("="*60)

    db = SessionLocal()
    try:
        # 获取Quick Check session
        qc_session = db.query(ASession).filter_by(
            user_id=TEST_USER_ID,
            session_type="quick_check"
        ).first()

        if not qc_session:
            print("[跳过] 没有Quick Check Session")
            return False

        # 获取关键帧
        qc_keyframes = db.query(AKeyframe).filter_by(session_id=qc_session.id).all()
        if not qc_keyframes:
            print("[跳过] Quick Check没有关键帧")
            return False

        # 测试帧匹配
        matcher = FrameMatcherService(db)
        matches = matcher.match_frames_to_baseline(qc_keyframes, TEST_USER_ID)

        print(f"[OK] 帧匹配完成")
        print(f"  - Quick Check帧数: {len(qc_keyframes)}")
        print(f"  - 匹配到的基线帧: {len(matches)}")

        if matches:
            for qc_id, bl_ref in list(matches.items())[:3]:
                print(f"  - QC Frame {qc_id[:8]}... -> BL Frame {bl_ref.baseline_frame_id[:8]}... (zone:{bl_ref.baseline_zone_id})")

        return True

    except Exception as e:
        print(f"[错误] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_evidence_pack_export():
    """测试5: EvidencePack导出"""
    print("\n" + "="*60)
    print("测试 5: EvidencePack 导出")
    print("="*60)

    db = SessionLocal()
    try:
        # 获取Quick Check session
        session = db.query(ASession).filter_by(
            user_id=TEST_USER_ID,
            session_type="quick_check"
        ).first()

        if not session:
            print("[跳过] 没有可用的测试Session")
            return False

        # 导出为JSON
        import tempfile
        output_path = Path(tempfile.gettempdir()) / f"test_evidence_pack_{session.id}.json"

        generator = EvidencePackGenerator(db)
        result_path = generator.export_evidence_pack_json(str(session.id), str(output_path))

        assert result_path.exists(), "导出文件不存在"

        # 验证JSON内容
        with open(result_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert 'session_id' in data, "JSON缺少session_id"
        assert 'frames' in data, "JSON缺少frames"
        assert len(data['frames']) > 0, "JSON中frames为空"

        print(f"[OK] EvidencePack导出成功")
        print(f"  - 导出路径: {result_path}")
        print(f"  - JSON大小: {result_path.stat().st_size} bytes")
        print(f"  - 帧数: {len(data['frames'])}")

        # 清理
        result_path.unlink()

        return True

    except Exception as e:
        print(f"[错误] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_error_handling():
    """测试6: 错误处理"""
    print("\n" + "="*60)
    print("测试 6: 错误处理")
    print("="*60)

    db = SessionLocal()
    try:
        generator = EvidencePackGenerator(db)

        # 测试不存在的session（使用有效的UUID格式）
        import uuid
        try:
            generator.generate_evidence_pack(str(uuid.uuid4()))
            print("[错误] 应该抛出异常")
            return False
        except EvidencePackError as e:
            print(f"[OK] 正确处理不存在的Session: {e}")

        # 测试没有关键帧的session
        empty_session = create_test_session(db, "quick_check")
        db.commit()

        try:
            generator.generate_evidence_pack(str(empty_session.id))
            print("[错误] 应该抛出异常")
            return False
        except EvidencePackError as e:
            print(f"[OK] 正确处理空Session: {e}")

        return True

    except Exception as e:
        print(f"[错误] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def cleanup_test_data():
    """清理测试数据"""
    print("\n" + "="*60)
    print("清理测试数据")
    print("="*60)

    db = SessionLocal()
    try:
        # 删除用户档案
        db.query(AUserProfile).filter_by(user_id=TEST_USER_ID).delete()

        # 获取所有测试session
        sessions = db.query(ASession).filter_by(user_id=TEST_USER_ID).all()

        for session in sessions:
            # 删除关键帧
            db.query(AKeyframe).filter_by(session_id=session.id).delete()
            # 删除EvidencePack
            db.query(AEvidencePack).filter_by(session_id=session.id).delete()
            # 删除Session
            db.delete(session)
        
        # 注意: B流记录遵循Write-Once原则，不删除

        db.commit()
        print(f"[清理] 已删除 {len(sessions)} 个测试Session及其关联数据")

    except Exception as e:
        db.rollback()
        print(f"[错误] 清理失败: {e}")
    finally:
        db.close()


def run_all_tests():
    """运行所有测试"""
    print("="*60)
    print("EvidencePack 功能 - 完整测试")
    print("="*60)

    results = {}

    # 测试1: EvidencePack生成
    results["EvidencePack生成"] = test_evidence_pack_generation()

    # 测试2: EvidencePack获取
    results["EvidencePack获取"] = test_evidence_pack_retrieval()

    # 测试3: 基线参考
    results["基线参考功能"] = test_baseline_reference()

    # 测试4: 帧匹配
    results["帧匹配功能"] = test_frame_matcher()

    # 测试5: 导出功能
    results["导出功能"] = test_evidence_pack_export()

    # 测试6: 错误处理
    results["错误处理"] = test_error_handling()

    # 打印结果汇总
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {test_name}: [{status}]")

    all_passed = all(results.values())
    print("\n" + ("所有测试通过!" if all_passed else "部分测试失败"))

    return all_passed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="EvidencePack功能测试")
    parser.add_argument("--test", choices=["all", "generate", "retrieve", "baseline", "match", "export", "error", "cleanup"],
                        default="all", help="选择测试类型")
    parser.add_argument("--cleanup", action="store_true", help="测试后清理数据")

    args = parser.parse_args()

    if args.test == "all":
        run_all_tests()
    elif args.test == "generate":
        test_evidence_pack_generation()
    elif args.test == "retrieve":
        test_evidence_pack_retrieval()
    elif args.test == "baseline":
        test_baseline_reference()
    elif args.test == "match":
        test_frame_matcher()
    elif args.test == "export":
        test_evidence_pack_export()
    elif args.test == "error":
        test_error_handling()
    elif args.test == "cleanup":
        cleanup_test_data()

    if args.cleanup:
        cleanup_test_data()
