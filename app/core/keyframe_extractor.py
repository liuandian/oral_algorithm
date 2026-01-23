# -*- coding: utf-8 -*-
# 在原文件基础上，替换 _detect_anomaly_opencv 方法
# ... (保留其他 imports 和类定义)

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