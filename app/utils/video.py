# -*- coding: utf-8 -*-
"""
视频处理工具
基于 OpenCV 的视频读取和帧处理功能
"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Generator
from PIL import Image


class VideoProcessor:
    """视频处理器"""

    def __init__(self, video_path: str):
        """
        初始化视频处理器

        Args:
            video_path: 视频文件路径
        """
        self.video_path = Path(video_path)
        if not self.video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        self.cap = cv2.VideoCapture(str(video_path))
        if not self.cap.isOpened():
            raise ValueError(f"无法打开视频文件: {video_path}")

        # 读取视频属性
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration = self.frame_count / self.fps if self.fps > 0 else 0
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """释放视频资源"""
        if self.cap.isOpened():
            self.cap.release()

    def get_frame_at_index(self, frame_index: int) -> Optional[np.ndarray]:
        """
        获取指定索引的帧

        Args:
            frame_index: 帧索引（从 0 开始）

        Returns:
            帧图像（BGR 格式）或 None
        """
        if frame_index < 0 or frame_index >= self.frame_count:
            return None

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ret, frame = self.cap.read()

        if not ret:
            return None

        return frame

    def get_frame_at_timestamp(self, timestamp_seconds: float) -> Optional[np.ndarray]:
        """
        获取指定时间戳的帧

        Args:
            timestamp_seconds: 时间戳（秒）

        Returns:
            帧图像（BGR 格式）或 None
        """
        frame_index = int(timestamp_seconds * self.fps)
        return self.get_frame_at_index(frame_index)

    def extract_uniform_frames(self, num_frames: int) -> List[Tuple[int, float, np.ndarray]]:
        """
        均匀抽取视频帧

        Args:
            num_frames: 需要抽取的帧数量

        Returns:
            List[(frame_index, timestamp_seconds, frame_image)]
        """
        if num_frames <= 0 or num_frames > self.frame_count:
            num_frames = min(num_frames, self.frame_count)

        # 计算均匀索引
        indices = np.linspace(0, self.frame_count - 1, num_frames, dtype=int)

        frames = []
        for idx in indices:
            frame = self.get_frame_at_index(idx)
            if frame is not None:
                timestamp = idx / self.fps
                frames.append((idx, timestamp, frame))

        return frames

    def iterate_frames(self, step: int = 1) -> Generator[Tuple[int, float, np.ndarray], None, None]:
        """
        迭代视频的所有帧

        Args:
            step: 步长（1=每帧，2=隔一帧，...）

        Yields:
            (frame_index, timestamp_seconds, frame_image)
        """
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # 重置到开始位置

        frame_index = 0
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break

            if frame_index % step == 0:
                timestamp = frame_index / self.fps
                yield (frame_index, timestamp, frame)

            frame_index += 1

    def format_timestamp(self, seconds: float) -> str:
        """
        格式化时间戳为 MM:SS 格式

        Args:
            seconds: 秒数

        Returns:
            格式化的时间字符串（如 "01:23"）
        """
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    @staticmethod
    def save_frame(frame: np.ndarray, output_path: str, quality: int = 85) -> bool:
        """
        保存帧为 JPEG 图片

        Args:
            frame: 帧图像（BGR 格式）
            output_path: 输出路径
            quality: JPEG 质量（0-100）

        Returns:
            是否成功
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 使用 OpenCV 保存
            cv2.imwrite(
                str(output_path),
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, quality]
            )
            return True
        except Exception as e:
            print(f"保存帧失败: {e}")
            return False

    @staticmethod
    def create_thumbnail(frame: np.ndarray, thumbnail_path: str, size: Tuple[int, int] = (320, 240)) -> bool:
        """
        创建缩略图

        Args:
            frame: 帧图像（BGR 格式）
            thumbnail_path: 缩略图输出路径
            size: 缩略图尺寸（width, height）

        Returns:
            是否成功
        """
        try:
            thumbnail_path = Path(thumbnail_path)
            thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

            # 转换为 RGB（PIL 格式）
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)

            # 等比例缩放
            img.thumbnail(size, Image.Resampling.LANCZOS)

            # 保存
            img.save(str(thumbnail_path), "JPEG", quality=75)
            return True
        except Exception as e:
            print(f"创建缩略图失败: {e}")
            return False


def validate_video(video_path: str, max_duration: int = 30, max_size_mb: int = 100) -> Tuple[bool, str]:
    """
    验证视频文件的有效性和尺寸

    Args:
        video_path: 视频文件路径
        max_duration: 最大时长（秒）
        max_size_mb: 最大文件大小（MB）

    Returns:
        (是否有效, 错误信息)
    """
    video_path = Path(video_path)

    # 检查文件是否存在
    if not video_path.exists():
        return False, "文件不存在"

    # 检查文件大小
    file_size_mb = video_path.stat().st_size / (1024 * 1024)
    if file_size_mb > max_size_mb:
        return False, f"文件过大（{file_size_mb:.1f}MB > {max_size_mb}MB）"

    # 检查视频属性
    try:
        with VideoProcessor(str(video_path)) as vp:
            if vp.duration > max_duration:
                return False, f"视频过长（{vp.duration:.1f}s > {max_duration}s）"

            if vp.frame_count == 0:
                return False, "视频无有效帧"

            return True, "验证通过"

    except Exception as e:
        return False, f"视频读取失败: {str(e)}"


def detect_frame_quality(frame: np.ndarray) -> float:
    """
    检测帧的质量（基于清晰度检测）

    Args:
        frame: 帧图像（BGR 格式）

    Returns:
        质量分数（0-1，越高越清晰）
    """
    # 转换为灰度图
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # 使用 Laplacian 算子计算清晰度
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    # 归一化到 0-1（经验值：< 100 为模糊，> 500 为清晰）
    quality = min(laplacian_var / 500.0, 1.0)

    return quality


def calculate_frame_difference(frame1: np.ndarray, frame2: np.ndarray) -> float:
    """
    计算两帧之间的差异度

    Args:
        frame1: 第一帧（BGR 格式）
        frame2: 第二帧（BGR 格式）

    Returns:
        差异度（0-1，越高越不同）
    """
    # 转换为灰度图
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)

    # 计算绝对差异
    diff = cv2.absdiff(gray1, gray2)

    # 归一化
    difference = np.mean(diff) / 255.0

    return difference
