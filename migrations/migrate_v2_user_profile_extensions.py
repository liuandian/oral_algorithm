# -*- coding: utf-8 -*-
"""
Migration V2: 用户档案扩展
- 扩展 a_user_profiles 表
- 新增 a_user_events 表
- 新增 a_concern_points 表
- 扩展 a_evidence_packs 表
"""
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

# 确保能导入 app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings


MIGRATION_SQL = """
-- ========================================
-- 1. 扩展 a_user_profiles 表
-- ========================================
ALTER TABLE a_user_profiles
ADD COLUMN IF NOT EXISTS total_baseline_updates INTEGER DEFAULT 0;

ALTER TABLE a_user_profiles
ADD COLUMN IF NOT EXISTS last_baseline_update_date TIMESTAMP;

ALTER TABLE a_user_profiles
ADD COLUMN IF NOT EXISTS timeline_summary JSONB DEFAULT '{}';

ALTER TABLE a_user_profiles
ADD COLUMN IF NOT EXISTS notification_preferences JSONB DEFAULT '{}';


-- ========================================
-- 2. 扩展 a_evidence_packs 表
-- ========================================
ALTER TABLE a_evidence_packs
ADD COLUMN IF NOT EXISTS baseline_reference_json JSONB;

ALTER TABLE a_evidence_packs
ADD COLUMN IF NOT EXISTS comparison_mode VARCHAR(20) DEFAULT 'none';

-- 添加 comparison_mode 约束（如果不存在）
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


-- ========================================
-- 3. 创建 a_user_events 表
-- ========================================
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


-- ========================================
-- 4. 创建 a_concern_points 表
-- ========================================
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


-- ========================================
-- 5. 创建 updated_at 触发器
-- ========================================
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


def migrate():
    """执行迁移"""
    print("=" * 60)
    print("Migration V2: 用户档案扩展")
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
        print("新增/更新的表:")
        print("  - a_user_profiles (扩展)")
        print("  - a_evidence_packs (扩展)")
        print("  - a_user_events (新增)")
        print("  - a_concern_points (新增)")
        print("=" * 60)

    except Exception as e:
        print(f"迁移失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    migrate()
