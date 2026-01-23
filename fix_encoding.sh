#!/bin/bash
# Fix encoding issues in Python files
# This script removes all files with encoding errors and will regenerate them

echo "=========================================="
echo "Fixing Encoding Issues"
echo "=========================================="

# List of files with encoding errors
FILES_TO_CLEAN=(
    "app/core/evidence_pack.py"
    "app/core/ingestion.py"
    "app/core/keyframe_extractor.py"
    "app/core/llm_client.py"
    "app/core/profile_manager.py"
    "app/models/database.py"
    "app/models/evidence_pack.py"
    "app/models/schemas.py"
    "app/services/qianwen_vision.py"
    "app/services/storage.py"
    "app/utils/hash.py"
    "app/utils/video.py"
)

# Backup directory
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Creating backup in $BACKUP_DIR..."

# Backup and remove files
for file in "${FILES_TO_CLEAN[@]}"; do
    if [ -f "$file" ]; then
        echo "  Backing up: $file"
        cp "$file" "$BACKUP_DIR/"
        rm "$file"
    fi
done

echo ""
echo "✓ Backup complete"
echo "✓ Files removed"
echo ""
echo "Next steps:"
echo "1. The files with encoding errors have been backed up to: $BACKUP_DIR/"
echo "2. You need to regenerate these files with proper UTF-8 encoding"
echo "3. Or restore from the provided clean templates"
echo ""
echo "=========================================="
