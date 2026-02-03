#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
系统集成测试 - 使用真实视频数据

测试完整流程：视频摄取 -> 关键帧提取 -> 语义分析 -> EvidencePack生成
"""
import sys
import os
import cv2
import uuid
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.ingestion import VideoIngestionService
from app.core.keyframe_extractor import KeyframeExtractor
from app.core.keyframe_analyzer import KeyframeAnalyzer
from app.core.evidence_pack import EvidencePackGenerator
from app.core.frame_matcher import FrameMatcherService
from app.core.profile_manager import ProfileManager
from app.models.database import (
    SessionLocal, ASession, BRawVideo, AKeyframe, 
    AEvidencePack, AUserProfile, init_db
)
from app.services.storage import storage_service
from app.utils.video import VideoProcessor
from app.utils.hash import calculate_file_hash


# 测试配置
TEST_USER_ID = f"test_integration_{datetime.now().strftime('%m%d%H%M%S')}"


def get_test_videos():
    """获取测试视频文件列表"""
    video_dir = Path(__file__).parent / "video"
    videos = []
    
    # 优先使用 test1.mp4
    test1 = video_dir / "test1.mp4"
    if test1.exists():
        videos.append(test1)
    
    # 从用户文件夹中选取代表性视频
    user_dirs = [
        "用户1【男性2次】",
        "用户2【2次】", 
        "用户9【2次黑色素+牙结石】",
        "用户12【3次黄牙结石】",
        "用户15【虫洞1次】",
    ]
    
    for user_dir in user_dirs:
        user_path = video_dir / user_dir
        if user_path.exists():
            # 查找该用户下的第一个mp4文件
            for subdir in user_path.iterdir():
                if subdir.is_dir():
                    for mp4_file in subdir.glob("*.mp4"):
                        if mp4_file not in videos:
                            videos.append(mp4_file)
                            break
                if len(videos) >= 5:
                    break
        if len(videos) >= 5:
            break
    
    return videos


def test_video_ingestion():
    """测试1: 视频摄取功能"""
    print("\n" + "="*60)
    print("测试 1: 视频摄取功能")
    print("="*60)
    
    db = SessionLocal()
    videos = get_test_videos()
    
    if not videos:
        print("[跳过] 未找到测试视频")
        return False, None
    
    test_video = videos[0]
    print(f"[信息] 使用测试视频: {test_video}")
    
    try:
        # 创建摄取服务
        ingestion = VideoIngestionService(db)
        
        # 摄取视频
        b_video, session = ingestion.ingest_video(
            video_file_data=None,
            temp_file_path=str(test_video),
            user_id=TEST_USER_ID,
            session_type="quick_check",
            user_description="Integration test video"
        )
        
        print(f"[OK] 视频摄取成功")
        print(f"  - B流视频ID: {b_video.id}")
        print(f"  - Session ID: {session.id}")
        print(f"  - 文件大小: {b_video.file_size_bytes / 1024:.1f} KB")
        duration_str = f"{b_video.duration_seconds:.2f}" if b_video.duration_seconds else "未知"
        print(f"  - 视频时长: {duration_str} 秒")
        
        return True, str(session.id)
        
    except Exception as e:
        db.rollback()
        print(f"[错误] 视频摄取失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None
    finally:
        db.close()


def test_keyframe_extraction(session_id: str):
    """测试2: 关键帧提取功能"""
    print("\n" + "="*60)
    print("测试 2: 关键帧提取功能")
    print("="*60)
    
    db = SessionLocal()
    try:
        # 获取session对应的视频路径
        session = db.query(ASession).filter_by(id=session_id).first()
        if not session:
            print(f"[错误] Session不存在: {session_id}")
            return False
        
        b_video = db.query(BRawVideo).filter_by(id=session.b_video_id).first()
        if not b_video:
            print(f"[错误] B流视频不存在")
            return False
        
        video_path = b_video.file_path
        print(f"[信息] 视频路径: {video_path}")
        
        # 清理已有的关键帧
        deleted = db.query(AKeyframe).filter_by(session_id=session_id).delete()
        db.commit()
        if deleted:
            print(f"[信息] 清理了 {deleted} 个已存在的关键帧")
        
        # 创建提取器
        extractor = KeyframeExtractor(db, enable_analysis=True)
        
        # 执行抽帧
        print(f"[信息] 开始抽帧...")
        extractor.extract_keyframes(session_id, video_path)
        
        # 验证结果
        keyframes = db.query(AKeyframe).filter_by(session_id=session_id).all()
        
        if not keyframes:
            print("[错误] 未提取到关键帧")
            return False
        
        print(f"[OK] 关键帧提取成功: {len(keyframes)} 帧")
        
        # 统计策略分布
        rule_triggered = [kf for kf in keyframes if kf.extraction_strategy == "rule_triggered"]
        uniform_sampled = [kf for kf in keyframes if kf.extraction_strategy == "uniform_sampled"]
        
        print(f"  - 规则触发帧: {len(rule_triggered)} 个")
        print(f"  - 均匀采样帧: {len(uniform_sampled)} 个")
        
        # 显示前3帧的详细信息
        print(f"\n  关键帧详情 (前3帧):")
        for kf in keyframes[:3]:
            meta = kf.meta_tags or {}
            print(f"    - Frame {kf.frame_index} @ {kf.timestamp_in_video}")
            print(f"      策略: {kf.extraction_strategy}, 异常分数: {kf.anomaly_score:.3f}")
            print(f"      分析: side={meta.get('side', 'unknown')}, "
                  f"type={meta.get('tooth_type', 'unknown')}, "
                  f"region={meta.get('region', 'unknown')}")
        
        # 更新session状态
        session.processing_status = "completed"
        db.commit()
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"[错误] 关键帧提取失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_semantic_analysis():
    """测试3: 语义分析功能"""
    print("\n" + "="*60)
    print("测试 3: 语义分析功能")
    print("="*60)
    
    db = SessionLocal()
    try:
        # 获取最近完成的session的关键帧
        keyframes = db.query(AKeyframe).filter(
            AKeyframe.session_id.in_(
                db.query(ASession.id).filter_by(user_id=TEST_USER_ID)
            )
        ).all()
        
        if not keyframes:
            print("[跳过] 没有可用的关键帧")
            return False
        
        analyzer = KeyframeAnalyzer(debug=False)
        
        # 分析前5帧
        sample_frames = keyframes[:5]
        results = []
        
        print(f"[信息] 分析 {len(sample_frames)} 个关键帧...")
        
        for kf in sample_frames:
            if not Path(kf.image_path).exists():
                continue
                
            image = cv2.imread(str(kf.image_path))
            if image is None:
                continue
            
            result = analyzer.analyze_frame(image)
            results.append({
                "frame_id": str(kf.id),
                "side": result.side.value,
                "tooth_type": result.tooth_type.value,
                "region": result.region.value,
                "issues": [i.value for i in result.detected_issues],
                "confidence": result.confidence_score
            })
        
        if not results:
            print("[错误] 未能分析任何关键帧")
            return False
        
        print(f"[OK] 语义分析完成: {len(results)} 帧")
        
        # 统计
        side_dist = {}
        region_dist = {}
        issue_count = {}
        
        for r in results:
            side_dist[r["side"]] = side_dist.get(r["side"], 0) + 1
            region_dist[r["region"]] = region_dist.get(r["region"], 0) + 1
            for issue in r["issues"]:
                issue_count[issue] = issue_count.get(issue, 0) + 1
        
        print(f"\n  分析统计:")
        print(f"    侧别分布: {side_dist}")
        print(f"    区域分布: {region_dist}")
        print(f"    问题统计: {issue_count}")
        
        avg_conf = sum(r["confidence"] for r in results) / len(results)
        print(f"    平均置信度: {avg_conf:.2f}")
        
        return True
        
    except Exception as e:
        print(f"[错误] 语义分析失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_evidence_pack_generation(session_id: str):
    """测试4: EvidencePack生成功能"""
    print("\n" + "="*60)
    print("测试 4: EvidencePack生成功能")
    print("="*60)
    
    db = SessionLocal()
    try:
        generator = EvidencePackGenerator(db)
        
        # 生成EvidencePack
        evidence_pack = generator.generate_evidence_pack(session_id)
        
        print(f"[OK] EvidencePack生成成功")
        print(f"  - Session ID: {evidence_pack.session_id}")
        print(f"  - 总帧数: {evidence_pack.total_frames}")
        print(f"  - Session类型: {evidence_pack.session_type}")
        
        # 验证基线参考
        if evidence_pack.baseline_reference:
            br = evidence_pack.baseline_reference
            print(f"  - 基线参考: has_baseline={br.has_baseline}, mode={br.comparison_mode}")
        
        # 验证数据库记录
        db_pack = db.query(AEvidencePack).filter_by(session_id=session_id).first()
        if db_pack:
            print(f"[OK] 数据库记录验证通过")
            print(f"  - EvidencePack ID: {db_pack.id}")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"[错误] EvidencePack生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_frame_matcher():
    """测试5: 帧匹配功能"""
    print("\n" + "="*60)
    print("测试 5: 帧匹配功能")
    print("="*60)
    
    db = SessionLocal()
    try:
        # 先创建基线数据
        videos = get_test_videos()
        
        if len(videos) < 2:
            print("[跳过] 需要至少2个视频来测试帧匹配")
            return False
        
        # 创建基线session（7个区域）
        ingestion = VideoIngestionService(db)
        
        for zone_id in range(1, 8):
            if zone_id > len(videos):
                break
            
            b_video, session = ingestion.ingest_video(
                video_file_data=None,
                temp_file_path=str(videos[(zone_id - 1) % len(videos)]),
                user_id=TEST_USER_ID,
                session_type="baseline",
                zone_id=zone_id
            )
            
            # 提取关键帧
            extractor = KeyframeExtractor(db, enable_analysis=True)
            extractor.extract_keyframes(str(session.id), b_video.file_path)
            
            ingestion.update_session_status(str(session.id), "completed")
        
        # 标记基线完成
        profile_mgr = ProfileManager(db)
        profile = profile_mgr.get_or_create_profile(TEST_USER_ID)
        profile.baseline_completed = True
        profile.baseline_completion_date = datetime.now()
        db.commit()
        
        print(f"[OK] 创建基线数据完成")
        
        # 测试帧匹配服务
        matcher = FrameMatcherService(db)
        
        # 获取Quick Check关键帧
        qc_session = db.query(ASession).filter_by(
            user_id=TEST_USER_ID,
            session_type="quick_check"
        ).first()
        
        if qc_session:
            qc_keyframes = db.query(AKeyframe).filter_by(
                session_id=qc_session.id
            ).all()
            
            matches = matcher.match_frames_to_baseline(qc_keyframes, TEST_USER_ID)
            
            print(f"[OK] 帧匹配完成")
            print(f"  - Quick Check帧数: {len(qc_keyframes)}")
            print(f"  - 匹配到的基线帧: {len(matches)}")
            
            # 获取区域覆盖情况
            coverage = matcher.get_zone_coverage(TEST_USER_ID)
            covered = sum(1 for v in coverage.values() if v)
            print(f"  - 区域覆盖: {covered}/7")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"[错误] 帧匹配测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_user_profile():
    """测试6: 用户档案管理"""
    print("\n" + "="*60)
    print("测试 6: 用户档案管理")
    print("="*60)
    
    db = SessionLocal()
    try:
        profile_mgr = ProfileManager(db)
        
        # 获取或创建档案
        profile = profile_mgr.get_or_create_profile(TEST_USER_ID)
        
        print(f"[OK] 用户档案")
        print(f"  - 用户ID: {profile.user_id}")
        print(f"  - 基线完成: {profile.baseline_completed}")
        print(f"  - Quick Check次数: {profile.total_quick_checks}")
        
        # 添加用户事件
        event = profile_mgr.add_user_event(
            user_id=TEST_USER_ID,
            event_type="checkup",
            event_date=datetime.now(),
            event_description="Integration test event"
        )
        
        print(f"[OK] 添加用户事件: {event.id}")
        
        # 添加关注点
        concern = profile_mgr.add_concern_point(
            user_id=TEST_USER_ID,
            concern_type="dark_spot",
            source_type="system_detected",
            zone_id=2,
            location_description="上门牙右侧",
            severity="mild"
        )
        
        print(f"[OK] 添加关注点: {concern.id}")
        
        # 获取活跃关注点
        active_concerns = profile_mgr.get_active_concerns(TEST_USER_ID)
        print(f"  - 活跃关注点: {len(active_concerns)}")
        
        # 获取扩展档案
        extended = profile_mgr.get_extended_profile(TEST_USER_ID)
        print(f"[OK] 扩展档案信息")
        print(f"  - 活跃关注点数: {extended.get('active_concerns_count', 0)}")
        print(f"  - 近30天事件数: {extended.get('recent_events_count', 0)}")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"[错误] 用户档案测试失败: {e}")
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
        # 删除用户档案（级联删除事件和关注点）
        db.query(AUserProfile).filter(
            AUserProfile.user_id.like("test_integration_%")
        ).delete(synchronize_session=False)
        
        # 获取测试session
        sessions = db.query(ASession).filter(
            ASession.user_id.like("test_integration_%")
        ).all()
        
        count = 0
        for session in sessions:
            # 删除关键帧
            db.query(AKeyframe).filter_by(session_id=session.id).delete()
            # 删除EvidencePack
            db.query(AEvidencePack).filter_by(session_id=session.id).delete()
            # 删除B流记录
            db.query(BRawVideo).filter_by(id=session.b_video_id).delete()
            # 删除Session
            db.delete(session)
            count += 1
        
        db.commit()
        print(f"[OK] 已清理 {count} 个测试Session及相关数据")
        
    except Exception as e:
        db.rollback()
        print(f"[错误] 清理失败: {e}")
    finally:
        db.close()


def run_all_tests():
    """运行所有集成测试"""
    print("="*60)
    print("系统集成测试 - 使用真实视频数据")
    print("="*60)
    print(f"测试用户ID: {TEST_USER_ID}")
    
    results = {}
    session_id = None
    
    # 测试1: 视频摄取
    success, session_id = test_video_ingestion()
    results["视频摄取"] = success
    
    if not success or not session_id:
        print("\n[严重] 视频摄取失败，后续测试无法继续")
        return results
    
    # 测试2: 关键帧提取
    results["关键帧提取"] = test_keyframe_extraction(session_id)
    
    # 测试3: 语义分析
    results["语义分析"] = test_semantic_analysis()
    
    # 测试4: EvidencePack生成
    results["EvidencePack生成"] = test_evidence_pack_generation(session_id)
    
    # 测试5: 帧匹配
    results["帧匹配"] = test_frame_matcher()
    
    # 测试6: 用户档案
    results["用户档案"] = test_user_profile()
    
    # 打印结果汇总
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {test_name}: [{status}]")
    
    all_passed = all(results.values())
    passed_count = sum(results.values())
    total_count = len(results)
    
    print(f"\n总计: {passed_count}/{total_count} 通过")
    
    if all_passed:
        print("\n🎉 所有测试通过!")
    else:
        print("\n⚠️ 部分测试失败")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="系统集成测试")
    parser.add_argument("--cleanup", action="store_true", help="清理所有测试数据")
    
    args = parser.parse_args()
    
    if args.cleanup:
        cleanup_test_data()
    else:
        try:
            run_all_tests()
        finally:
            # 可选：测试后自动清理
            # cleanup_test_data()
            pass
