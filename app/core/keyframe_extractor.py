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
            
            for i in range(0, total_frames, scan_interval):
                frame = processor.get_frame(i)
                if frame is not None:
                    score = self._detect_anomaly_opencv(frame)
                    if score > settings.PRIORITY_FRAME_THRESHOLD:
                        # 计算时间戳
                        ts_val = i / fps if fps else 0
                        # 获取触发原因
                        trigger_reason = self._get_anomaly_reason(frame, score)
                        priority_frames.append({
                            "frame_index": i,
                            "timestamp_val": ts_val,
                            "timestamp_str": self._format_timestamp(ts_val),
                            "score": score,
                            "strategy": "rule_triggered",
                            "reason": trigger_reason,
                            "image": frame
                        })
            
            print(f"[抽帧] 规则触发帧数量: {len(priority_frames)}")

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

    def _detect_anomaly_opencv(self, frame: np.ndarray) -> float:
        """
        OpenCV 异常检测 - 计算综合异常分数

        检测项目：
        1. 深色沉积物（牙结石、色素）
        2. 黄色牙菌斑
        3. 牙龈红肿
        4. 结构异常
        """
        if frame is None or frame.size == 0:
            return 0.0

        h, w = frame.shape[:2]
        total_pixels = h * w
        if total_pixels == 0:
            return 0.0

        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            anomaly_score = 0.0

            # 1. 深色沉积物（低亮度区域）
            mask_black = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 60]))
            black_ratio = np.count_nonzero(mask_black) / total_pixels
            if black_ratio > 0.02 and black_ratio < 0.3:  # 排除全黑帧
                anomaly_score += min(black_ratio * 4.0, 0.35)

            # 2. 黄色牙菌斑/牙石
            mask_yellow = cv2.inRange(hsv, np.array([15, 40, 80]), np.array([35, 255, 255]))
            yellow_ratio = np.count_nonzero(mask_yellow) / total_pixels
            if yellow_ratio > 0.015:
                anomaly_score += min(yellow_ratio * 5.0, 0.35)

            # 3. 牙龈红肿（高饱和度红色）
            mask_red1 = cv2.inRange(hsv, np.array([0, 120, 50]), np.array([10, 255, 255]))
            mask_red2 = cv2.inRange(hsv, np.array([160, 120, 50]), np.array([180, 255, 255]))
            red_ratio = (np.count_nonzero(mask_red1) + np.count_nonzero(mask_red2)) / total_pixels
            if red_ratio > 0.08:
                anomaly_score += min(red_ratio * 2.5, 0.3)

            return min(anomaly_score, 1.0)

        except Exception as e:
            print(f"[CV Error] Frame analysis failed: {e}")
            return 0.0

    def _get_anomaly_reason(self, frame: np.ndarray, score: float) -> str:
        """
        获取异常触发的具体原因

        Args:
            frame: 图像帧
            score: 异常分数

        Returns:
            触发原因字符串
        """
        if frame is None or frame.size == 0:
            return "unknown"

        reasons = []

        try:
            h, w = frame.shape[:2]
            total_pixels = h * w
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            # 检测深色沉积
            mask_black = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 60]))
            black_ratio = np.count_nonzero(mask_black) / total_pixels
            if black_ratio > 0.02 and black_ratio < 0.3:
                reasons.append("dark_deposit")

            # 检测黄色牙菌斑
            mask_yellow = cv2.inRange(hsv, np.array([15, 40, 80]), np.array([35, 255, 255]))
            yellow_ratio = np.count_nonzero(mask_yellow) / total_pixels
            if yellow_ratio > 0.015:
                reasons.append("yellow_plaque")

            # 检测牙龈红肿
            mask_red1 = cv2.inRange(hsv, np.array([0, 120, 50]), np.array([10, 255, 255]))
            mask_red2 = cv2.inRange(hsv, np.array([160, 120, 50]), np.array([180, 255, 255]))
            red_ratio = (np.count_nonzero(mask_red1) + np.count_nonzero(mask_red2)) / total_pixels
            if red_ratio > 0.08:
                reasons.append("gum_issue")

            if reasons:
                return ",".join(reasons)
            else:
                return "anomaly_detected"

        except Exception:
            return "detection_error"