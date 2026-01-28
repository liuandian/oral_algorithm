# -*- coding: utf-8 -*-
"""
关键帧语义分析器 - 口腔图像中间表示生成
基于传统计算机视觉特征提取，生成每帧的最小中间表示

分析维度：
1. 侧别 (Side): upper / lower / left / right / unknown
2. 牙齿类型 (Tooth Type): anterior / posterior / unknown
3. 区域 (Region): occlusal / interproximal / gum / lingual / buccal / unknown
4. 异常类型 (Detected Issues): dark_deposit / yellow_plaque / structural_defect / gum_issue / unknown

技术方案：
- HSV 色彩空间分析 (牙龈、牙齿、异常物识别)
- 形态学特征提取 (牙齿轮廓、排列方式)
- 空间位置分析 (基于图像区域判断视角)
- 纹理分析 (咬合面、牙缝、牙龈纹理)
"""
import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from app.models.evidence_pack import (
    ToothSide, ToothType, Region, DetectedIssue, FrameMetaTags
)


@dataclass
class AnalysisResult:
    """分析结果数据类"""
    side: ToothSide
    tooth_type: ToothType
    region: Region
    detected_issues: List[DetectedIssue]
    confidence_score: float
    debug_info: Dict = None


class KeyframeAnalyzer:
    """
    关键帧语义分析器

    使用传统 CV 方法进行口腔图像分析，生成结构化中间表示
    """

    # ========================================
    # HSV 色彩阈值常量
    # ========================================

    # 牙齿白色区域 (高亮度，低饱和度)
    TOOTH_WHITE_LOWER = np.array([0, 0, 180])
    TOOTH_WHITE_UPPER = np.array([180, 40, 255])

    # 牙龈粉红色区域
    GUM_PINK_LOWER = np.array([0, 30, 80])
    GUM_PINK_UPPER = np.array([20, 180, 255])
    GUM_PINK_LOWER2 = np.array([160, 30, 80])
    GUM_PINK_UPPER2 = np.array([180, 180, 255])

    # 黑色/深色沉积物 (低亮度)
    DARK_DEPOSIT_LOWER = np.array([0, 0, 0])
    DARK_DEPOSIT_UPPER = np.array([180, 255, 60])

    # 黄色牙菌斑/牙石
    YELLOW_PLAQUE_LOWER = np.array([15, 40, 80])
    YELLOW_PLAQUE_UPPER = np.array([35, 255, 255])

    # 牙龈红肿 (高饱和度红色)
    GUM_RED_LOWER1 = np.array([0, 120, 50])
    GUM_RED_UPPER1 = np.array([10, 255, 255])
    GUM_RED_LOWER2 = np.array([160, 120, 50])
    GUM_RED_UPPER2 = np.array([180, 255, 255])

    # 口腔深色背景 (咽喉/舌根)
    ORAL_CAVITY_LOWER = np.array([0, 0, 0])
    ORAL_CAVITY_UPPER = np.array([180, 255, 40])

    # ========================================
    # 阈值常量
    # ========================================

    # 异常检测阈值
    DARK_DEPOSIT_RATIO_THRESHOLD = 0.02      # 深色沉积占比阈值
    YELLOW_PLAQUE_RATIO_THRESHOLD = 0.015    # 黄色牙菌斑占比阈值
    GUM_REDNESS_RATIO_THRESHOLD = 0.08       # 牙龈红肿占比阈值
    STRUCTURAL_DEFECT_THRESHOLD = 0.01       # 结构缺损阈值

    # 区域判断阈值
    GUM_VISIBILITY_THRESHOLD = 0.15          # 牙龈可见性阈值
    TOOTH_AREA_THRESHOLD = 0.10              # 牙齿区域阈值

    def __init__(self, debug: bool = False):
        """
        初始化分析器

        Args:
            debug: 是否输出调试信息
        """
        self.debug = debug

    def analyze_frame(self, frame: np.ndarray) -> AnalysisResult:
        """
        分析单帧图像，生成完整的中间表示

        Args:
            frame: BGR 格式的图像数组

        Returns:
            AnalysisResult 包含所有分析维度的结果
        """
        if frame is None or frame.size == 0:
            return self._create_unknown_result("Empty frame")

        # 预处理
        frame_rgb, frame_hsv, frame_gray = self._preprocess(frame)
        if frame_hsv is None:
            return self._create_unknown_result("Preprocessing failed")

        # 提取各类 mask
        masks = self._extract_color_masks(frame_hsv)

        # 计算各区域占比
        ratios = self._calculate_region_ratios(masks, frame.shape[:2])

        # 判断是否为有效口腔图像
        if not self._is_valid_oral_image(ratios):
            return self._create_unknown_result("Not a valid oral image", ratios)

        # 分析各维度
        side, side_conf = self._analyze_side(frame, masks, ratios)
        tooth_type, type_conf = self._analyze_tooth_type(frame, masks, ratios)
        region, region_conf = self._analyze_region(frame, masks, ratios)
        detected_issues = self._detect_issues(frame, masks, ratios)

        # 计算综合置信度
        confidence = self._calculate_overall_confidence(
            side_conf, type_conf, region_conf, ratios
        )

        debug_info = None
        if self.debug:
            debug_info = {
                "ratios": ratios,
                "side_conf": side_conf,
                "type_conf": type_conf,
                "region_conf": region_conf
            }

        return AnalysisResult(
            side=side,
            tooth_type=tooth_type,
            region=region,
            detected_issues=detected_issues,
            confidence_score=confidence,
            debug_info=debug_info
        )

    def analyze_frame_to_meta_tags(self, frame: np.ndarray) -> FrameMetaTags:
        """
        分析帧并直接返回 FrameMetaTags 对象

        Args:
            frame: BGR 格式的图像数组

        Returns:
            FrameMetaTags Pydantic 模型
        """
        result = self.analyze_frame(frame)
        return FrameMetaTags(
            side=result.side,
            tooth_type=result.tooth_type,
            region=result.region,
            detected_issues=result.detected_issues,
            confidence_score=result.confidence_score,
            is_verified=False
        )

    # ========================================
    # 预处理方法
    # ========================================

    def _preprocess(self, frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        图像预处理

        Returns:
            (RGB图像, HSV图像, 灰度图像)
        """
        try:
            # 确保是 BGR 格式
            if len(frame.shape) == 2:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

            # 转换色彩空间
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            return frame_rgb, frame_hsv, frame_gray
        except Exception as e:
            if self.debug:
                print(f"[KeyframeAnalyzer] Preprocess error: {e}")
            return None, None, None

    # ========================================
    # 颜色掩码提取
    # ========================================

    def _extract_color_masks(self, hsv: np.ndarray) -> Dict[str, np.ndarray]:
        """
        提取各类颜色区域的二值掩码

        Args:
            hsv: HSV 色彩空间图像

        Returns:
            包含各类掩码的字典
        """
        masks = {}

        # 牙齿白色区域
        masks["tooth_white"] = cv2.inRange(hsv, self.TOOTH_WHITE_LOWER, self.TOOTH_WHITE_UPPER)

        # 牙龈粉红色区域 (两个范围合并)
        gum_mask1 = cv2.inRange(hsv, self.GUM_PINK_LOWER, self.GUM_PINK_UPPER)
        gum_mask2 = cv2.inRange(hsv, self.GUM_PINK_LOWER2, self.GUM_PINK_UPPER2)
        masks["gum_pink"] = cv2.bitwise_or(gum_mask1, gum_mask2)

        # 深色沉积物
        masks["dark_deposit"] = cv2.inRange(hsv, self.DARK_DEPOSIT_LOWER, self.DARK_DEPOSIT_UPPER)

        # 黄色牙菌斑
        masks["yellow_plaque"] = cv2.inRange(hsv, self.YELLOW_PLAQUE_LOWER, self.YELLOW_PLAQUE_UPPER)

        # 牙龈红肿
        red_mask1 = cv2.inRange(hsv, self.GUM_RED_LOWER1, self.GUM_RED_UPPER1)
        red_mask2 = cv2.inRange(hsv, self.GUM_RED_LOWER2, self.GUM_RED_UPPER2)
        masks["gum_red"] = cv2.bitwise_or(red_mask1, red_mask2)

        # 口腔深色背景
        masks["oral_cavity"] = cv2.inRange(hsv, self.ORAL_CAVITY_LOWER, self.ORAL_CAVITY_UPPER)

        # 形态学操作去噪
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        for key in masks:
            masks[key] = cv2.morphologyEx(masks[key], cv2.MORPH_OPEN, kernel)
            masks[key] = cv2.morphologyEx(masks[key], cv2.MORPH_CLOSE, kernel)

        return masks

    def _calculate_region_ratios(self, masks: Dict[str, np.ndarray],
                                  shape: Tuple[int, int]) -> Dict[str, float]:
        """
        计算各区域占比

        Args:
            masks: 颜色掩码字典
            shape: 图像尺寸 (height, width)

        Returns:
            各区域占比字典
        """
        total_pixels = shape[0] * shape[1]
        if total_pixels == 0:
            return {k: 0.0 for k in masks}

        ratios = {}
        for key, mask in masks.items():
            ratios[key] = np.count_nonzero(mask) / total_pixels

        return ratios

    # ========================================
    # 有效性检查
    # ========================================

    def _is_valid_oral_image(self, ratios: Dict[str, float]) -> bool:
        """
        判断是否为有效的口腔图像

        基于牙齿和牙龈的可见性判断
        """
        tooth_visible = ratios.get("tooth_white", 0) > self.TOOTH_AREA_THRESHOLD
        gum_visible = ratios.get("gum_pink", 0) > 0.05

        # 至少要能看到牙齿或牙龈
        return tooth_visible or gum_visible

    # ========================================
    # 侧别分析 (Side)
    # ========================================

    def _analyze_side(self, frame: np.ndarray, masks: Dict[str, np.ndarray],
                      ratios: Dict[str, float]) -> Tuple[ToothSide, float]:
        """
        分析拍摄侧别：上/下/左/右

        使用策略：
        1. 牙龈位置分析 - 牙龈在图像上方通常是上颌，下方是下颌
        2. 口腔背景位置 - 咽喉深色背景的位置
        3. 牙齿排列方向 - 通过轮廓分析
        """
        h, w = frame.shape[:2]

        # 分析牙龈位置分布
        gum_mask = masks.get("gum_pink", np.zeros((h, w), dtype=np.uint8))
        tooth_mask = masks.get("tooth_white", np.zeros((h, w), dtype=np.uint8))

        # 计算上下半区的牙龈占比
        upper_half_gum = np.count_nonzero(gum_mask[:h//2, :])
        lower_half_gum = np.count_nonzero(gum_mask[h//2:, :])

        # 计算左右半区的牙齿占比
        left_half_tooth = np.count_nonzero(tooth_mask[:, :w//2])
        right_half_tooth = np.count_nonzero(tooth_mask[:, w//2:])

        # 计算上下半区的牙齿占比
        upper_half_tooth = np.count_nonzero(tooth_mask[:h//2, :])
        lower_half_tooth = np.count_nonzero(tooth_mask[h//2:, :])

        # 判断逻辑
        confidence = 0.5
        side = ToothSide.UNKNOWN

        total_gum = upper_half_gum + lower_half_gum
        total_tooth = left_half_tooth + right_half_tooth

        if total_gum > 0:
            gum_upper_ratio = upper_half_gum / total_gum
            gum_lower_ratio = lower_half_gum / total_gum

            # 牙龈在上方 -> 通常是上颌牙齿（从下往上拍）
            if gum_upper_ratio > 0.65:
                side = ToothSide.UPPER
                confidence = min(0.5 + (gum_upper_ratio - 0.5) * 0.8, 0.9)
            # 牙龈在下方 -> 通常是下颌牙齿（从上往下拍）
            elif gum_lower_ratio > 0.65:
                side = ToothSide.LOWER
                confidence = min(0.5 + (gum_lower_ratio - 0.5) * 0.8, 0.9)

        # 如果垂直方向不明显，检查水平方向（可能是侧面拍摄）
        if side == ToothSide.UNKNOWN and total_tooth > 0:
            left_ratio = left_half_tooth / total_tooth
            right_ratio = right_half_tooth / total_tooth

            if left_ratio > 0.7:
                side = ToothSide.LEFT
                confidence = min(0.5 + (left_ratio - 0.5) * 0.6, 0.8)
            elif right_ratio > 0.7:
                side = ToothSide.RIGHT
                confidence = min(0.5 + (right_ratio - 0.5) * 0.6, 0.8)

        return side, confidence

    # ========================================
    # 牙齿类型分析 (Tooth Type)
    # ========================================

    def _analyze_tooth_type(self, frame: np.ndarray, masks: Dict[str, np.ndarray],
                            ratios: Dict[str, float]) -> Tuple[ToothType, float]:
        """
        分析牙齿类型：前牙/后牙

        使用策略：
        1. 牙齿形态特征 - 前牙扁平/后牙有咬合面
        2. 牙齿宽高比 - 前牙较窄长，后牙较宽
        3. 咬合面检测 - 后牙通常可见咬合面纹理
        """
        tooth_mask = masks.get("tooth_white", None)
        if tooth_mask is None or np.count_nonzero(tooth_mask) < 100:
            return ToothType.UNKNOWN, 0.3

        # 找到牙齿轮廓
        contours, _ = cv2.findContours(tooth_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return ToothType.UNKNOWN, 0.3

        # 分析最大的几个轮廓
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

        aspect_ratios = []
        solidity_scores = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 500:  # 忽略小区域
                continue

            # 计算边界矩形
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = w / h if h > 0 else 1.0
            aspect_ratios.append(aspect_ratio)

            # 计算凸包填充率（solidity）
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = area / hull_area if hull_area > 0 else 0
            solidity_scores.append(solidity)

        if not aspect_ratios:
            return ToothType.UNKNOWN, 0.3

        avg_aspect_ratio = np.mean(aspect_ratios)
        avg_solidity = np.mean(solidity_scores)

        confidence = 0.5
        tooth_type = ToothType.UNKNOWN

        # 前牙特征：窄长 (aspect_ratio < 1.0), 高 solidity
        # 后牙特征：宽扁 (aspect_ratio > 1.0), 较低 solidity（因为咬合面有凹凸）

        if avg_aspect_ratio < 0.8 and avg_solidity > 0.85:
            tooth_type = ToothType.ANTERIOR
            confidence = min(0.6 + (0.8 - avg_aspect_ratio) * 0.3, 0.85)
        elif avg_aspect_ratio > 1.2:
            tooth_type = ToothType.POSTERIOR
            confidence = min(0.6 + (avg_aspect_ratio - 1.0) * 0.2, 0.85)
        elif avg_solidity < 0.8:
            # 低 solidity 可能表示有咬合面凹凸
            tooth_type = ToothType.POSTERIOR
            confidence = 0.6

        return tooth_type, confidence

    # ========================================
    # 区域分析 (Region)
    # ========================================

    def _analyze_region(self, frame: np.ndarray, masks: Dict[str, np.ndarray],
                        ratios: Dict[str, float]) -> Tuple[Region, float]:
        """
        分析可见区域：咬合面/牙缝/龈缘/舌侧/颊侧

        使用策略：
        1. 牙龈可见性 - 龈缘区域会有大量牙龈可见
        2. 牙齿间隙 - 牙缝区域有明显的间隙
        3. 咬合面纹理 - 咬合面有特殊的沟裂纹理
        4. 视角判断 - 基于牙齿和牙龈的相对位置
        """
        h, w = frame.shape[:2]

        gum_ratio = ratios.get("gum_pink", 0)
        tooth_ratio = ratios.get("tooth_white", 0)
        dark_ratio = ratios.get("dark_deposit", 0)
        oral_cavity_ratio = ratios.get("oral_cavity", 0)

        confidence = 0.5
        region = Region.UNKNOWN

        # 龈缘判断：牙龈可见性高
        if gum_ratio > self.GUM_VISIBILITY_THRESHOLD:
            region = Region.GUM
            confidence = min(0.5 + gum_ratio * 1.5, 0.85)
            return region, confidence

        # 咬合面判断：牙齿区域大，且有纹理特征
        if tooth_ratio > 0.25:
            # 使用灰度图分析纹理
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            tooth_mask = masks.get("tooth_white")

            # 在牙齿区域计算纹理复杂度
            if tooth_mask is not None:
                # 使用 Laplacian 检测纹理
                laplacian = cv2.Laplacian(gray, cv2.CV_64F)
                tooth_laplacian = laplacian * (tooth_mask / 255.0)
                texture_var = np.var(tooth_laplacian[tooth_mask > 0]) if np.any(tooth_mask > 0) else 0

                # 高纹理方差可能是咬合面
                if texture_var > 500:
                    region = Region.OCCLUSAL
                    confidence = min(0.5 + texture_var / 5000, 0.8)
                    return region, confidence

        # 牙缝判断：检测牙齿之间的间隙
        tooth_mask = masks.get("tooth_white")
        if tooth_mask is not None:
            # 垂直投影分析
            vertical_proj = np.sum(tooth_mask, axis=0) / 255

            # 检测投影中的"谷"（间隙）
            valleys = self._detect_valleys(vertical_proj)

            if len(valleys) >= 2:  # 至少有2个牙缝
                region = Region.INTERPROXIMAL
                confidence = min(0.5 + len(valleys) * 0.1, 0.8)
                return region, confidence

        # 舌侧/颊侧判断：基于口腔深色背景的位置
        cavity_mask = masks.get("oral_cavity")
        if cavity_mask is not None and oral_cavity_ratio > 0.1:
            # 分析深色背景在图像中的位置
            # 如果深色背景在中心，可能是从舌侧或颊侧拍摄
            center_cavity = np.count_nonzero(cavity_mask[h//3:2*h//3, w//3:2*w//3])
            total_cavity = np.count_nonzero(cavity_mask)

            if total_cavity > 0:
                center_ratio = center_cavity / total_cavity
                if center_ratio > 0.5:
                    # 需要更多信息来区分舌侧和颊侧
                    # 暂时基于牙龈位置判断
                    gum_mask = masks.get("gum_pink")
                    if gum_mask is not None:
                        upper_gum = np.count_nonzero(gum_mask[:h//2, :])
                        lower_gum = np.count_nonzero(gum_mask[h//2:, :])

                        if upper_gum > lower_gum * 1.5:
                            region = Region.LINGUAL  # 可能是舌侧
                        else:
                            region = Region.BUCCAL   # 可能是颊侧
                        confidence = 0.55
                        return region, confidence

        return region, confidence

    def _detect_valleys(self, projection: np.ndarray, threshold: float = 0.3) -> List[int]:
        """
        检测投影中的谷点（牙齿间隙）

        Args:
            projection: 投影数组
            threshold: 谷点阈值（相对于最大值）

        Returns:
            谷点索引列表
        """
        if len(projection) < 10:
            return []

        # 平滑处理
        kernel_size = max(5, len(projection) // 50)
        if kernel_size % 2 == 0:
            kernel_size += 1
        smoothed = np.convolve(projection, np.ones(kernel_size)/kernel_size, mode='same')

        max_val = np.max(smoothed)
        if max_val == 0:
            return []

        valleys = []
        threshold_val = max_val * threshold

        # 简单的谷点检测
        for i in range(1, len(smoothed) - 1):
            if smoothed[i] < threshold_val:
                if smoothed[i] < smoothed[i-1] and smoothed[i] < smoothed[i+1]:
                    valleys.append(i)

        return valleys

    # ========================================
    # 异常检测 (Detected Issues)
    # ========================================

    def _detect_issues(self, frame: np.ndarray, masks: Dict[str, np.ndarray],
                       ratios: Dict[str, float]) -> List[DetectedIssue]:
        """
        检测口腔异常类型（多选）

        检测项目：
        1. 深色沉积 (dark_deposit)
        2. 黄色牙菌斑/牙石 (yellow_plaque)
        3. 结构缺损 (structural_defect)
        4. 牙龈异常 (gum_issue)
        """
        issues = []

        # 1. 深色沉积检测
        dark_ratio = ratios.get("dark_deposit", 0)
        tooth_ratio = ratios.get("tooth_white", 0)

        # 排除口腔背景后的深色区域
        if tooth_ratio > 0.1:  # 确保有牙齿可见
            # 计算牙齿区域内的深色占比
            tooth_mask = masks.get("tooth_white")
            dark_mask = masks.get("dark_deposit")

            if tooth_mask is not None and dark_mask is not None:
                # 在牙齿区域附近检测深色
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
                tooth_region = cv2.dilate(tooth_mask, kernel)
                dark_in_tooth = cv2.bitwise_and(dark_mask, tooth_region)
                dark_tooth_ratio = np.count_nonzero(dark_in_tooth) / max(np.count_nonzero(tooth_region), 1)

                if dark_tooth_ratio > self.DARK_DEPOSIT_RATIO_THRESHOLD:
                    issues.append(DetectedIssue.DARK_DEPOSIT)

        # 2. 黄色牙菌斑检测
        yellow_ratio = ratios.get("yellow_plaque", 0)
        if yellow_ratio > self.YELLOW_PLAQUE_RATIO_THRESHOLD:
            issues.append(DetectedIssue.YELLOW_PLAQUE)

        # 3. 牙龈异常检测（红肿）
        gum_red_ratio = ratios.get("gum_red", 0)
        gum_pink_ratio = ratios.get("gum_pink", 0)

        if gum_pink_ratio > 0.05:  # 确保牙龈可见
            # 计算红色占牙龈的比例
            gum_redness = gum_red_ratio / (gum_pink_ratio + gum_red_ratio + 1e-6)
            if gum_redness > 0.3 or gum_red_ratio > self.GUM_REDNESS_RATIO_THRESHOLD:
                issues.append(DetectedIssue.GUM_ISSUE)

        # 4. 结构缺损检测（通过边缘不规则性）
        structural_issue = self._detect_structural_defect(frame, masks)
        if structural_issue:
            issues.append(DetectedIssue.STRUCTURAL_DEFECT)

        # 如果没有检测到任何问题
        if not issues:
            issues.append(DetectedIssue.NONE)

        return issues

    def _detect_structural_defect(self, frame: np.ndarray,
                                   masks: Dict[str, np.ndarray]) -> bool:
        """
        检测结构缺损（龋齿、缺损等）

        通过分析牙齿轮廓的不规则性来判断
        """
        tooth_mask = masks.get("tooth_white")
        if tooth_mask is None:
            return False

        # 找轮廓
        contours, _ = cv2.findContours(tooth_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return False

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 1000:
                continue

            # 计算轮廓的凸包
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)

            if hull_area == 0:
                continue

            # 凸度缺陷
            solidity = area / hull_area

            # 低 solidity 可能表示有缺损
            if solidity < 0.75:
                # 进一步检查缺陷的位置和大小
                hull_indices = cv2.convexHull(cnt, returnPoints=False)
                try:
                    defects = cv2.convexityDefects(cnt, hull_indices)
                    if defects is not None:
                        significant_defects = 0
                        for i in range(defects.shape[0]):
                            _, _, _, d = defects[i, 0]
                            # d 是缺陷深度（以 1/256 像素为单位）
                            if d > 5000:  # 较大的缺陷
                                significant_defects += 1

                        if significant_defects >= 2:
                            return True
                except:
                    pass

        return False

    # ========================================
    # 辅助方法
    # ========================================

    def _calculate_overall_confidence(self, side_conf: float, type_conf: float,
                                       region_conf: float, ratios: Dict[str, float]) -> float:
        """
        计算综合置信度
        """
        # 基础置信度：各维度置信度的加权平均
        base_conf = (side_conf * 0.3 + type_conf * 0.3 + region_conf * 0.4)

        # 根据图像质量调整
        tooth_ratio = ratios.get("tooth_white", 0)

        # 牙齿可见性越高，置信度越高
        quality_factor = min(tooth_ratio / 0.3, 1.0)

        final_conf = base_conf * (0.7 + 0.3 * quality_factor)

        return min(max(final_conf, 0.0), 1.0)

    def _create_unknown_result(self, reason: str,
                                debug_info: Dict = None) -> AnalysisResult:
        """
        创建未知结果
        """
        if self.debug:
            print(f"[KeyframeAnalyzer] Unknown result: {reason}")

        return AnalysisResult(
            side=ToothSide.UNKNOWN,
            tooth_type=ToothType.UNKNOWN,
            region=Region.UNKNOWN,
            detected_issues=[DetectedIssue.UNKNOWN],
            confidence_score=0.0,
            debug_info={"reason": reason, **(debug_info or {})}
        )


# ========================================
# 便捷函数
# ========================================

def analyze_keyframe(frame: np.ndarray, debug: bool = False) -> FrameMetaTags:
    """
    便捷函数：分析单帧并返回 FrameMetaTags

    Args:
        frame: BGR 格式的图像数组
        debug: 是否输出调试信息

    Returns:
        FrameMetaTags 对象
    """
    analyzer = KeyframeAnalyzer(debug=debug)
    return analyzer.analyze_frame_to_meta_tags(frame)
