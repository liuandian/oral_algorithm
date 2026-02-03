#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库管理脚本 - 统一入口

功能：
  - init:  初始化数据库（删除旧表 + 创建新表 + 触发器）
  - reset: 重置数据库（同 init）
  - migrate: 增量迁移（在已有表上添加新字段/表）

用法：
  python migrations/manage_db.py init    # 全新初始化
  python migrations/manage_db.py reset   # 强制重置（删除所有数据）
  python migrations/manage_db.py migrate # 执行增量迁移
"""
import sys
import os
from pathlib import Path
from sqlalchemy import create_engine, text, inspect

# 设置路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.models.database import Base
from app.models import database  # 确保模型被导入


# ========================================
# SQL 定义
# ========================================

# 1. 初始化触发器和扩展
INIT_SQL = """
-- 启用 UUID 扩展
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- B流写保护触发器
CREATE OR REPLACE FUNCTION prevent_b_stream_update()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'B 数据流禁止修改操作 (Write-Once)';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_b_raw_videos_readonly ON b_raw_videos;
CREATE TRIGGER trigger_b_raw_videos_readonly
    BEFORE UPDATE ON b_raw_videos
    FOR EACH ROW
    EXECUTE FUNCTION prevent_b_stream_update();

-- 用户档案基线检查触发器
CREATE OR REPLACE FUNCTION check_baseline_completion()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.baseline_zone_map ?& ARRAY['1', '2', '3', '4', '5', '6', '7'] THEN
        NEW.baseline_completed := TRUE;
        NEW.baseline_completion_date := NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_check_baseline ON a_user_profiles;
CREATE TRIGGER trigger_check_baseline
    BEFORE UPDATE ON a_user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION check_baseline_completion();
"""

# 2. V2 迁移 SQL (用户档案扩展)
V2_MIGRATION_SQL = """
-- 扩展 a_user_profiles 表
ALTER TABLE a_user_profiles
ADD COLUMN IF NOT EXISTS total_baseline_updates INTEGER DEFAULT 0;

ALTER TABLE a_user_profiles
ADD COLUMN IF NOT EXISTS last_baseline_update_date TIMESTAMP;

ALTER TABLE a_user_profiles
ADD COLUMN IF NOT EXISTS timeline_summary JSONB DEFAULT '{}';

ALTER TABLE a_user_profiles
ADD COLUMN IF NOT EXISTS notification_preferences JSONB DEFAULT '{}';

-- 扩展 a_evidence_packs 表
ALTER TABLE a_evidence_packs
ADD COLUMN IF NOT EXISTS baseline_reference_json JSONB;

ALTER TABLE a_evidence_packs
ADD COLUMN IF NOT EXISTS comparison_mode VARCHAR(20) DEFAULT 'none';

-- 添加 comparison_mode 约束
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'check_comparison_mode'
    ) THEN
        ALTER TABLE a_evidence_packs
        ADD CONSTRAINT check_comparison_mode
        CHECK (comparison_mode IN ('none', 'partial', 'full'));
    END IF;
END $$;

-- 创建 a_user_events 表
CREATE TABLE IF NOT EXISTS a_user_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL REFERENCES a_user_profiles(user_id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    event_description TEXT,
    event_date TIMESTAMP NOT NULL,
    related_session_id UUID REFERENCES a_sessions(id) ON DELETE SET NULL,
    event_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_event_type CHECK (
        event_type IN ('dental_cleaning', 'scaling', 'filling', 'extraction', 'crown', 'orthodontic', 'whitening', 'checkup', 'other')
    )
);

CREATE INDEX IF NOT EXISTS idx_user_events_user_id ON a_user_events(user_id);
CREATE INDEX IF NOT EXISTS idx_user_events_event_date ON a_user_events(event_date);

-- 创建 a_concern_points 表
CREATE TABLE IF NOT EXISTS a_concern_points (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL REFERENCES a_user_profiles(user_id) ON DELETE CASCADE,
    source_type VARCHAR(20) NOT NULL,
    zone_id INTEGER,
    location_description VARCHAR(200),
    concern_type VARCHAR(50) NOT NULL,
    concern_description TEXT,
    severity VARCHAR(20) DEFAULT 'mild',
    status VARCHAR(20) DEFAULT 'active',
    first_detected_at TIMESTAMP DEFAULT NOW(),
    last_observed_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    related_sessions JSONB DEFAULT '[]',
    evidence_frame_ids JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT check_concern_source_type CHECK (source_type IN ('user_reported', 'system_detected')),
    CONSTRAINT check_concern_severity CHECK (severity IN ('mild', 'moderate', 'severe')),
    CONSTRAINT check_concern_status CHECK (status IN ('active', 'resolved', 'monitoring')),
    CONSTRAINT check_concern_zone_id CHECK (zone_id IS NULL OR (zone_id BETWEEN 1 AND 7))
);

CREATE INDEX IF NOT EXISTS idx_concern_points_user_id ON a_concern_points(user_id);
CREATE INDEX IF NOT EXISTS idx_concern_points_status ON a_concern_points(status);

-- 创建 updated_at 触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_concern_points_updated_at ON a_concern_points;
CREATE TRIGGER trigger_concern_points_updated_at
    BEFORE UPDATE ON a_concern_points
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""

# 3. V3 迁移 SQL (关键帧 extraction_reason)
V3_MIGRATION_SQL = """
-- 添加 extraction_reason 字段到 a_keyframes 表
ALTER TABLE a_keyframes
ADD COLUMN IF NOT EXISTS extraction_reason VARCHAR(50);

-- 为现有数据设置默认值
UPDATE a_keyframes
SET extraction_reason = ''
WHERE extraction_reason IS NULL;
"""


def get_engine():
    """获取数据库引擎"""
    db_url = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    return create_engine(db_url)


def check_tables_exist(engine):
    """检查是否已有表存在"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    core_tables = ['b_raw_videos', 'a_sessions', 'a_keyframes', 'a_user_profiles']
    return any(t in tables for t in core_tables)


def init_db(force=False):
    """
    初始化数据库

    Args:
        force: 如果为 True，强制删除并重建（reset模式）
    """
    print("=" * 60)
    if force:
        print("数据库重置模式 (强制删除所有数据)")
    else:
        print("数据库初始化")
    print("=" * 60)

    engine = get_engine()

    try:
        # 检查是否已有数据
        has_tables = check_tables_exist(engine)

        if has_tables and not force:
            print("\n[警告] 检测到数据库中已有表存在！")
            print("如果需要重置，请使用: python migrations/manage_db.py reset")
            print("或者执行增量迁移: python migrations/manage_db.py migrate")
            print("\n操作已取消，未做任何更改。")
            return

        if has_tables and force:
            print("1. 删除旧表...")
            Base.metadata.drop_all(bind=engine)
            print("   ✓ 旧表已删除")

        # 创建表
        print("2. 创建数据表...")
        Base.metadata.create_all(bind=engine)
        print("   ✓ 表创建完成")

        # 应用触发器和扩展
        print("3. 应用触发器和扩展...")
        with engine.connect() as conn:
            conn.execute(text(INIT_SQL))
            conn.commit()
        print("   ✓ 触发器创建完成")

        # 应用 V2 迁移（创建额外表和字段）
        print("4. 应用 V2 扩展...")
        with engine.connect() as conn:
            conn.execute(text(V2_MIGRATION_SQL))
            conn.commit()
        print("   ✓ V2 扩展完成")

        # 应用 V3 迁移
        print("5. 应用 V3 扩展...")
        with engine.connect() as conn:
            conn.execute(text(V3_MIGRATION_SQL))
            conn.commit()
        print("   ✓ V3 扩展完成")

        print("\n" + "=" * 60)
        print("数据库初始化完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n[错误] 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def migrate_db():
    """增量迁移 - 在已有表上添加新字段/表"""
    print("=" * 60)
    print("执行增量迁移")
    print("=" * 60)

    engine = get_engine()

    try:
        # 检查是否已有表
        if not check_tables_exist(engine):
            print("\n[错误] 未检测到现有表，请先执行初始化:")
            print("  python migrations/manage_db.py init")
            sys.exit(1)

        print("\n1. 应用 V2 迁移 (用户档案扩展)...")
        with engine.connect() as conn:
            conn.execute(text(V2_MIGRATION_SQL))
            conn.commit()
        print("   ✓ V2 迁移完成")

        print("\n2. 应用 V3 迁移 (关键帧字段)...")
        with engine.connect() as conn:
            conn.execute(text(V3_MIGRATION_SQL))
            conn.commit()
        print("   ✓ V3 迁移完成")

        # 确保触发器存在
        print("\n3. 检查并创建触发器...")
        with engine.connect() as conn:
            conn.execute(text(INIT_SQL))
            conn.commit()
        print("   ✓ 触发器检查完成")

        print("\n" + "=" * 60)
        print("增量迁移完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n[错误] 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def show_status():
    """显示数据库状态"""
    print("=" * 60)
    print("数据库状态检查")
    print("=" * 60)

    engine = get_engine()
    inspector = inspect(engine)

    tables = inspector.get_table_names()
    core_tables = ['b_raw_videos', 'a_sessions', 'a_keyframes',
                   'a_evidence_packs', 'a_user_profiles', 'a_reports']

    print(f"\n数据库: {settings.DB_NAME}")
    print(f"主机: {settings.DB_HOST}:{settings.DB_PORT}")
    print(f"\n核心表状态:")

    for table in core_tables:
        status = "✓ 存在" if table in tables else "✗ 不存在"
        print(f"  - {table}: {status}")

    # 检查扩展表
    extended_tables = ['a_user_events', 'a_concern_points']
    print(f"\n扩展表状态:")
    for table in extended_tables:
        status = "✓ 存在" if table in tables else "✗ 不存在"
        print(f"  - {table}: {status}")

    if all(t in tables for t in core_tables):
        print("\n✓ 数据库结构完整")
    else:
        print("\n⚠ 部分表缺失，建议执行: python migrations/manage_db.py init")

    print("=" * 60)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="数据库管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python migrations/manage_db.py init      # 全新安装（首次使用）
  python migrations/manage_db.py reset     # 强制重置（删除所有数据！）
  python migrations/manage_db.py migrate   # 增量迁移（保留数据）
  python migrations/manage_db.py status    # 查看状态
        """
    )

    parser.add_argument(
        "command",
        choices=["init", "reset", "migrate", "status"],
        help="要执行的命令"
    )

    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="强制模式（init时使用，等同于reset）"
    )

    args = parser.parse_args()

    if args.command == "init":
        init_db(force=args.force)
    elif args.command == "reset":
        confirm = input("⚠️  警告: 这将删除所有数据！确认重置? [y/N]: ")
        if confirm.lower() == 'y':
            init_db(force=True)
        else:
            print("操作已取消")
    elif args.command == "migrate":
        migrate_db()
    elif args.command == "status":
        show_status()


if __name__ == "__main__":
    main()
