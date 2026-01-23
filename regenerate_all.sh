#!/bin/bash
# 批量重新生成所有有编码问题的Python文件
# 此脚本会备份并删除有问题的文件

echo "=========================================="
echo "批量重新生成Python文件"
echo "=========================================="

# 创建备份目录
BACKUP_DIR="backup_broken_files_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# 需要重新生成的文件列表
FILES=(
    "app/models/evidence_pack.py"
    "app/models/schemas.py"
    "app/models/database.py"
    "app/core/evidence_pack.py"
    "app/core/ingestion.py"
    "app/core/keyframe_extractor.py"
    "app/core/llm_client.py"
    "app/core/profile_manager.py"
    "app/services/qianwen_vision.py"
    "app/services/storage.py"
    "app/utils/hash.py"
    "app/utils/video.py"
)

echo "备份文件到: $BACKUP_DIR/"
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        cp "$file" "$BACKUP_DIR/"
        echo "  ✓ 备份: $file"
    fi
done

echo ""
echo "清理有问题的文件..."
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        rm "$file"
        echo "  ✓ 删除: $file"
    fi
done

echo ""
echo "=========================================="
echo "完成！现在可以重新生成文件"
echo "备份位置: $BACKUP_DIR/"
echo "=========================================="
