#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量生成所有项目文件
确保使用正确的UTF-8中文编码
"""

# 由于文件内容太长，让我通过CLI直接重新生成关键文件
# 这个脚本标记了需要重新生成的文件

files_to_regenerate = [
    "app/models/evidence_pack.py",
    "app/models/schemas.py",
    "app/models/database.py",
    "app/core/keyframe_extractor.py",  # 最关键的算法文件
    "app/core/ingestion.py",
    "app/core/evidence_pack.py",
    "app/core/llm_client.py",
    "app/core/profile_manager.py",
    "app/services/qianwen_vision.py",
    "app/services/storage.py",
    "app/utils/video.py",
    "app/utils/hash.py",
]

print("需要重新生成的文件列表：")
for i, f in enumerate(files_to_regenerate, 1):
    print(f"{i}. {f}")
