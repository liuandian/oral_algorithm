# 智能口腔健康监测系统 - API 使用指南

> 版本: V1.0  
> 更新日期: 2026-02-03

---

## 目录

1. [API 概述](#api-概述)
2. [用户管理 API](#用户管理-api)
3. [视频上传 API](#视频上传-api)
4. [Session 管理 API](#session-管理-api)
5. [报告获取 API](#报告获取-api)
6. [用户档案 API](#用户档案-api)
7. [错误处理](#错误处理)

---

## API 概述

### 基础信息

| 项目 | 内容 |
|------|------|
| 基础 URL | `http://localhost:8000/api/v1` |
| 协议 | HTTP/1.1 (开发) / HTTPS (生产) |
| 数据格式 | JSON |
| 认证方式 | JWT Token (Bearer) |

### 响应格式

所有 API 响应遵循统一格式：

**成功响应:**
```json
{
  "status": "success",
  "data": { ... },
  "message": "操作成功"
}
```

**错误响应:**
```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述",
    "details": { ... }
  }
}
```

### HTTP 状态码

| 状态码 | 含义 | 说明 |
|--------|------|------|
| 200 | OK | 请求成功 |
| 201 | Created | 资源创建成功 |
| 400 | Bad Request | 请求参数错误 |
| 401 | Unauthorized | 未认证或认证失败 |
| 404 | Not Found | 资源不存在 |
| 409 | Conflict | 资源冲突（如重复） |
| 422 | Validation Error | 数据验证失败 |
| 500 | Internal Server Error | 服务器内部错误 |

---

## 用户管理 API

### 1. 用户注册

**POST** `/users/register`

创建新用户账户。

**请求参数:**
```json
{
  "phone_number": "13800138000"
}
```

**响应示例:**
```json
{
  "status": "success",
  "data": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "phone_number": "13800138000",
    "created_at": "2026-01-15T10:30:00"
  },
  "message": "用户注册成功"
}
```

**错误情况:**
- `409 Conflict`: 手机号已注册

---

### 2. 用户登录

**POST** `/users/login`

用户登录获取 JWT Token。

**请求参数:**
```json
{
  "phone_number": "13800138000"
}
```

**响应示例:**
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user_id": "550e8400-e29b-41d4-a716-446655440000"
  },
  "message": "登录成功"
}
```

---

### 3. 获取当前用户信息

**GET** `/users/me`

获取当前登录用户的基本信息。

**请求头:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**响应示例:**
```json
{
  "status": "success",
  "data": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "phone_number": "13800138000",
    "profile": {
      "nickname": "张三",
      "avatar_url": "https://example.com/avatar.jpg"
    },
    "created_at": "2026-01-15T10:30:00"
  }
}
```

---

## 视频上传 API

### 1. 上传视频

**POST** `/upload/video`

上传口腔视频文件，系统会自动创建 Session 并开始处理流程。

**请求头:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: multipart/form-data
```

**请求参数:**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | 视频文件 (MP4/MOV, 最大 100MB) |
| session_type | String | 是 | `quick_check` 或 `baseline` |
| zone_id | Integer | 是 | 口腔分区 (1-7) |

**curl 示例:**
```bash
curl -X POST "http://localhost:8000/api/v1/upload/video" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@/path/to/your/video.mp4" \
  -F "session_type=quick_check" \
  -F "zone_id=2"
```

**响应示例:**
```json
{
  "status": "success",
  "data": {
    "session_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "video_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
    "file_hash": "a1b2c3d4e5f6...",
    "file_size": 5242880,
    "duration": 15.5,
    "session_type": "quick_check",
    "zone_id": 2,
    "processing_status": "pending",
    "uploaded_at": "2026-01-15T10:30:00"
  },
  "message": "视频上传成功，开始处理"
}
```

**处理流程说明:**

上传成功后，系统会异步执行以下流程：

```
1. 视频摄入 (pending)
   ↓
2. 关键帧提取 (processing)
   ↓
3. 帧匹配与对比 (processing)
   ↓
4. EvidencePack 构建 (processing)
   ↓
5. LLM 报告生成 (processing)
   ↓
6. 完成 (completed)
```

可以通过 [查询 Session 状态](#2-查询-session-状态) 接口获取处理进度。

---

## Session 管理 API

### 1. 列出用户的 Sessions

**GET** `/sessions`

获取当前用户的所有检查 Session 列表。

**请求头:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**查询参数:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| limit | Integer | 否 | 返回数量限制 (默认 20, 最大 100) |
| offset | Integer | 否 | 分页偏移量 (默认 0) |
| status | String | 否 | 按状态过滤: pending/processing/completed/failed |
| session_type | String | 否 | 按类型过滤: quick_check/baseline |

**响应示例:**
```json
{
  "status": "success",
  "data": {
    "total": 25,
    "limit": 20,
    "offset": 0,
    "sessions": [
      {
        "session_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        "session_type": "quick_check",
        "zone_id": 2,
        "processing_status": "completed",
        "started_at": "2026-01-15T10:30:00",
        "completed_at": "2026-01-15T10:32:15",
        "has_report": true,
        "keyframe_count": 20
      },
      {
        "session_id": "6ba7b812-9dad-11d1-80b4-00c04fd430c8",
        "session_type": "baseline",
        "zone_id": 1,
        "processing_status": "processing",
        "started_at": "2026-01-15T09:00:00",
        "completed_at": null,
        "has_report": false,
        "keyframe_count": 0
      }
    ]
  }
}
```

---

### 2. 查询 Session 状态

**GET** `/sessions/{session_id}`

获取指定 Session 的详细信息和处理状态。

**路径参数:**
- `session_id`: Session UUID

**响应示例 (处理中):**
```json
{
  "status": "success",
  "data": {
    "session_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "video_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
    "session_type": "quick_check",
    "zone_id": 2,
    "processing_status": "processing",
    "processing_stage": "keyframe_extraction",
    "progress_percent": 45,
    "started_at": "2026-01-15T10:30:00",
    "completed_at": null,
    "error_message": null
  }
}
```

**响应示例 (已完成):**
```json
{
  "status": "success",
  "data": {
    "session_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "video_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
    "session_type": "quick_check",
    "zone_id": 2,
    "processing_status": "completed",
    "started_at": "2026-01-15T10:30:00",
    "completed_at": "2026-01-15T10:32:15",
    "video_info": {
      "duration": 15.5,
      "resolution": "1920x1080",
      "file_size": 5242880
    },
    "keyframe_count": 20,
    "has_report": true,
    "has_evidence_pack": true
  }
}
```

---

### 3. 删除 Session

**DELETE** `/sessions/{session_id}`

删除指定的 Session 及其关联数据（关键帧、报告等）。

> ⚠️ **注意**: 此操作不会删除 B-Stream 中的原始视频（符合 A/B/C 架构原则）

**响应示例:**
```json
{
  "status": "success",
  "data": {
    "deleted": true,
    "session_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
  },
  "message": "Session 删除成功"
}
```

---

### 4. 获取 Evidence Pack

**GET** `/sessions/{session_id}/evidence-pack`

获取 Session 的 Evidence Pack（结构化分析数据）。

**响应示例:**
```json
{
  "status": "success",
  "data": {
    "session_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "session_type": "quick_check",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2026-01-15T10:30:00",
    "frames": [
      {
        "frame_id": "frame-001",
        "timestamp": 2.5,
        "image_url": "/data/A/keyframes/6ba7b810/0.jpg",
        "extraction_strategy": "rule_based",
        "extraction_reason": "dark_deposit,gum_issue",
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
          "days_since": 45
        }
      ],
      "active_concerns": [
        {
          "concern_type": "dark_spots",
          "display_name": "色素沉着",
          "severity": "moderate",
          "zone_id": 2,
          "days_active": 76
        }
      ],
      "days_since_last_check": 30
    }
  }
}
```

---

## 报告获取 API

### 1. 获取 Session 报告

**GET** `/sessions/{session_id}/report`

获取指定 Session 的 LLM 分析报告。

**响应示例:**
```json
{
  "status": "success",
  "data": {
    "report_id": "550e8400-e29b-41d4-a716-446655440001",
    "session_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "report_text": "## 口腔健康分析报告...",
    "llm_model": "qwen-vl-max",
    "tokens_used": 2580,
    "created_at": "2026-01-15T10:32:15"
  }
}
```

---

### 2. 获取报告文本

**GET** `/sessions/{session_id}/report/text`

直接获取报告的纯文本内容（Markdown 格式）。

**响应:**
```markdown
# 口腔健康分析报告

## 健康评分: 78/100

## 主要发现

### 1. 色素沉着
- **位置**: 上颌前牙区域
- **程度**: 轻度
- **建议**: 刚完成洁牙1.5个月，色素沉着出现较快，建议调整饮食习惯...

### 2. 牙龈状况
- **状态**: 轻微红肿
- **可能原因**: 刷牙方式不当或近期口腔卫生维护不足
...

## 个性化建议

### 立即行动
1. 减少咖啡、茶、红酒等易染色饮品的摄入
2. 使用软毛牙刷，采用巴氏刷牙法
...

### 持续关注
- 色素沉着是否有扩散趋势
- 牙龈红肿是否缓解
...

### 复查建议
建议2-3个月后进行复查，重点关注色素沉着的进展情况。

---
*报告生成时间: 2026-01-15 10:32:15*  
*AI 模型: 通义千问 Vision*
```

---

### 3. 重新生成报告

**POST** `/sessions/{session_id}/report/regenerate`

重新触发 LLM 报告生成（例如：Evidence Pack 更新后）。

**响应示例:**
```json
{
  "status": "success",
  "data": {
    "session_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "report_id": "550e8400-e29b-41d4-a716-446655440002",
    "status": "processing"
  },
  "message": "报告重新生成已启动"
}
```

---

## 用户档案 API

### 1. 获取用户档案

**GET** `/profile`

获取当前用户的完整档案信息（包含历史事件和关注点）。

**响应示例:**
```json
{
  "status": "success",
  "data": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "phone_number": "13800138000",
    "profile": {
      "nickname": "张三",
      "avatar_url": "https://example.com/avatar.jpg",
      "date_of_birth": "1990-05-15"
    },
    "checkup_stats": {
      "total_checkups": 12,
      "last_checkup_date": "2025-12-15",
      "days_since_last_checkup": 31
    },
    "events": [
      {
        "id": "event-001",
        "event_type": "dental_cleaning",
        "event_type_display": "洁牙",
        "event_date": "2025-12-01",
        "clinic_name": "美奥口腔",
        "notes": "超声波洁牙，无不适"
      }
    ],
    "concerns": [
      {
        "id": "concern-001",
        "concern_type": "dark_spots",
        "display_name": "色素沉着",
        "severity": "moderate",
        "status": "active",
        "zone_id": 2,
        "first_observed_at": "2025-11-01",
        "last_observed_at": "2025-12-15",
        "notes": "上颌前牙区域可见黄色斑点"
      }
    ]
  }
}
```

---

### 2. 更新用户档案

**PUT** `/profile`

更新用户档案信息。

**请求参数:**
```json
{
  "nickname": "张三",
  "avatar_url": "https://example.com/avatar.jpg",
  "date_of_birth": "1990-05-15"
}
```

**响应示例:**
```json
{
  "status": "success",
  "data": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "profile": {
      "nickname": "张三",
      "avatar_url": "https://example.com/avatar.jpg",
      "date_of_birth": "1990-05-15",
      "updated_at": "2026-01-15T11:00:00"
    }
  },
  "message": "档案更新成功"
}
```

---

### 3. 添加用户事件

**POST** `/profile/events`

添加口腔相关事件记录（洁牙、补牙等）。

**请求参数:**
```json
{
  "event_type": "dental_cleaning",
  "event_date": "2025-12-01",
  "dentist_name": "李医生",
  "clinic_name": "美奥口腔",
  "cost": 380.00,
  "notes": "超声波洁牙，无不适"
}
```

**事件类型:**
- `dental_cleaning` - 洁牙
- `filling` - 补牙
- `extraction` - 拔牙
- `orthodontic` - 正畸
- `whitening` - 美白
- `checkup` - 常规检查
- `other` - 其他

**响应示例:**
```json
{
  "status": "success",
  "data": {
    "event_id": "event-002",
    "event_type": "dental_cleaning",
    "event_date": "2025-12-01",
    "created_at": "2026-01-15T11:00:00"
  },
  "message": "事件添加成功"
}
```

---

### 4. 删除用户事件

**DELETE** `/profile/events/{event_id}`

删除指定的事件记录。

**响应示例:**
```json
{
  "status": "success",
  "data": {
    "deleted": true,
    "event_id": "event-002"
  },
  "message": "事件删除成功"
}
```

---

### 5. 添加关注点

**POST** `/profile/concerns`

添加口腔问题关注点。

**请求参数:**
```json
{
  "concern_type": "dark_spots",
  "severity": "moderate",
  "zone_id": 2,
  "first_observed_at": "2025-11-01",
  "notes": "上颌前牙区域可见黄色斑点"
}
```

**严重程度:**
- `mild` - 轻度
- `moderate` - 中度
- `severe` - 重度

**关注点类型:**
- `dark_spots` - 色素沉着
- `plaque_buildup` - 牙菌斑堆积
- `gum_inflammation` - 牙龈红肿
- `tooth_decay` - 龋齿
- `calculus` - 牙结石
- `sensitivity` - 敏感
- `misalignment` - 排列不齐
- `other` - 其他

**响应示例:**
```json
{
  "status": "success",
  "data": {
    "concern_id": "concern-002",
    "concern_type": "dark_spots",
    "severity": "moderate",
    "status": "active",
    "created_at": "2026-01-15T11:00:00"
  },
  "message": "关注点添加成功"
}
```

---

### 6. 更新关注点状态

**PUT** `/profile/concerns/{concern_id}`

更新关注点的状态或严重程度。

**请求参数:**
```json
{
  "severity": "mild",
  "status": "monitoring",
  "notes": "情况有所好转"
}
```

**状态类型:**
- `active` - 活跃（需要关注）
- `resolved` - 已解决
- `monitoring` - 监测中

**响应示例:**
```json
{
  "status": "success",
  "data": {
    "concern_id": "concern-001",
    "status": "monitoring",
    "updated_at": "2026-01-15T11:00:00"
  },
  "message": "关注点更新成功"
}
```

---

## 错误处理

### 常见错误码

| 错误码 | HTTP 状态 | 说明 | 处理建议 |
|--------|-----------|------|----------|
| `USER_NOT_FOUND` | 404 | 用户不存在 | 检查用户ID或重新注册 |
| `SESSION_NOT_FOUND` | 404 | Session 不存在 | 检查 Session ID |
| `VIDEO_TOO_LARGE` | 400 | 视频文件过大 | 压缩视频或分段上传 |
| `INVALID_VIDEO_FORMAT` | 400 | 视频格式不支持 | 转换为 MP4/MOV 格式 |
| `PROCESSING_FAILED` | 500 | 处理失败 | 重新上传或联系支持 |
| `LLM_API_ERROR` | 503 | LLM 服务不可用 | 稍后重试 |
| `UNAUTHORIZED` | 401 | 未授权 | 检查 JWT Token |
| `FORBIDDEN` | 403 | 权限不足 | 确认资源所有权 |
| `DUPLICATE_PHONE` | 409 | 手机号已注册 | 直接登录 |

### 错误响应示例

```json
{
  "status": "error",
  "error": {
    "code": "VIDEO_TOO_LARGE",
    "message": "视频文件大小超过限制 (100MB)",
    "details": {
      "max_size_mb": 100,
      "actual_size_mb": 156
    }
  }
}
```

---

## 完整调用流程示例

### 场景：完成一次完整的口腔检查

```bash
# 1. 用户登录获取 Token
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/users/login" \
  -H "Content-Type: application/json" \
  -d '{"phone_number":"13800138000"}' | jq -r '.data.access_token')

# 2. 上传视频
curl -X POST "http://localhost:8000/api/v1/upload/video" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@oral_video.mp4" \
  -F "session_type=quick_check" \
  -F "zone_id=2"
# 返回: {"data": {"session_id": "xxx", ...}}

SESSION_ID="xxx"

# 3. 轮询检查处理状态
while true; do
  STATUS=$(curl -s "http://localhost:8000/api/v1/sessions/$SESSION_ID" \
    -H "Authorization: Bearer $TOKEN" | jq -r '.data.processing_status')
  echo "Status: $STATUS"
  if [ "$STATUS" = "completed" ]; then
    break
  elif [ "$STATUS" = "failed" ]; then
    echo "处理失败"
    exit 1
  fi
  sleep 5
done

# 4. 获取分析报告
curl -s "http://localhost:8000/api/v1/sessions/$SESSION_ID/report/text" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 附录

### A. 口腔分区图

```
        [上颌]
    ┌───┬───┬───┐
    │ 1 │ 2 │ 3 │    1: 左上后牙  2: 上颌前牙  3: 右上后牙
    └───┴───┴───┘
    
    ┌───┬───┬───┐
    │ 4 │ 5 │ 6 │    4: 左下后牙  5: 下颌前牙  6: 右下后牙
    └───┴───┴───┘
        [下颌]
    
    ┌───────────┐
    │     7     │    7: 全口概览
    └───────────┘
```

### B. 视频拍摄建议

| 项目 | 建议 |
|------|------|
| 分辨率 | 1080p 或更高 |
| 时长 | 10-30 秒 |
| 光线 | 充足的自然光或补光 |
| 角度 | 垂直于牙齿表面 |
| 稳定性 | 保持手机稳定，避免晃动 |
| 对焦 | 确保牙齿清晰可见 |
