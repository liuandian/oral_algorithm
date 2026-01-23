-- ========================================
-- 智能口腔健康监测系统 - 数据库架构 V1
-- 数据流隔离设计：A 流（业务层）/ B 流（原始层）/ C 流（训练层）
-- ========================================

-- 启用 UUID 扩展
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ========================================
-- B 数据流：原始资产库（只读层）
-- ========================================
CREATE TABLE IF NOT EXISTS b_raw_videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    file_hash VARCHAR(64) UNIQUE NOT NULL,  -- SHA256，防重复上传
    file_path TEXT NOT NULL,                -- 文件系统绝对路径
    file_size_bytes BIGINT NOT NULL,
    duration_seconds FLOAT,
    uploaded_at TIMESTAMP DEFAULT NOW(),

    -- 原始元数据（Write-Once）
    device_info JSONB DEFAULT '{}',
    user_text_description TEXT,
    session_type VARCHAR(20) NOT NULL CHECK (session_type IN ('quick_check', 'baseline')),
    zone_id INT CHECK (zone_id BETWEEN 1 AND 7),  -- baseline 专用，1-7分区

    -- 物理隔离保护
    is_locked BOOLEAN DEFAULT TRUE NOT NULL  -- 强制锁定，防止误修改
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_b_user_uploaded ON b_raw_videos(user_id, uploaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_b_hash ON b_raw_videos(file_hash);
CREATE INDEX IF NOT EXISTS idx_b_session_type ON b_raw_videos(session_type);

-- 触发器：防止 UPDATE 操作（Write-Once 约束）
CREATE OR REPLACE FUNCTION prevent_b_stream_update()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'B 数据流禁止修改操作 (Write-Once)';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 安全地创建触发器（避免重复报错）
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trigger_b_raw_videos_readonly') THEN
        CREATE TRIGGER trigger_b_raw_videos_readonly
            BEFORE UPDATE ON b_raw_videos
            FOR EACH ROW
            EXECUTE FUNCTION prevent_b_stream_update();
    END IF;
END $$;


-- ========================================
-- A 数据流：业务应用层
-- ========================================

-- A1: Session 记录
CREATE TABLE IF NOT EXISTS a_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    b_video_id UUID NOT NULL REFERENCES b_raw_videos(id) ON DELETE RESTRICT,  -- 指向B流
    session_type VARCHAR(20) NOT NULL CHECK (session_type IN ('quick_check', 'baseline')),
    zone_id INT CHECK (zone_id BETWEEN 1 AND 7),  -- baseline专用
    processing_status VARCHAR(20) DEFAULT 'pending' CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_a_sessions_user ON a_sessions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_a_sessions_status ON a_sessions(processing_status);


-- A2: 关键帧表
CREATE TABLE IF NOT EXISTS a_keyframes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES a_sessions(id) ON DELETE CASCADE,
    frame_index INT NOT NULL,
    timestamp_in_video VARCHAR(10) NOT NULL,  -- "00:12.50"
    extraction_strategy VARCHAR(20) NOT NULL CHECK (extraction_strategy IN ('rule_triggered', 'uniform_sampled')),

    -- 图像存储（A流的缓存副本）
    image_path TEXT NOT NULL,
    image_thumbnail_path TEXT,

    -- 结构化元数据
    meta_tags JSONB NOT NULL DEFAULT '{}',  -- {side, tooth_type, region, detected_issues}

    -- 检测得分（供排序）
    anomaly_score FLOAT DEFAULT 0.0 CHECK (anomaly_score >= 0 AND anomaly_score <= 1),

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(session_id, frame_index)
);

CREATE INDEX IF NOT EXISTS idx_a_keyframes_session ON a_keyframes(session_id, anomaly_score DESC);
CREATE INDEX IF NOT EXISTS idx_a_keyframes_strategy ON a_keyframes(extraction_strategy);


-- A3: 证据包（EvidencePack）
CREATE TABLE IF NOT EXISTS a_evidence_packs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES a_sessions(id) ON DELETE CASCADE UNIQUE,
    pack_json JSONB NOT NULL,  -- 完整的EvidencePack JSON
    total_frames INT NOT NULL CHECK (total_frames > 0 AND total_frames <= 25),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_a_evidence_session ON a_evidence_packs(session_id);


-- A4: 用户档案
CREATE TABLE IF NOT EXISTS a_user_profiles (
    user_id VARCHAR(64) PRIMARY KEY,
    baseline_completed BOOLEAN DEFAULT FALSE,
    baseline_completion_date TIMESTAMP,

    -- 基线映射（7个分区的session_id）
    baseline_zone_map JSONB DEFAULT '{}',  -- {"zone_1": "session_id", "zone_2": "session_id", ...}

    -- 统计信息
    total_quick_checks INT DEFAULT 0,
    last_check_date TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_a_profiles_baseline ON a_user_profiles(baseline_completed);


-- A5: LLM 报告
CREATE TABLE IF NOT EXISTS a_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES a_sessions(id) ON DELETE CASCADE,
    evidence_pack_id UUID NOT NULL REFERENCES a_evidence_packs(id) ON DELETE CASCADE,

    report_text TEXT NOT NULL,  -- 千问生成的健康报告
    llm_model VARCHAR(50),
    tokens_used INT,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_a_reports_session ON a_reports(session_id);


-- ========================================
-- C 数据流：训练沙盒（V1预留）
-- ========================================
CREATE TABLE IF NOT EXISTS c_training_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    b_video_id UUID NOT NULL REFERENCES b_raw_videos(id) ON DELETE RESTRICT,
    snapshot_path TEXT NOT NULL,
    purpose VARCHAR(50) CHECK (purpose IN ('annotation', 'augmentation', 'training')),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 预留注释表
CREATE TABLE IF NOT EXISTS c_annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID NOT NULL REFERENCES c_training_snapshots(id) ON DELETE CASCADE,
    annotation_data JSONB DEFAULT '{}',
    annotator_id VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW()
);


-- ========================================
-- 数据完整性检查函数 (修正版)
-- ========================================

-- 检查基线完成状态
CREATE OR REPLACE FUNCTION check_baseline_completion()
RETURNS TRIGGER AS $$
BEGIN
    -- 修正逻辑：使用 JSONB 键存在操作符 (?&) 检查是否包含所有分区键
    IF NEW.baseline_zone_map ?& ARRAY['zone_1', 'zone_2', 'zone_3', 'zone_4', 'zone_5', 'zone_6', 'zone_7'] THEN
        NEW.baseline_completed := TRUE;
        NEW.baseline_completion_date := NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trigger_check_baseline') THEN
        CREATE TRIGGER trigger_check_baseline
            BEFORE UPDATE ON a_user_profiles
            FOR EACH ROW
            EXECUTE FUNCTION check_baseline_completion();
    END IF;
END $$;