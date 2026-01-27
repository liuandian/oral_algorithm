# -*- coding: utf-8 -*-
"""
Migration V3: 关键帧 extraction_reason 字段
- 确保 a_keyframes 表有 extraction_reason 字段
"""
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

# 确保能导入 app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings


MIGRATION_SQL = """
-- ========================================
-- 1. 添加 extraction_reason 字段到 a_keyframes 表
-- ========================================
ALTER TABLE a_keyframes
ADD COLUMN IF NOT EXISTS extraction_reason VARCHAR(50);

-- 为现有数据设置默认值（可选）
UPDATE a_keyframes
SET extraction_reason = ''
WHERE extraction_reason IS NULL;
"""


def migrate():
    """执行迁移"""
    print("=" * 60)
    print("Migration V3: 关键帧 extraction_reason 字段")
    print("=" * 60)

    db_url = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    engine = create_engine(db_url)

    try:
        with engine.connect() as conn:
            print("执行迁移SQL...")
            conn.execute(text(MIGRATION_SQL))
            conn.commit()

        print("=" * 60)
        print("迁移完成！")
        print("更新的表:")
        print("  - a_keyframes (添加 extraction_reason 字段)")
        print("=" * 60)

    except Exception as e:
        print(f"迁移失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    migrate()
