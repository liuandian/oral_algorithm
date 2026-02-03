# -*- coding: utf-8 -*-
"""
智能抽帧核心算法 - 含语义分析版
功能：
1. 双轨制抽帧（规则触发 + 均匀采样）
2. 每帧生成结构化中间表示（侧别、牙齿类型、区域、异常检测）
3. 保存关键帧及元数据到数据库
"""
import cv2
import numpy as np
import uuid
from pathlib import Path
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.database import AKeyframe
from app.services.storage import storage_service
from app.utils.video import VideoProcessor
from app.config import settings
from app.core.keyframe_analyzer import KeyframeAnalyzer

class KeyframeExtractor:
    def __init__(self, db: Session, enable_analysis: bool = True):
        """
        初始化抽帧器

        Args:
            db: 数据库会话
            enable_analysis: 是否启用语义分析（生成中间表示）
        """
        self.db = db
        self.enable_analysis = enable_analysis
        self.analyzer = KeyframeAnalyzer(debug=False) if enable_analysis else None

    def _format_timestamp(self, seconds: float) -> str:
        """
        将秒数格式化为 MM:SS.mm 格式 (例如 00:06.05)
        保证长度不超过 VARCHAR(10)
        """
        try:
            m = int(seconds // 60)
            s = seconds % 60
            # 格式化为 00:06.05 (8个字符)
            return f"{m:02d}:{s:05.2f}"
        except:
            return "00:00.00"

    def extract_keyframes(self, session_id: str, video_path: str):
        """
        执行双轨制抽帧策略
        """
        processor = None
        try:
            # 1. 初始化视频处理器
            processor = VideoProcessor(video_path)
            duration = processor.get_duration()
            total_frames = processor.get_frame_count()
            fps = processor.get_fps()
            
            print(f"[抽帧] 视频信息: {duration:.2f}s, {total_frames} frames, {fps:.2f} fps")

            # 2. 轨道一：规则触发帧 (Priority Track)
            priority_frames = []
            scan_interval = int(fps) if fps > 0 else 30
            
            print(f"[抽帧] 开始规则扫描: 间隔={scan_interval}帧, 阈值={settings.PRIORITY_FRAME_THRESHOLD}")
            
            for i in range(0, total_frames, scan_interval):
                frame = processor.get_frame(i)
                if frame is not None:
                    # 获取详细分析结果
                    score, detail_scores, reason = self._detect_anomaly_opencv(frame)
                    
                    # 打印详细分析日志
                    log_msg = self._format_detection_log(i, score, detail_scores, reason)
                    print(log_msg)
                    
                    if score > settings.PRIORITY_FRAME_THRESHOLD:
                        # 计算时间戳
                        ts_val = i / fps if fps else 0
                        priority_frames.append({
                            "frame_index": i,
                            "timestamp_val": ts_val,
                            "timestamp_str": self._format_timestamp(ts_val),
                            "score": score,
                            "strategy": "rule_triggered",
                            "reason": reason,
                            "image": frame
                        })
            
            print(f"[抽帧] 规则触发帧数量: {len(priority_frames)} (阈值>{settings.PRIORITY_FRAME_THRESHOLD})")

            # 3. 轨道二：均匀抽帧 (Uniform Track)
            uniform_frames = []
            target_count = settings.UNIFORM_SAMPLE_COUNT
            if duration > 0:
                interval = total_frames / target_count
                for i in range(target_count):
                    idx = int(i * interval)
                    # 避免重复
                    if any(abs(pf["frame_index"] - idx) < 5 for pf in priority_frames):
                        continue
                        
                    frame = processor.get_frame(idx)
                    if frame is not None:
                        ts_val = idx / fps if fps else 0
                        uniform_frames.append({
                            "frame_index": idx,
                            "timestamp_val": ts_val,
                            "timestamp_str": self._format_timestamp(ts_val),
                            "score": 0.0,
                            "strategy": "uniform_sampled",  # 修正：匹配数据库 Enum
                            "reason": "uniform",
                            "image": frame
                        })

            # 4. 合并与去重 (总量控制)
            all_candidates = priority_frames + uniform_frames
            all_candidates.sort(key=lambda x: x["frame_index"])
            
            # 截断到最大数量
            final_frames = all_candidates[:settings.MAX_KEYFRAMES]
            
            print(f"[抽帧] 最终保留帧数: {len(final_frames)}")

            # 5. 保存并入库（含语义分析）
            for idx, item in enumerate(final_frames):
                # 保存图片文件
                image_filename = f"frame_{item['frame_index']}_{uuid.uuid4().hex[:6]}.jpg"
                save_path = storage_service.save_keyframe(
                    session_id=session_id,
                    filename=image_filename,
                    image_data=item['image']
                )

                # 6. 语义分析：生成中间表示
                if self.enable_analysis and self.analyzer is not None:
                    try:
                        meta_tags = self.analyzer.analyze_frame_to_meta_tags(item['image'])
                        meta_tags_dict = meta_tags.model_dump()
                        print(f"[抽帧] 帧 {item['frame_index']} 分析完成: "
                              f"side={meta_tags.side.value}, "
                              f"tooth_type={meta_tags.tooth_type.value}, "
                              f"region={meta_tags.region.value}, "
                              f"issues={[i.value for i in meta_tags.detected_issues]}, "
                              f"conf={meta_tags.confidence_score:.2f}")
                    except Exception as e:
                        print(f"[抽帧] 帧 {item['frame_index']} 语义分析失败: {e}")
                        meta_tags_dict = {
                            "side": "unknown",
                            "tooth_type": "unknown",
                            "region": "unknown",
                            "detected_issues": ["unknown"],
                            "confidence_score": 0.0,
                            "is_verified": False
                        }
                else:
                    meta_tags_dict = {
                        "side": "unknown",
                        "tooth_type": "unknown",
                        "region": "unknown",
                        "detected_issues": ["unknown"],
                        "confidence_score": 0.0,
                        "is_verified": False
                    }

                # 写入数据库
                keyframe = AKeyframe(
                    session_id=session_id,
                    frame_index=item['frame_index'],
                    timestamp_in_video=item['timestamp_str'],
                    extraction_strategy=item['strategy'],
                    extraction_reason=item['reason'],
                    image_path=str(save_path),
                    anomaly_score=item['score'],
                    meta_tags=meta_tags_dict
                )
                self.db.add(keyframe)

            self.db.commit()
            
        except Exception as e:
            print(f"[抽帧错误] {str(e)}")
            self.db.rollback()
            raise e
        finally:
            if processor:
                processor.release()

    def _detect_anomaly_opencv(self, frame: np.ndarray) -> tuple:
        """
        OpenCV 异常检测 - 计算综合异常分数和各维度得分

        检测项目：
        1. 深色沉积物（牙结石、色素）
        2. 黄色牙菌斑
        3. 牙龈红肿
        4. 结构异常

        Returns:
            tuple: (总异常分数, 详细得分字典, 触发原因字符串)
        """
        if frame is None or frame.size == 0:
            return 0.0, {}, "unknown"

        h, w = frame.shape[:2]
        total_pixels = h * w
        if total_pixels == 0:
            return 0.0, {}, "unknown"

        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            anomaly_score = 0.0
            
            # 详细得分记录
            detail_scores = {
                "dark_deposit": 0.0,
                "yellow_plaque": 0.0,
                "gum_issue": 0.0,
            }
            triggered_reasons = []

            # 1. 深色沉积物（低亮度区域）
            mask_black = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 60]))
            black_ratio = np.count_nonzero(mask_black) / total_pixels
            if black_ratio > 0.02 and black_ratio < 0.3:  # 排除全黑帧
                score = min(black_ratio * 4.0, 0.35)
                anomaly_score += score
                detail_scores["dark_deposit"] = round(score, 3)
                if score > 0.1:  # 显著的深色沉积
                    triggered_reasons.append("dark_deposit")

            # 2. 黄色牙菌斑/牙石
            mask_yellow = cv2.inRange(hsv, np.array([15, 40, 80]), np.array([35, 255, 255]))
            yellow_ratio = np.count_nonzero(mask_yellow) / total_pixels
            if yellow_ratio > 0.015:
                score = min(yellow_ratio * 5.0, 0.35)
                anomaly_score += score
                detail_scores["yellow_plaque"] = round(score, 3)
                if score > 0.1:  # 显著的黄色牙菌斑
                    triggered_reasons.append("yellow_plaque")

            # 3. 牙龈红肿（高饱和度红色）
            mask_red1 = cv2.inRange(hsv, np.array([0, 120, 50]), np.array([10, 255, 255]))
            mask_red2 = cv2.inRange(hsv, np.array([160, 120, 50]), np.array([180, 255, 255]))
            red_ratio = (np.count_nonzero(mask_red1) + np.count_nonzero(mask_red2)) / total_pixels
            if red_ratio > 0.08:
                score = min(red_ratio * 2.5, 0.3)
                anomaly_score += score
                detail_scores["gum_issue"] = round(score, 3)
                if score > 0.1:  # 显著的牙龈问题
                    triggered_reasons.append("gum_issue")

            total_score = min(anomaly_score, 1.0)
            
            # 生成原因字符串
            if triggered_reasons:
                reason_str = ",".join(triggered_reasons)
            elif total_score > 0:
                reason_str = "anomaly_detected"
            else:
                reason_str = "none"
            
            return total_score, detail_scores, reason_str

        except Exception as e:
            print(f"[CV Error] Frame analysis failed: {e}")
            return 0.0, {}, "detection_error"

    def _format_detection_log(self, frame_index: int, total_score: float, 
                              detail_scores: dict, reason: str) -> str:
        """
        格式化检测日志输出
        
        Returns:
            格式化的日志字符串
        """
        # 构建详细得分字符串
        details = []
        if detail_scores.get("dark_deposit", 0) > 0:
            details.append(f"dark={detail_scores['dark_deposit']:.2f}")
        if detail_scores.get("yellow_plaque", 0) > 0:
            details.append(f"yellow={detail_scores['yellow_plaque']:.2f}")
        if detail_scores.get("gum_issue", 0) > 0:
            details.append(f"gum={detail_scores['gum_issue']:.2f}")
        
        detail_str = ", ".join(details) if details else "none"
        
        return (f"[抽帧] 规则抽帧 Frame {frame_index} 分析完成: "
                f"total={total_score:.2f}, {detail_str}; 原因={reason}")