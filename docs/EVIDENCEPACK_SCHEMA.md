# EvidencePack 结构与数据 Schema 技术文档

> 版本: V1.0  
> 更新日期: 2026-02-03

---

## 目录

1. [概述](#概述)
2. [顶层结构](#顶层结构)
3. [核心数据模型](#核心数据模型)
4. [用户历史上下文](#用户历史上下文)
5. [完整 JSON Schema](#完整-json-schema)
6. [数据流转与生命周期](#数据流转与生命周期)
7. [使用示例](#使用示例)
8. [版本兼容性](#版本兼容性)

---

## 概述

EvidencePack（证据包）是智能口腔健康监测系统的核心数据载体，它在视频处理和 LLM 分析之间起到桥梁作用。它封装了从视频提取的关键帧、元数据、用户历史上下文以及与基线的对比信息，为 LLM 提供完整、结构化的分析输入。

### 设计目标

- **完整性**: 包含 LLM 分析所需的所有上下文信息
- **可追溯性**: 每个数据项都有明确的来源和时间戳
- **可扩展性**: 支持未来新增字段而不破坏兼容性
- **序列化友好**: 支持 JSON 序列化，便于存储和传输

### 使用场景

| 场景 | 说明 |
|------|------|
| 关键帧存储 | 保存提取的关键帧元数据和路径 |
| LLM 输入 | 作为通义千问 Vision API 的结构化输入 |
| 报告生成 | 支持个性化报告的上下文构建 |
| 历史对比 | 提供与基线数据的对比依据 |
| 数据导出 | 支持用户数据的结构化导出 |

---

## 顶层结构

```python
class EvidencePack(BaseModel):
    """EvidencePack 顶层模型"""
    
    # 基础标识
    session_id: str                          # Session 唯一标识 (UUID)
    session_type: Literal["quick_check", "baseline"]  # Session 类型
    user_id: str                             # 用户标识 (UUID)
    created_at: datetime                     # 创建时间 (ISO 8601)
    
    # 核心数据
    frames: List[KeyframeData]               # 关键帧列表 (5-25帧)
    
    # 上下文信息
    baseline_reference: BaselineReference    # 基线参考信息
    user_history: Optional[UserHistorySummary]  # 用户历史摘要
```

### 字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `session_id` | string | ✅ | Session UUID，唯一标识一次检查 |
| `session_type` | string | ✅ | `quick_check` (快速检查) 或 `baseline` (基线采集) |
| `user_id` | string | ✅ | 用户 UUID |
| `created_at` | datetime | ✅ | EvidencePack 生成时间 |
| `frames` | array | ✅ | 关键帧数据数组，按时间顺序排列 |
| `baseline_reference` | object | ✅ | 基线对比相关信息 |
| `user_history` | object | ❌ | 用户历史上下文（检查记录、事件、关注点） |

---

## 核心数据模型

### 1. KeyframeData - 关键帧数据

表示从视频中提取的一帧关键图像及其元数据。

```python
class KeyframeData(BaseModel):
    """关键帧数据结构"""
    
    # 标识信息
    frame_id: str                            # 帧唯一标识
    frame_index: int                         # 在视频中的帧序号
    
    # 时间信息
    timestamp: float                         # 视频中的时间戳（秒）
    
    # 存储路径
    image_url: str                           # 图像文件路径/URL
    
    # 提取策略
    extraction_strategy: str                 # 提取策略类型
    extraction_reason: str                   # 提取原因/标签
    
    # 质量指标
    anomaly_score: float                     # 异常分数 (0.0-1.0+)
    meta_tags: FrameMetaTags                 # 元数据标签
```

#### 字段详解

| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| `frame_id` | string | `"frame-001"` | 帧的唯一标识符 |
| `frame_index` | integer | `150` | 在原始视频中的帧序号 |
| `timestamp` | float | `5.23` | 视频时间戳，单位秒 |
| `image_url` | string | `"/data/A/keyframes/{session_id}/0.jpg"` | 图像存储路径 |
| `extraction_strategy` | string | `"rule_based"` | 提取策略：`rule_based` 或 `random_sampled` |
| `extraction_reason` | string | `"dark_deposit,gum_issue"` | 提取原因标签，逗号分隔 |
| `anomaly_score` | float | `0.75` | 异常分数，越高表示越可能有问题 |
| `meta_tags` | object | `{...}` | 详细元数据 |

#### 提取策略类型

| 类型 | 说明 | 优先级 |
|------|------|--------|
| `rule_based` | 基于规则的提取（检测到异常特征） | 高 |
| `random_sampled` | 均匀随机采样 | 低 |
| `uniform_sampled` | 均匀时间间隔采样 | 低 |

#### 提取原因标签

| 标签 | 说明 | 触发条件 |
|------|------|----------|
| `dark_deposit` | 暗色沉积物 | 亮度 < 60 的区域占比 > 10% |
| `yellow_plaque` | 黄色牙菌斑 | HSV 黄色区域检测 |
| `gum_issue` | 牙龈问题 | 红色通道异常 |
| `uniform_sample` | 均匀采样 | 作为补充帧 |

---

### 2. FrameMetaTags - 帧元数据标签

包含关键帧的图像质量和技术指标。

```python
class FrameMetaTags(BaseModel):
    """帧元数据标签"""
    
    quality_score: Optional[float] = None    # 图像质量评分 (0-1)
    sharpness: Optional[float] = None        # 清晰度/锐度
    brightness: Optional[float] = None       # 亮度值
    contrast: Optional[float] = None         # 对比度
    blur_score: Optional[float] = None       # 模糊度（越低越好）
    face_detected: Optional[bool] = None     # 是否检测到人脸
    mouth_region: Optional[Dict] = None      # 口腔区域坐标
    
    # 详细异常分数（规则提取时）
    dark_deposit_score: Optional[float] = None    # 暗色沉积物分数
    yellow_plaque_score: Optional[float] = None   # 黄色牙菌斑分数
    gum_issue_score: Optional[float] = None       # 牙龈问题分数
```

#### 字段详解

| 字段 | 类型 | 范围 | 说明 |
|------|------|------|------|
| `quality_score` | float | 0.0-1.0 | 综合图像质量评分 |
| `sharpness` | float | 0.0+ | 拉普拉斯算子计算的清晰度 |
| `brightness` | float | 0-255 | 平均亮度值 |
| `contrast` | float | 0.0+ | 对比度指标 |
| `blur_score` | float | 0.0+ | 模糊度，< 100 表示较清晰 |
| `face_detected` | bool | true/false | 人脸检测结果 |
| `mouth_region` | object | `{x, y, w, h}` | 口腔区域边界框 |
| `dark_deposit_score` | float | 0.0-1.0 | 暗色沉积物检测分数 |
| `yellow_plaque_score` | float | 0.0-1.0 | 黄色牙菌斑检测分数 |
| `gum_issue_score` | float | 0.0-1.0 | 牙龈问题检测分数 |

---

### 3. BaselineReference - 基线参考

包含与历史基线数据的对比信息。

```python
class BaselineReference(BaseModel):
    """基线参考信息"""
    
    has_baseline: bool = False               # 是否存在基线
    baseline_session_id: Optional[str] = None  # 基线 Session ID
    comparison_mode: str = "none"            # 对比模式
    matched_baseline_frames: List[MatchedBaselineFrame] = []  # 匹配的基线帧
```

#### 字段详解

| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| `has_baseline` | bool | `true` | 是否找到匹配的基线数据 |
| `baseline_session_id` | string | `"uuid..."` | 基线 Session 的 ID |
| `comparison_mode` | string | `"zone_based"` | 对比模式类型 |
| `matched_baseline_frames` | array | `[{...}]` | 当前帧与基线帧的匹配关系 |

#### 对比模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `none` | 无对比 | 首次检查或无基线 |
| `zone_based` | 基于分区匹配 | 同分区对比 |
| `temporal` | 基于时间匹配 | 按时间顺序对比 |
| `similarity` | 基于相似度匹配 | 内容相似帧对比 |

---

### 4. MatchedBaselineFrame - 匹配的基线帧

表示当前帧与基线帧的匹配关系。

```python
class MatchedBaselineFrame(BaseModel):
    """匹配的基线帧"""
    
    current_frame_index: int                 # 当前帧索引
    baseline_frame_index: int                # 基线帧索引
    baseline_zone_id: int                    # 基线帧所在分区
    similarity_score: Optional[float] = None  # 相似度分数
```

#### 字段详解

| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| `current_frame_index` | int | `0` | 当前 EvidencePack 中的帧索引 |
| `baseline_frame_index` | int | `5` | 基线 Session 中的帧索引 |
| `baseline_zone_id` | int | `2` | 基线帧所属口腔分区 |
| `similarity_score` | float | `0.88` | 两帧相似度 (0-1) |

---

## 用户历史上下文

### 5. UserHistorySummary - 用户历史摘要

提供用户的历史检查记录、就诊事件和关注点信息，支持 LLM 的个性化分析。

```python
class UserHistorySummary(BaseModel):
    """用户历史摘要"""
    
    # 统计信息
    total_events: int = 0                    # 总事件数
    recent_events: List[UserEventData] = []  # 近期事件（最近6个月）
    
    # 关注点
    active_concerns: List[ConcernPointData] = []      # 活跃关注点
    resolved_concerns_count: int = 0                  # 已解决关注点数
    monitoring_concerns_count: int = 0                # 监测中关注点数
    
    # 时间维度
    days_since_last_check: Optional[int] = None       # 距上次检查天数
    days_since_last_event: Optional[int] = None       # 距上次事件天数
```

#### 字段详解

| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| `total_events` | int | `5` | 用户历史事件总数 |
| `recent_events` | array | `[{...}]` | 最近6个月的事件列表（最多10条） |
| `active_concerns` | array | `[{...}]` | 状态为 `active` 的关注点 |
| `resolved_concerns_count` | int | `3` | 已解决的关注点数量 |
| `monitoring_concerns_count` | int | `2` | 监测中的关注点数量 |
| `days_since_last_check` | int | `30` | 距上次检查的天数 |
| `days_since_last_event` | int | `45` | 距上次事件的天数 |

---

### 6. UserEventData - 用户事件数据

记录用户的口腔相关事件（洁牙、补牙等）。

```python
class UserEventData(BaseModel):
    """用户事件数据"""
    
    event_type: str                          # 事件类型
    event_type_display: str                  # 事件类型中文显示
    event_date: date                         # 事件日期
    days_since: int                          # 距今天数
    dentist_name: Optional[str] = None       # 医生姓名
    clinic_name: Optional[str] = None        # 诊所名称
    cost: Optional[float] = None             # 费用
    notes: Optional[str] = None              # 备注
```

#### 字段详解

| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| `event_type` | string | `"dental_cleaning"` | 事件类型标识 |
| `event_type_display` | string | `"洁牙"` | 中文显示名称 |
| `event_date` | date | `"2025-12-01"` | 事件发生日期 |
| `days_since` | int | `45` | 距离今天的天数 |
| `dentist_name` | string | `"李医生"` | 医生姓名（可选） |
| `clinic_name` | string | `"美奥口腔"` | 诊所名称（可选） |
| `cost` | float | `380.0` | 费用（可选） |
| `notes` | string | `"无不适"` | 备注（可选） |

#### 事件类型映射

| 类型标识 | 中文显示 | 典型场景 |
|----------|----------|----------|
| `dental_cleaning` | 洁牙 | 定期洗牙 |
| `filling` | 补牙 | 龋齿填充 |
| `extraction` | 拔牙 | 智齿拔除等 |
| `orthodontic` | 正畸 | 矫正治疗 |
| `whitening` | 美白 | 牙齿美白 |
| `checkup` | 常规检查 | 定期检查 |
| `other` | 其他 | 其他事件 |

---

### 7. ConcernPointData - 关注点数据

追踪用户口腔问题的关注点。

```python
class ConcernPointData(BaseModel):
    """关注点数据"""
    
    concern_type: str                        # 关注点类型
    display_name: str                        # 中文显示名称
    severity: str                            # 严重程度
    severity_display: str                    # 严重程度中文
    status: str                              # 状态
    status_display: str                      # 状态中文
    zone_id: Optional[int] = None            # 所在分区
    zone_display: str                        # 分区中文显示
    first_observed_at: date                  # 首次观察日期
    last_observed_at: Optional[date] = None  # 最后观察日期
    days_active: int                         # 持续天数
    notes: Optional[str] = None              # 备注
```

#### 字段详解

| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| `concern_type` | string | `"dark_spots"` | 关注点类型标识 |
| `display_name` | string | `"色素沉着"` | 中文显示名称 |
| `severity` | string | `"moderate"` | 严重程度标识 |
| `severity_display` | string | `"中度"` | 严重程度中文 |
| `status` | string | `"active"` | 状态标识 |
| `status_display` | string | `"活跃"` | 状态中文 |
| `zone_id` | int | `2` | 口腔分区编号 |
| `zone_display` | string | `"上颌前侧"` | 分区中文名称 |
| `first_observed_at` | date | `"2025-11-01"` | 首次发现日期 |
| `last_observed_at` | date | `"2025-12-15"` | 最后观察日期 |
| `days_active` | int | `76` | 问题持续天数 |
| `notes` | string | `"黄色斑点"` | 备注说明 |

#### 关注点类型映射

| 类型标识 | 中文显示 | 说明 |
|----------|----------|------|
| `dark_spots` | 色素沉着 | 牙齿表面色斑 |
| `plaque_buildup` | 牙菌斑堆积 | 细菌生物膜 |
| `gum_inflammation` | 牙龈红肿 | 牙龈炎症 |
| `tooth_decay` | 龋齿 | 蛀牙 |
| `calculus` | 牙结石 | 钙化沉积物 |
| `sensitivity` | 敏感 | 牙齿敏感 |
| `misalignment` | 排列不齐 | 牙齿错位 |
| `other` | 其他 | 其他问题 |

#### 严重程度映射

| 标识 | 中文 | 说明 |
|------|------|------|
| `mild` | 轻度 | 轻微问题，可观察 |
| `moderate` | 中度 | 需要关注和处理 |
| `severe` | 重度 | 需要立即处理 |

#### 状态映射

| 标识 | 中文 | 说明 |
|------|------|------|
| `active` | 活跃 | 需要关注的活跃问题 |
| `resolved` | 已解决 | 问题已解决 |
| `monitoring` | 监测中 | 正在观察中 |

---

## 完整 JSON Schema

### EvidencePack 完整示例

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_type": "quick_check",
  "user_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "created_at": "2026-01-15T10:30:00+08:00",
  "frames": [
    {
      "frame_id": "frame-001",
      "frame_index": 150,
      "timestamp": 5.0,
      "image_url": "/data/A/keyframes/550e8400/0.jpg",
      "extraction_strategy": "rule_based",
      "extraction_reason": "dark_deposit,gum_issue",
      "anomaly_score": 0.75,
      "meta_tags": {
        "quality_score": 0.85,
        "sharpness": 245.5,
        "brightness": 128.0,
        "contrast": 45.2,
        "blur_score": 50.0,
        "face_detected": true,
        "mouth_region": {
          "x": 200,
          "y": 300,
          "width": 400,
          "height": 300
        },
        "dark_deposit_score": 0.35,
        "yellow_plaque_score": 0.0,
        "gum_issue_score": 0.30
      }
    },
    {
      "frame_id": "frame-002",
      "frame_index": 300,
      "timestamp": 10.0,
      "image_url": "/data/A/keyframes/550e8400/1.jpg",
      "extraction_strategy": "random_sampled",
      "extraction_reason": "uniform_sample",
      "anomaly_score": 0.15,
      "meta_tags": {
        "quality_score": 0.90,
        "sharpness": 280.0,
        "brightness": 135.0,
        "contrast": 48.0,
        "blur_score": 35.0,
        "face_detected": true,
        "mouth_region": {
          "x": 210,
          "y": 310,
          "width": 380,
          "height": 290
        }
      }
    }
  ],
  "baseline_reference": {
    "has_baseline": true,
    "baseline_session_id": "6ba7b809-9dad-11d1-80b4-00c04fd430c8",
    "comparison_mode": "zone_based",
    "matched_baseline_frames": [
      {
        "current_frame_index": 0,
        "baseline_frame_index": 5,
        "baseline_zone_id": 2,
        "similarity_score": 0.88
      }
    ]
  },
  "user_history": {
    "total_events": 3,
    "recent_events": [
      {
        "event_type": "dental_cleaning",
        "event_type_display": "洁牙",
        "event_date": "2025-12-01",
        "days_since": 45,
        "dentist_name": "李医生",
        "clinic_name": "美奥口腔",
        "cost": 380.0,
        "notes": "超声波洁牙，无不适"
      }
    ],
    "active_concerns": [
      {
        "concern_type": "dark_spots",
        "display_name": "色素沉着",
        "severity": "moderate",
        "severity_display": "中度",
        "status": "active",
        "status_display": "活跃",
        "zone_id": 2,
        "zone_display": "上颌前侧",
        "first_observed_at": "2025-11-01",
        "last_observed_at": "2025-12-15",
        "days_active": 76,
        "notes": "上颌前牙区域可见黄色斑点"
      }
    ],
    "resolved_concerns_count": 2,
    "monitoring_concerns_count": 1,
    "days_since_last_check": 30,
    "days_since_last_event": 45
  }
}
```

### JSON Schema 定义

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "EvidencePack",
  "type": "object",
  "required": ["session_id", "session_type", "user_id", "created_at", "frames", "baseline_reference"],
  "properties": {
    "session_id": {
      "type": "string",
      "format": "uuid",
      "description": "Session 唯一标识"
    },
    "session_type": {
      "type": "string",
      "enum": ["quick_check", "baseline"],
      "description": "Session 类型"
    },
    "user_id": {
      "type": "string",
      "format": "uuid",
      "description": "用户标识"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "创建时间 (ISO 8601)"
    },
    "frames": {
      "type": "array",
      "items": { "$ref": "#/definitions/KeyframeData" },
      "minItems": 5,
      "maxItems": 25,
      "description": "关键帧列表"
    },
    "baseline_reference": {
      "$ref": "#/definitions/BaselineReference",
      "description": "基线参考信息"
    },
    "user_history": {
      "$ref": "#/definitions/UserHistorySummary",
      "description": "用户历史摘要"
    }
  },
  "definitions": {
    "KeyframeData": {
      "type": "object",
      "required": ["frame_id", "frame_index", "timestamp", "image_url", "extraction_strategy", "anomaly_score"],
      "properties": {
        "frame_id": { "type": "string" },
        "frame_index": { "type": "integer", "minimum": 0 },
        "timestamp": { "type": "number", "minimum": 0 },
        "image_url": { "type": "string", "format": "uri" },
        "extraction_strategy": { 
          "type": "string",
          "enum": ["rule_based", "random_sampled", "uniform_sampled"]
        },
        "extraction_reason": { "type": "string" },
        "anomaly_score": { "type": "number", "minimum": 0, "maximum": 10 },
        "meta_tags": { "$ref": "#/definitions/FrameMetaTags" }
      }
    },
    "FrameMetaTags": {
      "type": "object",
      "properties": {
        "quality_score": { "type": "number", "minimum": 0, "maximum": 1 },
        "sharpness": { "type": "number", "minimum": 0 },
        "brightness": { "type": "number", "minimum": 0, "maximum": 255 },
        "contrast": { "type": "number", "minimum": 0 },
        "blur_score": { "type": "number", "minimum": 0 },
        "face_detected": { "type": "boolean" },
        "mouth_region": {
          "type": "object",
          "properties": {
            "x": { "type": "integer" },
            "y": { "type": "integer" },
            "width": { "type": "integer" },
            "height": { "type": "integer" }
          }
        },
        "dark_deposit_score": { "type": "number", "minimum": 0, "maximum": 1 },
        "yellow_plaque_score": { "type": "number", "minimum": 0, "maximum": 1 },
        "gum_issue_score": { "type": "number", "minimum": 0, "maximum": 1 }
      }
    },
    "BaselineReference": {
      "type": "object",
      "required": ["has_baseline", "comparison_mode"],
      "properties": {
        "has_baseline": { "type": "boolean" },
        "baseline_session_id": { "type": "string", "format": "uuid" },
        "comparison_mode": { 
          "type": "string",
          "enum": ["none", "zone_based", "temporal", "similarity"]
        },
        "matched_baseline_frames": {
          "type": "array",
          "items": { "$ref": "#/definitions/MatchedBaselineFrame" }
        }
      }
    },
    "MatchedBaselineFrame": {
      "type": "object",
      "required": ["current_frame_index", "baseline_frame_index", "baseline_zone_id"],
      "properties": {
        "current_frame_index": { "type": "integer", "minimum": 0 },
        "baseline_frame_index": { "type": "integer", "minimum": 0 },
        "baseline_zone_id": { "type": "integer", "minimum": 1, "maximum": 7 },
        "similarity_score": { "type": "number", "minimum": 0, "maximum": 1 }
      }
    },
    "UserHistorySummary": {
      "type": "object",
      "properties": {
        "total_events": { "type": "integer", "minimum": 0 },
        "recent_events": {
          "type": "array",
          "items": { "$ref": "#/definitions/UserEventData" },
          "maxItems": 10
        },
        "active_concerns": {
          "type": "array",
          "items": { "$ref": "#/definitions/ConcernPointData" }
        },
        "resolved_concerns_count": { "type": "integer", "minimum": 0 },
        "monitoring_concerns_count": { "type": "integer", "minimum": 0 },
        "days_since_last_check": { "type": "integer", "minimum": 0 },
        "days_since_last_event": { "type": "integer", "minimum": 0 }
      }
    },
    "UserEventData": {
      "type": "object",
      "required": ["event_type", "event_type_display", "event_date", "days_since"],
      "properties": {
        "event_type": { "type": "string" },
        "event_type_display": { "type": "string" },
        "event_date": { "type": "string", "format": "date" },
        "days_since": { "type": "integer", "minimum": 0 },
        "dentist_name": { "type": ["string", "null"] },
        "clinic_name": { "type": ["string", "null"] },
        "cost": { "type": ["number", "null"] },
        "notes": { "type": ["string", "null"] }
      }
    },
    "ConcernPointData": {
      "type": "object",
      "required": ["concern_type", "display_name", "severity", "severity_display", "status", "status_display", "first_observed_at", "days_active"],
      "properties": {
        "concern_type": { "type": "string" },
        "display_name": { "type": "string" },
        "severity": { 
          "type": "string",
          "enum": ["mild", "moderate", "severe"]
        },
        "severity_display": { "type": "string" },
        "status": { 
          "type": "string",
          "enum": ["active", "resolved", "monitoring"]
        },
        "status_display": { "type": "string" },
        "zone_id": { "type": ["integer", "null"], "minimum": 1, "maximum": 7 },
        "zone_display": { "type": "string" },
        "first_observed_at": { "type": "string", "format": "date" },
        "last_observed_at": { "type": ["string", "null"], "format": "date" },
        "days_active": { "type": "integer", "minimum": 0 },
        "notes": { "type": ["string", "null"] }
      }
    }
  }
}
```

---

## 数据流转与生命周期

### EvidencePack 生成流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        EvidencePack 生成流程                      │
└─────────────────────────────────────────────────────────────────┘

1. 视频摄入 (Ingestion)
   └─► 视频存入 B-Stream
       └─► 获取 video_id
           │
           ▼
2. Session 创建
   └─► 创建 ASession 记录
       └─► 获取 session_id, user_id
           │
           ▼
3. 关键帧提取 (Keyframe Extraction)
   └─► KeyframeExtractor.extract()
       └─► 生成 KeyframeData 列表
           - frame_id, timestamp
           - extraction_strategy, extraction_reason
           - anomaly_score, meta_tags
           │
           ▼
4. 帧匹配 (Frame Matching)
   └─► FrameMatcher.match()
       └─► 生成 BaselineReference
           - has_baseline
           - matched_baseline_frames[]
           │
           ▼
5. 用户历史构建 (User History)
   └─► EvidencePackGenerator._build_user_history()
       └─► 查询数据库
           - AUserEvent (最近6个月)
           - AConcernPoint (按状态分组)
       └─► 生成 UserHistorySummary
           - total_events, recent_events[]
           - active_concerns[]
           - days_since_last_check
           │
           ▼
6. EvidencePack 组装
   └─► 整合所有组件
       └─► EvidencePack 对象
           │
           ▼
7. 序列化存储
   └─► JSON 序列化
       └─► 存入 AEvidencePack 表
           └─► 同时存入文件: data/A/evidence/{session_id}.json
```

### EvidencePack 使用场景

```
┌─────────────────────────────────────────────────────────────────┐
│                        EvidencePack 使用场景                      │
└─────────────────────────────────────────────────────────────────┘

场景 1: LLM 报告生成
───────────────────────────────────────────────────────────────────
EvidencePack
    │
    ├─► PromptBuilder.build_prompt()
    │   └─► 提取 frames[].image_url 作为图片输入
    │   └─► 提取 user_history 构建上下文 Prompt
    │   └─► 提取 baseline_reference 构建对比指令
    │
    └─► QianwenVisionClient.analyze()
        └─► 发送图片 + Prompt 到千问 API
            └─► 返回分析报告

场景 2: 数据导出
───────────────────────────────────────────────────────────────────
EvidencePack
    │
    └─► JSON 序列化
        └─► 用户下载历史数据

场景 3: 报告重新生成
───────────────────────────────────────────────────────────────────
EvidencePack (从数据库加载)
    │
    └─► 更新某些字段
        └─► 重新触发 LLM 分析

场景 4: 趋势分析
───────────────────────────────────────────────────────────────────
EvidencePack[] (多个历史记录)
    │
    └─► 提取 user_history.concerns
        └─► 分析关注点变化趋势
```

---

## 使用示例

### 1. 创建 EvidencePack

```python
from app.core.evidence_pack import EvidencePackGenerator
from app.models.database import get_db

# 获取数据库会话
db = next(get_db())

# 创建生成器
generator = EvidencePackGenerator(db)

# 生成 EvidencePack
evidence_pack = generator.generate_evidence_pack(
    session_id="550e8400-e29b-41d4-a716-446655440000",
    frames=extracted_frames,  # List[KeyframeData]
    baseline_reference=baseline_ref  # BaselineReference
)

# 访问数据
print(f"Session: {evidence_pack.session_id}")
print(f"Frames: {len(evidence_pack.frames)}")
print(f"Has baseline: {evidence_pack.baseline_reference.has_baseline}")
```

### 2. 序列化与反序列化

```python
from app.models.evidence_pack import EvidencePack
import json

# 序列化为 JSON
json_str = evidence_pack.model_dump_json(indent=2)

# 保存到文件
with open("evidence_pack.json", "w") as f:
    f.write(json_str)

# 从 JSON 反序列化
with open("evidence_pack.json", "r") as f:
    data = json.load(f)

evidence_pack = EvidencePack.model_validate(data)
```

### 3. 访问关键帧数据

```python
# 遍历所有关键帧
for frame in evidence_pack.frames:
    print(f"Frame {frame.frame_index} @ {frame.timestamp:.2f}s")
    print(f"  Strategy: {frame.extraction_strategy}")
    print(f"  Reason: {frame.extraction_reason}")
    print(f"  Anomaly Score: {frame.anomaly_score:.2f}")
    
    # 访问元数据
    if frame.meta_tags:
        print(f"  Quality: {frame.meta_tags.quality_score:.2f}")
        print(f"  Sharpness: {frame.meta_tags.sharpness:.2f}")

# 按策略筛选
rule_based_frames = [
    f for f in evidence_pack.frames 
    if f.extraction_strategy == "rule_based"
]
print(f"规则提取帧数: {len(rule_based_frames)}")

# 按异常分数排序
sorted_frames = sorted(
    evidence_pack.frames,
    key=lambda f: f.anomaly_score,
    reverse=True
)
```

### 4. 访问用户历史

```python
history = evidence_pack.user_history
if history:
    print(f"距上次检查: {history.days_since_last_check} 天")
    print(f"历史事件数: {history.total_events}")
    
    # 遍历近期事件
    for event in history.recent_events:
        print(f"  - {event.event_type_display}: {event.days_since} 天前")
    
    # 遍历活跃关注点
    for concern in history.active_concerns:
        print(f"  ⚠️ {concern.display_name} ({concern.severity_display})")
        print(f"     位置: {concern.zone_display}")
        print(f"     持续: {concern.days_active} 天")
```

### 5. 基线对比分析

```python
baseline = evidence_pack.baseline_reference
if baseline.has_baseline:
    print(f"基线 Session: {baseline.baseline_session_id}")
    print(f"对比模式: {baseline.comparison_mode}")
    
    # 遍历匹配的基线帧
    for match in baseline.matched_baseline_frames:
        print(f"  当前帧 #{match.current_frame_index}")
        print(f"    → 匹配基线帧 #{match.baseline_frame_index}")
        print(f"    → 分区: {match.baseline_zone_id}")
        print(f"    → 相似度: {match.similarity_score:.2f}")
```

---

## 版本兼容性

### 当前版本: V1.0

EvidencePack Schema 版本遵循语义化版本控制 (SemVer)。

#### 版本变更规则

| 版本类型 | 规则 | 示例 |
|----------|------|------|
| 主版本 (X.0.0) | 不兼容的结构变更 | 删除必填字段、修改字段类型 |
| 次版本 (0.X.0) | 向后兼容的功能添加 | 新增可选字段 |
| 修订版本 (0.0.X) | 向后兼容的问题修复 | 文档更新、默认值调整 |

#### V1.0 特性

- ✅ 支持 `quick_check` 和 `baseline` 两种 Session 类型
- ✅ 最多 25 个关键帧，最少 5 个
- ✅ 完整的用户历史上下文（事件、关注点）
- ✅ 基线对比支持
- ✅ 详细的关键帧元数据

#### 未来可能的扩展

| 功能 | 描述 | 预计版本 |
|------|------|----------|
| 3D 扫描数据 | 支持口腔 3D 模型 | V1.1 |
| 多模态分析 | 结合 X 光片数据 | V1.2 |
| 时间序列 | 更详细的趋势数据 | V1.3 |

#### 迁移策略

当 Schema 升级时，系统会：

1. 保留旧版本数据（向后兼容读取）
2. 新数据使用新 Schema 写入
3. 提供数据迁移脚本（必要时）

```python
# 兼容性读取示例
from pydantic import ValidationError

try:
    evidence_pack = EvidencePack.model_validate(data)
except ValidationError as e:
    # 尝试使用旧版本 Schema 读取
    evidence_pack = EvidencePackV0.model_validate(data)
    # 转换为当前版本
    evidence_pack = migrate_v0_to_v1(evidence_pack)
```

---

## 附录

### A. 口腔分区定义

| 分区 ID | 中文名称 | 英文名称 | 描述 |
|---------|----------|----------|------|
| 1 | 上颌左侧 | Upper Left | 左上后牙区域 |
| 2 | 上颌前侧 | Upper Front | 上颌前牙区域 |
| 3 | 上颌右侧 | Upper Right | 右上后牙区域 |
| 4 | 下颌左侧 | Lower Left | 左下后牙区域 |
| 5 | 下颌前侧 | Lower Front | 下颌前牙区域 |
| 6 | 下颌右侧 | Lower Right | 右下后牙区域 |
| 7 | 全口概览 | Full Mouth | 整体口腔视图 |

### B. 数据库映射

| EvidencePack 字段 | 数据库表 | 表字段 |
|-------------------|----------|--------|
| session_id | asession | id |
| user_id | asession | user_id |
| session_type | asession | session_type |
| frames[] | akeyframe | * (多条记录) |
| user_history | (计算字段) | 查询 aevent + aconcern |
| baseline_reference | (计算字段) | 查询历史 session |

### C. 文件存储映射

| 数据类型 | 文件路径 |
|----------|----------|
| EvidencePack JSON | `data/A/evidence/{session_id}.json` |
| 关键帧图像 | `data/A/keyframes/{session_id}/{index}.jpg` |
| 分析报告 | `data/A/reports/{report_id}.md` |
