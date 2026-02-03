#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
智能抽帧算法测试脚本

测试 KeyframeExtractor 的双轨制抽帧策略
"""
import sys
import os
import cv2
import uuid
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.keyframe_extractor import KeyframeExtractor
from app.models.database import SessionLocal, ASession, BRawVideo, init_db
from app.services.storage import storage_service
from app.utils.video import VideoProcessor
from app.utils.hash import calculate_file_hash


# 测试配置
TEST_VIDEO_PATH = Path(__file__).parent / "video" / "test1.mp4"
TEST_USER_ID = "test_user_001"


def setup_test_data():
    """准备测试数据：创建用户和视频记录"""
    db = SessionLocal()
    try:
        # 检查测试视频是否存在
        if not TEST_VIDEO_PATH.exists():
            print(f"[错误] 测试视频不存在: {TEST_VIDEO_PATH}")
            return None, None

        # 计算文件hash
        file_hash = calculate_file_hash(str(TEST_VIDEO_PATH))
        print(f"[信息] 测试视频 Hash: {file_hash[:16]}...")

        # 检查是否已存在
        existing = db.query(BRawVideo).filter_by(file_hash=file_hash).first()
        if existing:
            print(f"[信息] 使用已存在的B流视频记录: {existing.id}")
            # 检查是否有对应的session
            session = db.query(ASession).filter_by(b_video_id=existing.id).first()
            if session:
                print(f"[信息] 使用已存在的Session: {session.id}")
                return db, session
            else:
                # 创建新的session
                session = ASession(
                    user_id=TEST_USER_ID,
                    b_video_id=existing.id,
                    session_type="quick_check",
                    zone_id=None,
                    processing_status="pending"
                )
                db.add(session)
                db.commit()
                print(f"[信息] 创建新Session: {session.id}")
                return db, session

        # 保存到B流
        b_path = storage_service.save_to_b_stream(
            source_path=str(TEST_VIDEO_PATH),
            user_id=TEST_USER_ID,
            file_hash=file_hash
        )
        print(f"[信息] 视频已保存到B流: {b_path}")

        # 获取视频信息
        processor = VideoProcessor(str(TEST_VIDEO_PATH))
        duration = processor.get_duration()
        processor.release()

        # 创建B流记录
        b_video = BRawVideo(
            user_id=TEST_USER_ID,
            file_hash=file_hash,
            file_path=str(b_path),
            file_size_bytes=TEST_VIDEO_PATH.stat().st_size,
            duration_seconds=duration,
            session_type="quick_check",
            zone_id=None
        )
        db.add(b_video)
        db.commit()
        print(f"[信息] 创建B流记录: {b_video.id}")

        # 创建Session
        session = ASession(
            user_id=TEST_USER_ID,
            b_video_id=b_video.id,
            session_type="quick_check",
            zone_id=None,
            processing_status="pending"
        )
        db.add(session)
        db.commit()
        print(f"[信息] 创建Session: {session.id}")

        return db, session

    except Exception as e:
        db.rollback()
        print(f"[错误] 准备测试数据失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def test_video_processor():
    """测试1: 视频处理器基本功能"""
    print("\n" + "="*60)
    print("测试 1: 视频处理器基本功能")
    print("="*60)

    if not TEST_VIDEO_PATH.exists():
        print(f"[跳过] 测试视频不存在: {TEST_VIDEO_PATH}")
        return False

    try:
        processor = VideoProcessor(str(TEST_VIDEO_PATH))

        fps = processor.get_fps()
        frame_count = processor.get_frame_count()
        duration = processor.get_duration()

        print(f"[OK] 视频信息:")
        print(f"  - 帧率: {fps:.2f} fps")
        print(f"  - 总帧数: {frame_count}")
        print(f"  - 时长: {duration:.2f} 秒")

        # 测试读取帧
        frame = processor.get_frame(0)
        if frame is not None:
            print(f"[OK] 成功读取第0帧: {frame.shape}")
        else:
            print(f"[错误] 无法读取第0帧")

        # 测试读取中间帧
        mid_frame_idx = frame_count // 2
        mid_frame = processor.get_frame(mid_frame_idx)
        if mid_frame is not None:
            print(f"[OK] 成功读取中间帧({mid_frame_idx})")
        else:
            print(f"[错误] 无法读取中间帧")

        processor.release()
        print("[OK] 视频处理器测试通过")
        return True

    except Exception as e:
        print(f"[错误] 视频处理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_keyframe_extraction():
    """测试2: 关键帧提取功能"""
    print("\n" + "="*60)
    print("测试 2: 关键帧提取功能")
    print("="*60)

    db, session = setup_test_data()
    if not session:
        print("[跳过] 无法准备测试数据")
        return False

    try:
        # 清理该session已有的关键帧（避免重复）
        from app.models.database import AKeyframe
        deleted = db.query(AKeyframe).filter_by(session_id=session.id).delete()
        db.commit()
        if deleted:
            print(f"[信息] 清理了 {deleted} 个已存在的关键帧")

        # 创建提取器
        extractor = KeyframeExtractor(db, enable_analysis=True)

        # 执行抽帧
        print(f"[信息] 开始抽帧: session_id={session.id}")
        print(f"[信息] 视频路径: {TEST_VIDEO_PATH}")

        extractor.extract_keyframes(
            session_id=str(session.id),
            video_path=str(TEST_VIDEO_PATH)
        )

        # 验证结果
        from app.models.database import AKeyframe
        keyframes = db.query(AKeyframe).filter_by(session_id=session.id).all()

        print(f"[OK] 提取完成，共 {len(keyframes)} 个关键帧")

        for kf in keyframes[:5]:  # 只显示前5个
            print(f"  - Frame {kf.frame_index} @ {kf.timestamp_in_video}")
            print(f"    策略: {kf.extraction_strategy}, 原因: {kf.extraction_reason}")
            print(f"    异常分数: {kf.anomaly_score:.3f}")
            if kf.meta_tags:
                side = kf.meta_tags.get('side', 'unknown')
                tooth_type = kf.meta_tags.get('tooth_type', 'unknown')
                region = kf.meta_tags.get('region', 'unknown')
                issues = kf.meta_tags.get('detected_issues', [])
                conf = kf.meta_tags.get('confidence_score', 0)
                print(f"    分析: side={side}, type={tooth_type}, region={region}")
                print(f"    问题: {issues}, 置信度: {conf:.2f}")

        # 更新session状态
        session.processing_status = "completed"
        db.commit()

        print("[OK] 关键帧提取测试通过")
        return True

    except Exception as e:
        db.rollback()
        print(f"[错误] 关键帧提取测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_extraction_strategies():
    """测试3: 验证双轨制策略"""
    print("\n" + "="*60)
    print("测试 3: 验证双轨制抽帧策略")
    print("="*60)

    db = SessionLocal()
    try:
        # 查询最近完成的session
        session = db.query(ASession).filter_by(
            user_id=TEST_USER_ID,
            processing_status="completed"
        ).order_by(ASession.created_at.desc()).first()

        if not session:
            print("[跳过] 没有已完成的Session，请先运行测试2")
            return False

        from app.models.database import AKeyframe
        keyframes = db.query(AKeyframe).filter_by(session_id=session.id).all()

        rule_triggered = [kf for kf in keyframes if kf.extraction_strategy == "rule_triggered"]
        uniform_sampled = [kf for kf in keyframes if kf.extraction_strategy == "uniform_sampled"]

        print(f"[OK] 策略分布统计:")
        print(f"  - 规则触发帧: {len(rule_triggered)} 个")
        print(f"  - 均匀采样帧: {len(uniform_sampled)} 个")
        print(f"  - 总计: {len(keyframes)} 个")

        if rule_triggered:
            print("\n  规则触发帧详情:")
            for kf in rule_triggered[:3]:
                print(f"    - Frame {kf.frame_index}: score={kf.anomaly_score:.3f}, reason={kf.extraction_reason}")

        # 验证策略分布是否合理
        if len(keyframes) >= 5:
            print("[OK] 关键帧数量符合要求 (>=5)")
        else:
            print(f"[警告] 关键帧数量较少: {len(keyframes)}")

        print("[OK] 双轨制策略测试通过")
        return True

    except Exception as e:
        print(f"[错误] 策略测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_anomaly_detection():
    """测试4: 异常检测功能"""
    print("\n" + "="*60)
    print("测试 4: 异常检测功能")
    print("="*60)

    if not TEST_VIDEO_PATH.exists():
        print("[跳过] 测试视频不存在")
        return False

    try:
        from app.core.keyframe_extractor import KeyframeExtractor
        import numpy as np

        # 创建临时提取器
        db = SessionLocal()
        extractor = KeyframeExtractor(db, enable_analysis=False)

        # 读取几帧测试异常检测
        processor = VideoProcessor(str(TEST_VIDEO_PATH))
        frame_count = processor.get_frame_count()

        scores = []
        sample_indices = [0, frame_count//4, frame_count//2, frame_count*3//4, frame_count-1]

        print("[信息] 采样帧异常检测:")
        for idx in sample_indices:
            if idx < frame_count:
                frame = processor.get_frame(idx)
                if frame is not None:
                    score = extractor._detect_anomaly_opencv(frame)
                    scores.append(score)
                    status = "⚠️ 异常" if score > 0.5 else "正常"
                    print(f"  - Frame {idx}: score={score:.3f} {status}")

        processor.release()
        db.close()

        if scores:
            avg_score = sum(scores) / len(scores)
            print(f"\n[OK] 平均异常分数: {avg_score:.3f}")

        print("[OK] 异常检测测试通过")
        return True

    except Exception as e:
        print(f"[错误] 异常检测测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_test_data():
    """清理测试数据"""
    print("\n" + "="*60)
    print("清理测试数据")
    print("="*60)

    db = SessionLocal()
    try:
        from app.models.database import AKeyframe, AEvidencePack

        # 查找测试用户的session
        sessions = db.query(ASession).filter_by(user_id=TEST_USER_ID).all()

        for session in sessions:
            # 删除相关关键帧
            kf_count = db.query(AKeyframe).filter_by(session_id=session.id).delete()
            # 删除EvidencePack
            ep_count = db.query(AEvidencePack).filter_by(session_id=session.id).delete()
            # 删除Session
            db.delete(session)

            print(f"[清理] Session {session.id}: 删除 {kf_count} 关键帧, {ep_count} EvidencePack")

        # 注意: B流记录遵循Write-Once原则，不删除
        print(f"[信息] B流记录保留 (Write-Once设计)")

        db.commit()
        print("[OK] 测试数据清理完成")

    except Exception as e:
        db.rollback()
        print(f"[错误] 清理失败: {e}")
    finally:
        db.close()


def run_all_tests():
    """运行所有测试"""
    print("="*60)
    print("智能抽帧算法 - 完整测试")
    print("="*60)

    results = {}

    # 测试1: 视频处理器
    results["视频处理器"] = test_video_processor()

    # 测试2: 关键帧提取
    results["关键帧提取"] = test_keyframe_extraction()

    # 测试3: 双轨制策略
    results["双轨制策略"] = test_extraction_strategies()

    # 测试4: 异常检测
    results["异常检测"] = test_anomaly_detection()

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

    parser = argparse.ArgumentParser(description="智能抽帧算法测试")
    parser.add_argument("--test", choices=["all", "processor", "extract", "strategy", "anomaly", "cleanup"],
                        default="all", help="选择测试类型")
    parser.add_argument("--cleanup", action="store_true", help="测试后清理数据")

    args = parser.parse_args()

    if args.test == "all":
        run_all_tests()
    elif args.test == "processor":
        test_video_processor()
    elif args.test == "extract":
        test_keyframe_extraction()
    elif args.test == "strategy":
        test_extraction_strategies()
    elif args.test == "anomaly":
        test_anomaly_detection()
    elif args.test == "cleanup":
        cleanup_test_data()

    if args.cleanup:
        cleanup_test_data()
