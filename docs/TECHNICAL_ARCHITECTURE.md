# 智能口腔健康监测系统 - 技术架构文档

> 版本: V1.0  
> 更新日期: 2026-02-03

---

## 目录

1. [系统概述](#系统概述)
2. [架构设计](#架构设计)
3. [数据流设计](#数据流设计)
4. [核心模块](#核心模块)
5. [数据库设计](#数据库设计)
6. [关键技术实现](#关键技术实现)

---

## 系统概述

智能口腔健康监测系统是一个基于视频分析的口腔健康评估后端服务。系统接收用户上传的口腔视频，通过计算机视觉算法提取关键帧，结合 LLM (大语言模型) 分析生成专业的口腔健康报告。

### 核心功能

| 功能模块 | 描述 |
|---------|------|
| 视频采集与存储 | 接收并安全存储原始口腔视频 |
| 关键帧提取 | 智能提取最具代表性的视频帧 |
| 帧匹配与对比 | 将当前帧与历史基线进行比对 |
| LLM 智能分析 | 基于通义千问 Vision 模型生成专业报告 |
| 用户档案管理 | 追踪用户历史检查记录和关注点 |

### 技术栈

- **后端框架**: FastAPI (Python 3.10+)
- **数据库**: PostgreSQL 15+
- **ORM**: SQLAlchemy 2.0
- **计算机视觉**: OpenCV + 自定义算法
- **LLM 服务**: 阿里云通义千问 (Qwen-VL)
- **数据存储**: 本地文件系统 (A/B/C 三层架构)

---

## 架构设计

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer                                │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐   │
│  │   Upload   │ │   Session  │ │   Report   │ │   Profile  │   │
│  │    API     │ │    API     │ │    API     │ │    API     │   │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘   │
└────────┼──────────────┼──────────────┼──────────────┼──────────┘
         │              │              │              │
         └──────────────┴──────┬───────┴──────────────┘
                               │
                    ┌──────────▼──────────┐
                    │    Core Services    │
                    │  ┌───────────────┐  │
                    │  │  Ingestion    │  │  ← 视频摄入与验证
                    │  └───────────────┘  │
                    │  ┌───────────────┐  │
                    │  │KeyFrame Extract│ │  ← 关键帧提取
                    │  └───────────────┘  │
                    │  ┌───────────────┐  │
                    │  │ Frame Matcher │  │  ← 帧匹配与基线对比
                    │  └───────────────┘  │
                    │  ┌───────────────┐  │
                    │  │ Evidence Pack │  │  ← 证据包构建
                    │  │   Generator   │  │
                    │  └───────────────┘  │
                    │  ┌───────────────┐  │
                    │  │  LLM Client   │  │  ← 报告生成
                    │  └───────────────┘  │
                    └──────────┬──────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
┌────────▼────────┐  ┌─────────▼──────────┐  ┌──────▼──────┐
│  B-Stream       │  │  A-Stream          │  │  C-Stream   │
│  (Raw Videos)   │  │  (Business Data)   │  │  (Training) │
│                 │  │                    │  │             │
│  /data/B/       │  │  /data/A/          │  │  /data/C/   │
│  ├── videos/    │  │  ├── keyframes/    │  │             │
│  └── backups/   │  │  ├── evidence/     │  │  (Reserved) │
│                 │  │  └── reports/      │  │             │
└─────────────────┘  └────────────────────┘  └─────────────┘
                               │
                    ┌──────────▼──────────┐
                    │    PostgreSQL       │
                    │  ┌───────────────┐  │
                    │  │   BVideo      │  │  ← 视频元数据
                    │  │   ASession    │  │  ← Session 状态
                    │  │   AKeyframe   │  │  ← 关键帧信息
                    │  │  AEvidencePack│  │  ← 证据包数据
                    │  │    AReport    │  │  ← 分析报告
                    │  │    AUser      │  │  ← 用户信息
                    │  │  AUserEvent   │  │  ← 用户事件
                    │  │ AConcernPoint │  │  ← 关注点
                    │  └───────────────┘  │
                    └─────────────────────┘
```

---

## 数据流设计

### A/B/C 三层数据流

系统采用**三层数据流架构**，确保数据安全性和可追溯性：

#### B-Stream (Base Layer) - 基础层

```
用途: 原始视频资产库
特性: Write-Once (只读/不可篡改)
路径: ./data/B/
├── videos/          # 原始视频文件
│   └── {video_hash}.mp4
└── backups/         # 备份文件
```

**核心原则**:
- 视频一旦写入，禁止修改或删除
- 通过哈希值唯一标识和校验
- 支持审计和溯源

#### A-Stream (Application Layer) - 应用层

```
用途: 业务数据存储
特性: 可读写，支持更新
路径: ./data/A/
├── keyframes/       # 关键帧图像
│   └── {session_id}/{frame_index}.jpg
├── evidence/        # EvidencePack JSON
│   └── {session_id}.json
└── reports/         # 生成的报告
    └── {report_id}.md
```

**核心数据**:
- 关键帧: 从视频中提取的代表性帧
- EvidencePack: 包含关键帧元数据、分析结果的结构化数据
- 报告: LLM 生成的文本报告

#### C-Stream (Copy Layer) - 训练层

```
用途: 模型训练沙盒
特性: 仅允许从 B-Stream 复制
路径: ./data/C/
状态: V1 版本预留，用于未来模型训练
```

### 数据流转流程

```
用户上传视频
     │
     ▼
┌─────────────────┐
│  1. Ingestion   │  ← 验证、计算哈希、存入 B-Stream
│     Service     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. Session     │  ← 创建 Session，状态=pending
│    Creation     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3. KeyFrame    │  ← 提取关键帧，存入 A/keyframes/
│   Extraction    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  4. Frame       │  ← 匹配基线帧（Quick Check）
│    Matching     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  5. Evidence    │  ← 构建 EvidencePack，存入 A/evidence/
│   Pack Build    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  6. LLM Report  │  ← 调用千问 API 生成报告
│   Generation    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  7. Report      │  ← 保存报告，状态=completed
│     Storage     │
└─────────────────┘
```

---

## 核心模块

### 1. 视频摄入模块 (Ingestion)

**文件**: `app/core/ingestion.py`

**职责**:
- 接收上传的视频文件
- 验证视频格式和大小
- 计算 SHA256 哈希作为唯一标识
- 存储到 B-Stream

**关键算法**:
```python
# 视频哈希计算
hash_obj = hashlib.sha256()
while chunk := file.read(8192):
    hash_obj.update(chunk)
video_hash = hash_obj.hexdigest()
```

### 2. 关键帧提取模块 (KeyFrame Extractor)

**文件**: `app/core/keyframe_extractor.py`

**职责**:
- 从视频中智能提取关键帧
- 双轨提取策略：规则提取 + 随机采样
- 计算每帧的异常分数

**双轨提取策略**:

```
输入视频
    │
    ├───→ 规则提取轨道 ───→ 高异常分数帧（视觉特征）
    │                         - 暗色沉积物检测
    │                         - 黄色牙菌斑检测
    │                         - 牙龈问题检测
    │
    └───→ 随机采样轨道 ───→ 均匀分布帧
                              - 确保区域覆盖
                              - 补充规则遗漏
    │
    ▼
合并策略：
- 优先保留规则提取的高异常帧
- 补充随机采样帧至目标数量
- 按时间顺序排序输出
```

**异常检测算法**:

| 检测类型 | 方法 | 阈值 |
|---------|------|------|
| 暗色沉积物 | 亮度通道分析 | < 60 |
| 黄色牙菌斑 | HSV 色彩空间 | S > 80, H 在黄色范围 |
| 牙龈问题 | 红色通道分析 | R > 150 |

### 3. 帧匹配模块 (Frame Matcher)

**文件**: `app/core/frame_matcher.py`

**职责**:
- 将当前关键帧与基线帧进行匹配
- 支持 Quick Check 与基线的对比分析

**匹配策略**:

```python
# 获取每个分区的中间帧作为代表
zone_middle_frames = {
    1: keyframe_zone_1_middle,  # 上颌左侧
    2: keyframe_zone_2_middle,  # 上颌前侧
    3: keyframe_zone_3_middle,  # 上颌右侧
    ...
}
```

### 4. Evidence Pack 生成器

**文件**: `app/core/evidence_pack.py`

**职责**:
- 聚合所有分析数据
- 构建结构化的 EvidencePack
- 包含用户历史上下文

**EvidencePack 结构**:

```json
{
  "session_id": "uuid",
  "session_type": "quick_check|baseline",
  "user_id": "uuid",
  "created_at": "2026-01-15T10:30:00",
  "frames": [
    {
      "frame_id": "uuid",
      "timestamp": 5.23,
      "image_url": "/data/A/keyframes/.../1.jpg",
      "extraction_strategy": "rule_based|random_sampled",
      "extraction_reason": "dark_deposit|yellow_plaque|gum_issue|uniform_sample",
      "anomaly_score": 0.75,
      "meta_tags": {
        "quality_score": 0.85,
        "sharpness": 0.72,
        "brightness": 128
      }
    }
  ],
  "baseline_reference": {
    "has_baseline": true,
    "baseline_session_id": "uuid",
    "comparison_mode": "zone_based|temporal",
    "matched_baseline_frames": [...]
  },
  "user_history": {
    "total_events": 5,
    "recent_events": [
      {
        "event_type": "dental_cleaning",
        "event_type_display": "洁牙",
        "event_date": "2025-12-01",
        "days_since": 45
      }
    ],
    "active_concerns": [
      {
        "concern_type": "dark_spots",
        "display_name": "色素沉着",
        "severity": "moderate",
        "zone_id": 2,
        "first_observed_at": "2025-11-01",
        "days_active": 76
      }
    ],
    "days_since_last_check": 30
  }
}
```

### 5. LLM 客户端与 Prompt 构建器

**文件**: 
- `app/core/llm_client.py`
- `app/core/llm_prompt_builder.py`

**职责**:
- 构建包含用户上下文的增强 Prompt
- 调用通义千问 Vision API
- 解析并存储生成报告

**Prompt 类型**:

| 类型 | 用途 | 特点 |
|------|------|------|
| Quick Check (无基线) | 首次检查或无历史数据 | 独立分析 |
| Quick Check (有基线) | 与历史数据对比 | 变化检测、趋势分析 |
| Baseline | 基线采集 | 详细记录、分区建档 |

---

## 数据库设计

### 实体关系图 (ERD)

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│    AUser     │       │   AProfile   │       │  AUserEvent  │
├──────────────┤       ├──────────────┤       ├──────────────┤
│ id (PK)      │◄──────┤ user_id (FK) │       │ id (PK)      │
│ phone_number │       │ nickname     │       │ user_id (FK) │
│ created_at   │       │ avatar_url   │       │ event_type   │
└──────────────┘       └──────────────┘       │ event_date   │
       │                                      │ notes        │
       │                                      └──────────────┘
       │
       │                 ┌──────────────┐       ┌──────────────┐
       │                 │ AConcernPoint│       │   ASetting   │
       │                 ├──────────────┤       ├──────────────┤
       │                 │ id (PK)      │       │ id (PK)      │
       │                 │ user_id (FK) │       │ user_id (FK) │
       │                 │ concern_type │       │ reminder_freq│
       └────────────────►│ severity     │       │ notify_enabled
                         │ zone_id      │       └──────────────┘
                         │ status       │
                         └──────────────┘
                                  │
                                  ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│    BVideo    │       │   ASession   │       │   AKeyframe  │
├──────────────┤       ├──────────────┤       ├──────────────┤
│ id (PK)      │◄──────┤ video_id (FK)│◄──────┤ session_id   │
│ file_hash    │       │ id (PK)      │       │ (FK)         │
│ file_path    │       │ user_id (FK) │       │ id (PK)      │
│ file_size    │       │ zone_id      │       │ frame_index  │
│ duration     │       │ session_type │       │ timestamp    │
│ resolution   │       │ status       │       │ image_path   │
└──────────────┘       │ started_at   │       │ anomaly_score│
                       └──────────────┘       │ meta_tags    │
                               │               └──────────────┘
                               │
                               ▼
                       ┌──────────────┐       ┌──────────────┐
                       │ AEvidencePack│       │    AReport   │
                       ├──────────────┤       ├──────────────┤
                       │ id (PK)      │◄──────┤ evidence_pack│
                       │ session_id   │       │ _id (FK)     │
                       │ (FK)         │       │ id (PK)      │
                       │ pack_data    │       │ report_text  │
                       │ (JSON)       │       │ llm_model    │
                       └──────────────┘       │ tokens_used  │
                                              └──────────────┘
```

### 表结构说明

#### AUser - 用户表
存储用户基础信息，以手机号作为唯一标识。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| phone_number | VARCHAR(20) | 手机号，唯一 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### AProfile - 用户档案表
存储用户可选的档案信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 外键 → AUser |
| nickname | VARCHAR(100) | 昵称 |
| avatar_url | TEXT | 头像 URL |
| date_of_birth | DATE | 出生日期 |

#### ASession - 检查会话表
记录每次视频检查会话。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 外键 → AUser |
| video_id | UUID | 外键 → BVideo |
| zone_id | INTEGER | 口腔分区 (1-7) |
| session_type | VARCHAR(20) | quick_check / baseline |
| processing_status | VARCHAR(20) | pending / processing / completed / failed |
| started_at | TIMESTAMP | 开始时间 |
| completed_at | TIMESTAMP | 完成时间 |

#### AKeyframe - 关键帧表
存储提取的关键帧信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| session_id | UUID | 外键 → ASession |
| frame_index | INTEGER | 帧序号 |
| timestamp_in_video | FLOAT | 视频时间戳(秒) |
| image_path | TEXT | 图片存储路径 |
| extraction_strategy | VARCHAR(20) | 提取策略 |
| extraction_reason | VARCHAR(100) | 提取原因 |
| anomaly_score | FLOAT | 异常分数 |
| meta_tags | JSON | 元数据标签 |

#### AUserEvent - 用户事件表
记录用户口腔相关事件（洁牙、补牙等）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 外键 → AUser |
| event_type | VARCHAR(50) | 事件类型 |
| event_date | DATE | 事件日期 |
| dentist_name | VARCHAR(100) | 医生姓名 |
| clinic_name | VARCHAR(200) | 诊所名称 |
| cost | DECIMAL | 费用 |
| notes | TEXT | 备注 |

#### AConcernPoint - 关注点表
追踪用户口腔问题关注点。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| user_id | UUID | 外键 → AUser |
| concern_type | VARCHAR(50) | 关注类型 |
| severity | VARCHAR(20) | 严重程度 |
| status | VARCHAR(20) | 状态 |
| zone_id | INTEGER | 分区 |
| first_observed_at | DATE | 首次观察 |
| last_observed_at | DATE | 最后观察 |

---

## 关键技术实现

### 1. 关键帧提取算法

```python
class KeyframeExtractor:
    def extract(self, video_path: str, target_count: int = 20) -> List[KeyframeData]:
        # 1. 规则提取：高异常分数帧
        rule_based_frames = self._extract_by_rules(video_path)
        
        # 2. 随机采样：均匀覆盖
        random_frames = self._extract_random_samples(
            video_path, 
            count=target_count - len(rule_based_frames)
        )
        
        # 3. 合并并去重
        all_frames = self._merge_frames(rule_based_frames, random_frames)
        
        # 4. 按时间排序
        return sorted(all_frames, key=lambda f: f.timestamp)
```

### 2. 异常分数计算

```python
def _detect_anomaly_opencv(frame: np.ndarray) -> tuple:
    """
    检测帧的异常分数
    
    Returns:
        (total_score, detail_scores, reason)
    """
    # 转换到 HSV 色彩空间
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # 暗色沉积物检测（低亮度区域）
    dark_mask = gray < 60
    dark_score = np.mean(dark_mask) * 0.8
    
    # 黄色牙菌斑检测
    yellow_lower = np.array([15, 80, 80])
    yellow_upper = np.array([35, 255, 255])
    yellow_mask = cv2.inRange(hsv, yellow_lower, yellow_upper)
    yellow_score = np.mean(yellow_mask > 0) * 0.6
    
    # 牙龈问题检测（红色区域）
    red_lower = np.array([0, 80, 80])
    red_upper = np.array([10, 255, 255])
    red_mask = cv2.inRange(hsv, red_lower, red_upper)
    gum_score = np.mean(red_mask > 0) * 0.5
    
    total_score = dark_score + yellow_score + gum_score
    detail_scores = {
        "dark_deposit": dark_score,
        "yellow_plaque": yellow_score,
        "gum_issue": gum_score
    }
    
    # 生成提取原因
    reasons = []
    if dark_score > 0.1:
        reasons.append("dark_deposit")
    if yellow_score > 0.1:
        reasons.append("yellow_plaque")
    if gum_score > 0.1:
        reasons.append("gum_issue")
    
    reason = ",".join(reasons) if reasons else "uniform_sample"
    
    return total_score, detail_scores, reason
```

### 3. Prompt 构建策略

```python
class PromptBuilder:
    @staticmethod
    def build_prompt(session: ASession, evidence_pack: EvidencePack) -> str:
        # 根据 session 类型选择 Prompt 模板
        if session.session_type == "baseline":
            return build_baseline_prompt(session, evidence_pack)
        else:  # quick_check
            if evidence_pack.baseline_reference.has_baseline:
                return build_comparison_prompt(session, evidence_pack)
            else:
                return build_standalone_quick_check_prompt(session, evidence_pack)
```

### 4. LLM API 调用

```python
def generate_report(self, session_id: str, evidence_pack: EvidencePack) -> AReport:
    # 1. 构建 Prompt
    prompt = self._build_prompt(session, evidence_pack)
    
    # 2. 获取基线中间帧（用于对比）
    baseline_frames = self._get_baseline_middle_frames(session.user_id)
    
    # 3. 调用千问 Vision API
    result = self.qianwen_client.analyze_evidence_pack(
        evidence_pack=evidence_pack,
        prompt=prompt,
        baseline_frames=baseline_frames
    )
    
    # 4. 保存报告
    report = AReport(
        session_id=session_id,
        report_text=result.text,
        tokens_used=result.total_tokens
    )
    
    return report
```

---

## 附录

### A. 口腔分区定义

| 分区 ID | 名称 | 描述 |
|---------|------|------|
| 1 | 上颌左侧 | 左上后牙区域 |
| 2 | 上颌前侧 | 上中切牙区域 |
| 3 | 上颌右侧 | 右上后牙区域 |
| 4 | 下颌左侧 | 左下后牙区域 |
| 5 | 下颌前侧 | 下中切牙区域 |
| 6 | 下颌右侧 | 右下后牙区域 |
| 7 | 全口概览 | 整体口腔视图 |

### B. 事件类型映射

| 事件类型 | 中文显示 | 说明 |
|---------|---------|------|
| dental_cleaning | 洁牙 | 专业洗牙 |
| filling | 补牙 | 龋齿填充 |
| extraction | 拔牙 | 牙齿拔除 |
| orthodontic | 正畸 | 矫正治疗 |
| whitening | 美白 | 牙齿美白 |
| checkup | 常规检查 | 定期检查 |
| other | 其他 | 其他事件 |

### C. 关注点类型

| 关注点类型 | 中文显示 | 说明 |
|-----------|---------|------|
| dark_spots | 色素沉着 | 牙齿表面色斑 |
| plaque_buildup | 牙菌斑堆积 | 细菌生物膜 |
| gum_inflammation | 牙龈红肿 | 牙龈炎症 |
| tooth_decay | 龋齿 | 蛀牙 |
| calculus | 牙结石 | 钙化沉积物 |
| sensitivity | 敏感 | 牙齿敏感 |
| misalignment | 排列不齐 | 牙齿错位 |
| other | 其他 | 其他问题 |
