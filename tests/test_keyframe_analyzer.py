#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
关键帧语义分析器测试脚本

测试 KeyframeAnalyzer 对口腔图像的分析能力
"""
import sys
import os
import cv2
import numpy as np
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.keyframe_analyzer import KeyframeAnalyzer, analyze_keyframe
from app.models.evidence_pack import FrameMetaTags


def test_analyzer_with_real_keyframe(image_path: str):
    """测试：使用真实关键帧图像测试分析器"""
    print("\n" + "=" * 60)
    print(f"测试 2: 真实图像测试")
    print(f"图像路径: {image_path}")
    print("=" * 60)

    if not os.path.exists(image_path):
        print(f"[错误] 图像文件不存在: {image_path}")
        return None

    # 读取图像
    image = cv2.imread(image_path)
    if image is None:
        print(f"[错误] 无法读取图像: {image_path}")
        return None

    print(f"图像尺寸: {image.shape}")

    # 使用便捷函数分析
    meta_tags = analyze_keyframe(image, debug=True)

    print(f"\n分析结果 (FrameMetaTags):")
    print(f"  侧别 (Side): {meta_tags.side.value}")
    print(f"  牙齿类型 (Tooth Type): {meta_tags.tooth_type.value}")
    print(f"  区域 (Region): {meta_tags.region.value}")
    print(f"  检测到的问题: {[i.value for i in meta_tags.detected_issues]}")
    print(f"  置信度: {meta_tags.confidence_score:.2f}")
    print(f"  是否已验证: {meta_tags.is_verified}")

    # 输出 JSON 格式
    print(f"\nJSON 输出:")
    print(meta_tags.model_dump_json(indent=2))

    return meta_tags


def test_batch_analysis(keyframe_dir: str):
    """测试：批量分析目录下的所有关键帧"""
    print("\n" + "=" * 60)
    print(f"测试 3: 批量分析")
    print(f"目录: {keyframe_dir}")
    print("=" * 60)

    keyframe_path = Path(keyframe_dir)
    if not keyframe_path.exists():
        print(f"[错误] 目录不存在: {keyframe_dir}")
        return

    # 查找所有图像文件
    image_files = list(keyframe_path.glob("*.jpg")) + list(keyframe_path.glob("*.png"))

    if not image_files:
        print(f"[警告] 目录中没有找到图像文件")
        return

    print(f"找到 {len(image_files)} 个图像文件\n")

    analyzer = KeyframeAnalyzer(debug=False)
    results = []

    for img_path in image_files[:10]:  # 最多分析10个
        image = cv2.imread(str(img_path))
        if image is None:
            print(f"[跳过] 无法读取: {img_path.name}")
            continue

        result = analyzer.analyze_frame(image)
        results.append({
            "filename": img_path.name,
            "side": result.side.value,
            "tooth_type": result.tooth_type.value,
            "region": result.region.value,
            "issues": [i.value for i in result.detected_issues],
            "confidence": result.confidence_score
        })

        print(f"  {img_path.name}: "
              f"side={result.side.value}, "
              f"type={result.tooth_type.value}, "
              f"region={result.region.value}, "
              f"issues={[i.value for i in result.detected_issues]}, "
              f"conf={result.confidence_score:.2f}")

    # 统计
    print(f"\n统计摘要:")
    print(f"  总计分析: {len(results)} 帧")

    if results:
        # 侧别分布
        side_counts = {}
        for r in results:
            side_counts[r["side"]] = side_counts.get(r["side"], 0) + 1
        print(f"  侧别分布: {side_counts}")

        # 区域分布
        region_counts = {}
        for r in results:
            region_counts[r["region"]] = region_counts.get(r["region"], 0) + 1
        print(f"  区域分布: {region_counts}")

        # 问题统计
        issue_counts = {}
        for r in results:
            for issue in r["issues"]:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
        print(f"  问题统计: {issue_counts}")

        # 平均置信度
        avg_conf = sum(r["confidence"] for r in results) / len(results)
        print(f"  平均置信度: {avg_conf:.2f}")



def main():
    """主测试函数"""
    import argparse

    parser = argparse.ArgumentParser(description="关键帧语义分析器测试")
    parser.add_argument("--image", type=str, help="单个图像文件路径")
    parser.add_argument("--dir", type=str, help="关键帧目录路径")

    args = parser.parse_args()

    print("=" * 60)
    print("关键帧语义分析器测试")
    print("=" * 60)



    # 测试单个真实图像
    if args.image:
        test_analyzer_with_real_keyframe(args.image)

    # 批量测试
    if args.dir:
        test_batch_analysis(args.dir)

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
