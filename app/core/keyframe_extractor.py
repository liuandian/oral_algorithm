"""
双轨制关键帧提取算法
核心模块：规则触发帧 + 均匀抽帧
"""
import cv2
import numpy as np
from typing import List, Tuple, Dict
from pathlib import Path
from dataclasses import dataclass

from app.utils.video import VideoProcessor, detect_frame_quality
from app.config import settings


@dataclass
class ExtractedFrame:
    """提取的关键帧数据"""
    frame_index: int
    timestamp_seconds: float
    timestamp_formatted: str  # "MM:SS"
    frame_image: np.ndarray
    extraction_strategy: str  # 'rule_triggered' or 'uniform_sampled'
    anomaly_score: float
    meta_info: Dict  # 额外元数据


class KeyframeExtractor:
    """双轨制关键帧提取器"""

    def __init__(
        self,
        video_path: str,
        max_frames: int = None,
        min_frames: int = None,
        uniform_sample_count: int = None,
        priority_threshold: float = None
    ):
        """
        初始化提取器

        Args:
            video_path: 视频文件路径
            max_frames: 最大关键帧数量
            min_frames: 最小关键帧数量
            uniform_sample_count: 均匀采样候选帧数量
            priority_threshold: 优先帧异常阈值
        """
        self.video_path = video_path
        self.max_frames = max_frames or settings.MAX_KEYFRAMES
        self.min_frames = min_frames or settings.MIN_KEYFRAMES
        self.uniform_sample_count = uniform_sample_count or settings.UNIFORM_SAMPLE_COUNT
        self.priority_threshold = priority_threshold or settings.PRIORITY_FRAME_THRESHOLD

        self.video_processor = VideoProcessor(video_path)

        # 提取结果
        self.priority_frames: List[ExtractedFrame] = []  # 规则触发帧
        self.uniform_frames: List[ExtractedFrame] = []   # 均匀采样帧
        self.final_frames: List[ExtractedFrame] = []     # 最终合并结果

    def extract(self) -> List[ExtractedFrame]:
        """
        执行双轨制提取

        Returns:
            最终关键帧列表
        """
        print(f"[抽帧] 开始处理视频: {self.video_path}")
        print(f"[抽帧] 视频信息: {self.video_processor.duration:.1f}秒, {self.video_processor.frame_count}帧")

        # 第一轨：规则触发帧检测
        self._extract_priority_frames()

        # 第二轨：均匀抽帧填充
        self._extract_uniform_frames()

        # 合并去重
        self._merge_and_deduplicate()

        print(f"[抽帧] 完成: 优先帧 {len(self.priority_frames)}, 均匀帧 {len(self.uniform_frames)}, 最终 {len(self.final_frames)}")

        return self.final_frames

    def _extract_priority_frames(self):
        """第一轨：规则触发帧（基于OpenCV传统算法）"""
        print("[抽帧] 第一轨：规则触发帧检测")

        # 均匀抽取候选帧进行检测
        candidate_frames = self.video_processor.extract_uniform_frames(self.uniform_sample_count)

        for frame_index, timestamp, frame_image in candidate_frames:
            # 使用传统 CV 算法检测异常
            anomaly_score = self._detect_anomaly_opencv(frame_image)

            # 判断是否触发优先级
            if anomaly_score >= self.priority_threshold:
                extracted = ExtractedFrame(
                    frame_index=frame_index,
                    timestamp_seconds=timestamp,
                    timestamp_formatted=self.video_processor.format_timestamp(timestamp),
                    frame_image=frame_image,
                    extraction_strategy="rule_triggered",
                    anomaly_score=anomaly_score,
                    meta_info={}
                )
                self.priority_frames.append(extracted)
                print(f"  ✓ 优先帧: 索引 {frame_index}, 时间 {extracted.timestamp_formatted}, 得分 {anomaly_score:.2f}")

    def _extract_uniform_frames(self):
        """第二轨：均匀抽帧填充"""
        print("[抽帧] 第二轨：均匀抽帧填充")

        # 计算还需要多少帧
        remaining = self.max_frames - len(self.priority_frames)
        if remaining <= 0:
            print(f"  优先帧已满 ({len(self.priority_frames)})，跳过均匀抽帧")
            return

        # 均匀抽取
        num_uniform = min(remaining, self.uniform_sample_count)
        uniform_candidates = self.video_processor.extract_uniform_frames(num_uniform)

        for frame_index, timestamp, frame_image in uniform_candidates:
            # 检查是否与优先帧重复
            if self._is_duplicate(frame_index):
                continue

            # 计算质量分数
            quality_score = detect_frame_quality(frame_image)

            extracted = ExtractedFrame(
                frame_index=frame_index,
                timestamp_seconds=timestamp,
                timestamp_formatted=self.video_processor.format_timestamp(timestamp),
                frame_image=frame_image,
                extraction_strategy="uniform_sampled",
                anomaly_score=0.0,  # 均匀帧无异常检测
                meta_info={"quality_score": quality_score}
            )
            self.uniform_frames.append(extracted)

        print(f"  ✓ 均匀帧: {len(self.uniform_frames)} 帧")

    def _merge_and_deduplicate(self):
        """合并两轨结果并去重"""
        print("[抽帧] 合并去重")

        # 优先帧优先级更高
        all_frames = self.priority_frames + self.uniform_frames

        # 按帧索引排序
        all_frames.sort(key=lambda x: x.frame_index)

        # 去重（保留异常分数更高的）
        seen_indices = set()
        for frame in all_frames:
            if frame.frame_index not in seen_indices:
                self.final_frames.append(frame)
                seen_indices.add(frame.frame_index)

        # 限制最大数量
        if len(self.final_frames) > self.max_frames:
            # 优先保留高分帧
            self.final_frames.sort(key=lambda x: x.anomaly_score, reverse=True)
            self.final_frames = self.final_frames[:self.max_frames]

            # 重新按时间排序
            self.final_frames.sort(key=lambda x: x.frame_index)

        # 确保满足最小数量
        if len(self.final_frames) < self.min_frames:
            print(f"  [警告] 关键帧数量不足 ({len(self.final_frames)} < {self.min_frames})，补充均匀帧")
            self._补充至最小数量()

    def _补充至最小数量(self):
        """补充帧至最小数量"""
        current_count = len(self.final_frames)
        needed = self.min_frames - current_count

        # 提取更多均匀帧
        additional_frames = self.video_processor.extract_uniform_frames(needed + current_count)

        for frame_index, timestamp, frame_image in additional_frames:
            if self._is_duplicate_in_final(frame_index):
                continue

            extracted = ExtractedFrame(
                frame_index=frame_index,
                timestamp_seconds=timestamp,
                timestamp_formatted=self.video_processor.format_timestamp(timestamp),
                frame_image=frame_image,
                extraction_strategy="uniform_sampled",
                anomaly_score=0.0,
                meta_info={}
            )
            self.final_frames.append(extracted)

            if len(self.final_frames) >= self.min_frames:
                break

        # 重新排序
        self.final_frames.sort(key=lambda x: x.frame_index)

    def _is_duplicate(self, frame_index: int) -> bool:
        """检查帧索引是否与优先帧重复"""
        return any(f.frame_index == frame_index for f in self.priority_frames)

    def _is_duplicate_in_final(self, frame_index: int) -> bool:
        """检查帧索引是否在最终列表中"""
        return any(f.frame_index == frame_index for f in self.final_frames)

    def _detect_anomaly_opencv(self, frame: np.ndarray) -> float:
            """
            OpenCV 异常检测 (增强鲁棒性版)
            """
            if frame is None or frame.size == 0:
                return 0.0

            h, w = frame.shape[:2]
            total_pixels = h * w
            if total_pixels == 0:
                return 0.0

            try:
                # 转换色彩空间
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                
                anomaly_score = 0.0

                # 1. 黑色沉积物
                mask_black = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 60])) # 稍微放宽亮度
                black_ratio = np.count_nonzero(mask_black) / total_pixels
                if black_ratio > 0.05: # 降低阈值敏感度
                    anomaly_score += min(black_ratio * 3.0, 0.4)

                # 2. 黄色牙菌斑 (调整黄色范围)
                mask_yellow = cv2.inRange(hsv, np.array([20, 40, 40]), np.array([35, 255, 255]))
                yellow_ratio = np.count_nonzero(mask_yellow) / total_pixels
                if yellow_ratio > 0.03:
                    anomaly_score += min(yellow_ratio * 3.0, 0.4)

                # 3. 牙龈红肿 (合并两个红色区间)
                mask_red1 = cv2.inRange(hsv, np.array([0, 100, 50]), np.array([10, 255, 255]))
                mask_red2 = cv2.inRange(hsv, np.array([160, 100, 50]), np.array([180, 255, 255]))
                red_ratio = (np.count_nonzero(mask_red1) + np.count_nonzero(mask_red2)) / total_pixels
                if red_ratio > 0.10:
                    anomaly_score += min(red_ratio * 2.0, 0.4)

                return min(anomaly_score, 1.0)
                
            except Exception as e:
                print(f"[CV Error] Frame analysis failed: {e}")
                return 0.0