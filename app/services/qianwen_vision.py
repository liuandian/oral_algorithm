# -*- coding: utf-8 -*-
"""
千问 Vision API 客户端
封装千问多模态 API 调用
"""
import json
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests

from dataclasses import dataclass
from app.models.evidence_pack import EvidencePack, KeyframeData


class QianwenAPIError(Exception):
    """千问 API 异常"""
    pass


@dataclass
class LLMResponse:
    """LLM 响应结果"""
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class QianwenVisionClient:
    """千问 Vision API 客户端"""

    # 限制发送的图像数量（避免请求过大超时）
    MAX_IMAGES_PER_REQUEST = 8

    def __init__(self, api_key: str, model: str = "qwen-vl-max"):
        """
        初始化客户端

        Args:
            api_key: 千问 API Key
            model: 模型名称（默认 qwen-vl-max）
        """
        self.api_key = api_key
        self.model = model
        self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

    def analyze_evidence_pack(self, evidence_pack: EvidencePack, prompt: str,
                               baseline_frames: List[KeyframeData] = None) -> LLMResponse:
        """
        使用千问 Vision API 分析 EvidencePack

        Args:
            evidence_pack: EvidencePack 证据包
            prompt: 分析提示词
            baseline_frames: 基线帧列表（7个区域各一帧）

        Returns:
            LLMResponse 包含报告文本和 token 使用信息

        Raises:
            QianwenAPIError: API 调用失败
        """
        print(f"[千问] 开始分析 EvidencePack: {len(evidence_pack.frames)} 帧")
        if baseline_frames:
            print(f"[千问] 包含 {len(baseline_frames)} 帧基线数据进行对比")

        # 第一步：构建消息内容
        message_content = self._build_message_content(evidence_pack, prompt, baseline_frames)

        # 第二步：构建请求体
        payload = {
            "model": self.model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": message_content
                    }
                ]
            },
            "parameters": {
                "max_tokens": 2000,
                "temperature": 0.7
            }
        }

        # 第三步：调用 API
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            # 增加超时时间：连接超时 30s，读取超时 180s
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=(30, 180)
            )

            response.raise_for_status()

        except requests.exceptions.RequestException as e:
            raise QianwenAPIError(f"千问 API 请求失败: {str(e)}")

        # 第四步：解析响应
        try:
            result = response.json()
            return self._extract_response_with_usage(result)

        except (json.JSONDecodeError, KeyError) as e:
            raise QianwenAPIError(f"千问 API 响应解析失败: {str(e)}")

    def _build_message_content(self, evidence_pack: EvidencePack, prompt: str,
                                baseline_frames: List[KeyframeData] = None) -> List[Dict[str, Any]]:
        """
        构建千问 API 消息内容

        Args:
            evidence_pack: EvidencePack 证据包
            prompt: 提示词
            baseline_frames: 基线帧列表（可选，用于对比分析）

        Returns:
            消息内容列表（包含文本和图像）
        """
        content = []

        # 第一项：文本提示词
        content.append({
            "text": prompt
        })

        # 如果有基线帧，先添加基线帧图像
        if baseline_frames:
            content.append({
                "text": "\n\n===== 基线数据（历史参考）====="
            })
            for idx, frame in enumerate(baseline_frames):
                image_base64 = self._load_image_as_base64(frame.image_url)
                if image_base64:
                    content.append({
                        "image": f"data:image/jpeg;base64,{image_base64}"
                    })

                # 添加基线帧信息
                zone_names = {
                    1: "上左后区", 2: "上前区", 3: "上右后区",
                    4: "下左后区", 5: "下前区", 6: "下右后区",
                    7: "磨牙特殊区"
                }
                zone_id = idx + 1
                zone_name = zone_names.get(zone_id, f"区域{zone_id}")
                content.append({
                    "text": f"\n[基线 {zone_id}] {zone_name} - 时间戳: {frame.timestamp}"
                })

            content.append({
                "text": "\n\n===== 本次检查数据 ====="
            })

        # 选择最有代表性的帧（优先选择异常分数高的帧）
        # 如果有基线帧，需要减少当前帧数量以控制总数
        max_current_frames = self.MAX_IMAGES_PER_REQUEST
        if baseline_frames:
            max_current_frames = max(4, self.MAX_IMAGES_PER_REQUEST - len(baseline_frames))

        frames_to_send = self._select_representative_frames(evidence_pack.frames, max_current_frames)
        print(f"[千问] 选择 {len(frames_to_send)} 帧发送 (共 {len(evidence_pack.frames)} 帧)")

        # 后续项：关键帧图像
        for idx, frame in enumerate(frames_to_send):
            # 从文件路径读取图像并转换为 base64
            image_base64 = self._load_image_as_base64(frame.image_url)

            if image_base64:
                # 添加图像
                content.append({
                    "image": f"data:image/jpeg;base64,{image_base64}"
                })

            # 添加帧元信息文本
            frame_info = (
                f"\n[当前帧 {idx + 1}] "
                f"时间戳: {frame.timestamp}, "
                f"异常分数: {frame.anomaly_score:.3f}, "
                f"策略: {frame.extraction_strategy}"
            )

            if frame.meta_tags:
                frame_info += f", 区域: {frame.meta_tags.region.value}"
                if frame.meta_tags.side.value != "unknown":
                    frame_info += f", 位置: {frame.meta_tags.side.value}"
                if frame.meta_tags.tooth_type.value != "unknown":
                    frame_info += f", 牙型: {frame.meta_tags.tooth_type.value}"

            content.append({
                "text": frame_info
            })

        return content

    def _select_representative_frames(self, frames: List[KeyframeData],
                                       max_count: int = None) -> List[KeyframeData]:
        """
        选择最有代表性的帧发送给 API

        策略：
        1. 优先选择异常分数高的帧（rule_triggered）
        2. 均匀采样补充到最大数量

        Args:
            frames: 所有关键帧列表
            max_count: 最大帧数（默认使用 MAX_IMAGES_PER_REQUEST）

        Returns:
            选中的帧列表
        """
        max_frames = max_count if max_count else self.MAX_IMAGES_PER_REQUEST

        if len(frames) <= max_frames:
            return frames

        # 分离 rule_triggered 和 uniform_sampled 帧
        rule_triggered = [f for f in frames if f.extraction_strategy == "rule_triggered"]
        uniform_sampled = [f for f in frames if f.extraction_strategy == "uniform_sampled"]

        selected = []

        # 优先添加 rule_triggered 帧（按异常分数排序）
        rule_triggered.sort(key=lambda x: x.anomaly_score, reverse=True)
        selected.extend(rule_triggered[:max_frames])

        # 如果还有空间，均匀采样补充
        remaining_slots = max_frames - len(selected)
        if remaining_slots > 0 and uniform_sampled:
            # 均匀采样
            step = max(1, len(uniform_sampled) // remaining_slots)
            for i in range(0, len(uniform_sampled), step):
                if len(selected) >= max_frames:
                    break
                selected.append(uniform_sampled[i])

        # 按原始顺序排序（根据时间戳）
        selected.sort(key=lambda x: x.timestamp)

        return selected

    def _load_image_as_base64(self, image_path: str) -> Optional[str]:
        """
        从文件路径加载图像并转换为 base64

        Args:
            image_path: 图像文件路径

        Returns:
            Base64 编码的图像字符串，失败返回 None
        """
        try:
            path = Path(image_path)
            if not path.exists():
                print(f"[警告] 图像文件不存在: {image_path}")
                return None

            with open(path, "rb") as f:
                image_data = f.read()
                return base64.b64encode(image_data).decode("utf-8")

        except Exception as e:
            print(f"[警告] 读取图像失败 {image_path}: {e}")
            return None

    def _extract_response_text(self, response_data: Dict[str, Any]) -> str:
        """
        从千问 API 响应中提取文本（保留用于向后兼容）

        Args:
            response_data: API 响应 JSON

        Returns:
            生成的文本内容
        """
        result = self._extract_response_with_usage(response_data)
        return result.text

    def _extract_response_with_usage(self, response_data: Dict[str, Any]) -> LLMResponse:
        """
        从千问 API 响应中提取文本和 token 使用信息

        Args:
            response_data: API 响应 JSON

        Returns:
            LLMResponse 包含文本和 token 统计

        Raises:
            QianwenAPIError: 响应格式错误
        """
        try:
            # 千问 API 响应格式：
            # {
            #   "output": {
            #     "choices": [
            #       {
            #         "message": {
            #           "content": [{"text": "..."}]
            #         }
            #       }
            #     ]
            #   },
            #   "usage": {
            #     "input_tokens": 100,
            #     "output_tokens": 50,
            #     "total_tokens": 150
            #   }
            # }
            output = response_data.get("output", {})
            choices = output.get("choices", [])

            if not choices:
                raise QianwenAPIError("API 响应中没有选择项")

            message = choices[0].get("message", {})
            content = message.get("content", [])

            # 提取所有文本内容并合并
            text_parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    text_parts.append(item["text"])
                elif isinstance(item, str):
                    text_parts.append(item)

            if not text_parts:
                raise QianwenAPIError("API 响应中没有文本内容")

            text = "\n".join(text_parts).strip()

            # 提取 token 使用信息
            usage = response_data.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

            print(f"[千问] Token 使用: input={input_tokens}, output={output_tokens}, total={total_tokens}")

            return LLMResponse(
                text=text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens
            )

        except QianwenAPIError:
            raise
        except Exception as e:
            raise QianwenAPIError(f"解析响应失败: {str(e)}")

    def analyze_single_frame(self, image_base64: str, prompt: str) -> str:
        """
        分析单帧图像（用于测试）

        Args:
            image_base64: Base64 编码的图像
            prompt: 分析提示词

        Returns:
            LLM 生成的分析文本
        """
        payload = {
            "model": self.model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"text": prompt},
                            {"image": f"data:image/jpeg;base64,{image_base64}"}
                        ]
                    }
                ]
            },
            "parameters": {
                "max_tokens": 1000,
                "temperature": 0.7
            }
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )

            response.raise_for_status()
            result = response.json()
            return self._extract_response_text(result)

        except Exception as e:
            raise QianwenAPIError(f"单帧分析失败: {str(e)}")
