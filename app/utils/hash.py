# -*- coding: utf-8 -*-
"""
文件 Hash 计算工具
用于视频文件去重和完整性校验
"""
import hashlib
from pathlib import Path
from typing import BinaryIO


def calculate_file_hash(file_path: str, algorithm: str = "sha256", chunk_size: int = 8192) -> str:
    """
    计算文件的 Hash 值

    Args:
        file_path: 文件路径
        algorithm: 哈希算法 (默认 sha256)
        chunk_size: 分块读取大小 (默认 8KB)

    Returns:
        十六进制 Hash 字符串

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 不支持的哈希算法
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    # 创建哈希对象
    try:
        hasher = hashlib.new(algorithm)
    except ValueError:
        raise ValueError(f"不支持的哈希算法: {algorithm}")

    # 分块读取文件计算 Hash
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)

    return hasher.hexdigest()


def calculate_stream_hash(stream: BinaryIO, algorithm: str = "sha256", chunk_size: int = 8192) -> str:
    """
    计算数据流的 Hash 值

    Args:
        stream: 二进制数据流
        algorithm: 哈希算法 (默认 sha256)
        chunk_size: 分块读取大小 (默认 8KB)

    Returns:
        十六进制 Hash 字符串
    """
    try:
        hasher = hashlib.new(algorithm)
    except ValueError:
        raise ValueError(f"不支持的哈希算法: {algorithm}")

    # 重置流位置到开始
    stream.seek(0)

    # 分块读取流计算 Hash
    while chunk := stream.read(chunk_size):
        hasher.update(chunk)

    # 重置流位置（方便后续使用）
    stream.seek(0)

    return hasher.hexdigest()


def verify_file_integrity(file_path: str, expected_hash: str, algorithm: str = "sha256") -> bool:
    """
    验证文件完整性

    Args:
        file_path: 文件路径
        expected_hash: 期望的 Hash 值
        algorithm: 哈希算法 (默认 sha256)

    Returns:
        True 如果文件完整，False 如果损坏
    """
    try:
        actual_hash = calculate_file_hash(file_path, algorithm)
        return actual_hash.lower() == expected_hash.lower()
    except FileNotFoundError:
        return False
