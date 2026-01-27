# migrations/init_db.py
import sys
import os
from pathlib import Path
from sqlalchemy import create_engine, text

# 1. 设置路径，确保能导入 app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.models.database import Base
# [关键] 必须导入定义了 Model 的模块，否则 create_all 找不到表！
# 假设你的所有 Model 都在 app.models.database 或 app.models 下
from app.models import database 

# 定义那些 Python 无法生成的复杂逻辑（触发器/扩展）
RAW_SQL_LOGIC = """
-- 1. 启用 UUID 扩展
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. B流写保护触发器
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

-- 3. 用户档案基线检查触发器 (修正了 ?& 语法)
CREATE OR REPLACE FUNCTION check_baseline_completion()
RETURNS TRIGGER AS $$
BEGIN
    -- 使用 ?& 操作符检查是否包含所有分区
    IF NEW.baseline_zone_map ?& ARRAY['zone_1', 'zone_2', 'zone_3', 'zone_4', 'zone_5', 'zone_6', 'zone_7'] THEN
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

def init_db():
    """全自动初始化数据库"""
    print("=" * 60)
    print("正在重置数据库 (Code-First 模式)...")
    
    # 获取数据库 URL
    db_url = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    engine = create_engine(db_url)

    try:
        # 1. 暴力删表 (DROP ALL)
        print("1. 删除旧表...")
        Base.metadata.drop_all(bind=engine)

        # 2. 自动建表 (CREATE ALL)
        print("2. 根据 Python 模型生成新表...")
        # SQLAlchemy 会自动把 class AKeyframe 变成 CREATE TABLE a_keyframes
        Base.metadata.create_all(bind=engine)

        # 3. 注入触发器 (Raw SQL)
        print("3. 应用触发器和扩展...")
        with engine.connect() as conn:
            conn.execute(text(RAW_SQL_LOGIC))
            conn.commit()

        print("=" * 60)
        print("数据库初始化完成！")

    except Exception as e:
        print(f"初始化失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_db()