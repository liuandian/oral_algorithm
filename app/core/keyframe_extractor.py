# -*- coding: utf-8 -*-
"""
智能抽帧核心算法 - 最终修正版
修复了时间戳长度溢出和枚举类型不匹配的问题
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

class KeyframeExtractor:
    def __init__(self, db: Session):
        """
        初始化抽帧器
        :param db: 数据库会话
        """
        self.db = db

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
                        priority_frames.append({
                            "frame_index": i,
                            "timestamp_val": ts_val,
                            "timestamp_str": self._format_timestamp(ts_val),
                            "score": score,
                            "strategy": "rule_triggered",  # 修正：匹配数据库 Enum
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
                            "image": frame
                        })

            # 4. 合并与去重 (总量控制)
            all_candidates = priority_frames + uniform_frames
            all_candidates.sort(key=lambda x: x["frame_index"])
            
            # 截断到最大数量
            final_frames = all_candidates[:settings.MAX_KEYFRAMES]
            
            print(f"[抽帧] 最终保留帧数: {len(final_frames)}")

            # 5. 保存并入库
            for idx, item in enumerate(final_frames):
                # 保存图片文件
                image_filename = f"frame_{item['frame_index']}_{uuid.uuid4().hex[:6]}.jpg"
                save_path = storage_service.save_keyframe(
                    session_id=session_id,
                    filename=image_filename,
                    image_data=item['image']
                )
                
                # 写入数据库
                keyframe = AKeyframe(
                    session_id=session_id,
                    frame_index=item['frame_index'],
                    timestamp_in_video=item['timestamp_str'], # 使用格式化后的字符串
                    extraction_strategy=item['strategy'],
                    image_path=str(save_path),
                    anomaly_score=item['score'],
                    meta_tags={"status": "unprocessed"} 
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
        OpenCV 异常检测
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

            # 1. 黑色沉积物
            mask_black = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 60]))
            black_ratio = np.count_nonzero(mask_black) / total_pixels
            if black_ratio > 0.05:
                anomaly_score += min(black_ratio * 3.0, 0.4)

            # 2. 黄色牙菌斑
            mask_yellow = cv2.inRange(hsv, np.array([20, 40, 40]), np.array([35, 255, 255]))
            yellow_ratio = np.count_nonzero(mask_yellow) / total_pixels
            if yellow_ratio > 0.03:
                anomaly_score += min(yellow_ratio * 3.0, 0.4)

            # 3. 牙龈红肿
            mask_red1 = cv2.inRange(hsv, np.array([0, 100, 50]), np.array([10, 255, 255]))
            mask_red2 = cv2.inRange(hsv, np.array([160, 100, 50]), np.array([180, 255, 255]))
            red_ratio = (np.count_nonzero(mask_red1) + np.count_nonzero(mask_red2)) / total_pixels
            if red_ratio > 0.10:
                anomaly_score += min(red_ratio * 2.0, 0.4)

            return min(anomaly_score, 1.0)
            
        except Exception as e:
            print(f"[CV Error] Frame analysis failed: {e}")
            return 0.0