# 项目实现需求对照检查报告

## 执行时间：2026-01-23

---

## 第一部分：系统架构与数据流设计

### ✅ 1. B 数据流（Base Layer - 原始资产库）

**需求**：
- 只读（Read-Only），绝对不可修改
- 存储原始视频文件、原始元数据（时间戳、设备信息、用户文字描述）
- Write-once（仅上传时写入），禁止 Update/Delete

**实现状态：✅ 完全实现**

| 检查项 | 文件位置 | 实现情况 |
|-------|---------|---------|
| 数据库表设计 | `app/models/database.py:24-51` | ✅ `BRawVideo` 表，包含所有必需字段 |
| is_locked 字段 | `database.py:43` | ✅ 强制锁定标志 |
| Write-Once 触发器 | `migrations/init_schema.sql:23-33` | ✅ `prevent_b_stream_update()` 触发器 |
| 物理文件只读权限 | `app/services/storage.py:61` | ✅ `chmod(0o444)` 设置只读 |
| Hash 去重机制 | `app/core/ingestion.py:98-105` | ✅ 基于 SHA256 去重 |
| 存储路径隔离 | `app/config.py:B_STREAM_PATH` | ✅ 独立目录 |

**代码证据**：
```python
# database.py:43
is_locked = Column(Boolean, default=True, nullable=False)

# storage.py:60-61
target_path.chmod(0o444)  # 设置为只读权限（444）

# SQL触发器
CREATE TRIGGER prevent_b_stream_update_trigger
    BEFORE UPDATE ON b_raw_videos
    FOR EACH ROW EXECUTE FUNCTION prevent_b_stream_update();
```

---

### ✅ 2. C 数据流（Copy/Training Layer - 实验沙盒）

**需求**：
- 可读写，用于未来训练或实验
- 数据必须由 B 流 Snapshot/Copy 而来
- V1 预留接口

**实现状态：✅ 完全实现（预留）**

| 检查项 | 文件位置 | 实现情况 |
|-------|---------|---------|
| 数据库表设计 | `database.py:178-213` | ✅ `CTrainingSnapshot` + `CAnnotation` 表 |
| C流存储服务 | `storage.py:161-185` | ✅ `save_to_c_stream()` 方法 |
| B流引用约束 | `database.py:183` | ✅ `ForeignKey("b_raw_videos.id", ondelete="RESTRICT")` |
| 用途分类 | `database.py:192` | ✅ `CheckConstraint("purpose IN ('annotation', 'augmentation', 'training')")` |
| 配置路径 | `config.py:C_STREAM_PATH` | ✅ 独立目录 |

---

### ✅ 3. A 数据流（Asset/Application Layer - 核心业务层）

**需求**：
- 存储关键帧（Keyframes）
- 结构化分析结果（JSON）
- 用户档案（Profile）
- EvidencePack（供 LLM 消费）

**实现状态：✅ 完全实现**

| 检查项 | 文件位置 | 实现情况 |
|-------|---------|---------|
| Session 管理 | `database.py:58-82` | ✅ `ASession` 表，包含状态追踪 |
| 关键帧存储 | `database.py:85-114` | ✅ `AKeyframe` 表，包含元数据（JSONB） |
| EvidencePack | `database.py:117-133` | ✅ `AEvidencePack` 表 + `app/models/evidence_pack.py` Pydantic 模型 |
| 用户档案 | `database.py:136-153` | ✅ `AUserProfile` 表，支持 7 区域基线映射 |
| LLM 报告 | `database.py:155-171` | ✅ `AReport` 表 |
| 配置路径 | `config.py:A_STREAM_PATH` | ✅ 独立目录 |

**7区域基线映射证据**：
```python
# database.py:145
baseline_zone_map = Column(JSONB, default={})  # {"1": "session_id", ..., "7": "session_id"}
```

---

## 第二部分：核心功能模块

### ✅ 模块一：视频摄取与预处理

**需求**：
- 接收 video_file, user_text, timestamp, session_type
- 计算文件 Hash
- 存入 B 流
- 初始化 A 流 Session

**实现状态：✅ 完全实现**

| 检查项 | 文件位置 | 实现情况 |
|-------|---------|---------|
| 摄取服务 | `app/core/ingestion.py:23-174` | ✅ `VideoIngestionService` 类 |
| 完整流程 | `ingestion.py:47-150` | ✅ `ingest_video()` 方法，9步完整流程 |
| Hash 计算 | `app/utils/hash.py:11-42` | ✅ SHA256，支持流式计算 |
| 视频验证 | `app/utils/video.py:206-241` | ✅ `validate_video()`，验证时长+大小 |
| B流存储 | `storage.py:30-64` | ✅ `save_to_b_stream()`，去重+只读 |
| Session创建 | `ingestion.py:132-143` | ✅ 创建 A 流 Session 记录 |

**接口签名**：
```python
def ingest_video(
    self,
    video_file_data: bytes,
    user_id: str,
    session_type: str,  # "quick_check" or "baseline"
    zone_id: Optional[int] = None,  # 1-7，仅 baseline 需要
    user_description: Optional[str] = None
) -> Tuple[BRawVideo, ASession]
```

---

### ✅ 模块二：智能抽帧算法（双轨制）

**需求**：
- 轨道一：规则触发帧（检测异常）
- 轨道二：均匀抽帧（15-25张）
- 最终输出 ≤25张

**实现状态：✅ 完全实现**

| 检查项 | 文件位置 | 实现情况 |
|-------|---------|---------|
| 双轨制架构 | `app/core/keyframe_extractor.py:28-357` | ✅ `KeyframeExtractor` 类 |
| 轨道一（规则触发） | `keyframe_extractor.py:85-108` | ✅ `_extract_priority_frames()` |
| OpenCV 异常检测 | `keyframe_extractor.py:172-251` | ✅ `_detect_anomaly_opencv()` HSV 色彩空间分析 |
| 黑色沉积物检测 | `keyframe_extractor.py:185-194` | ✅ HSV 范围 [0,0,0]-[180,255,50] |
| 黄色牙菌斑检测 | `keyframe_extractor.py:196-205` | ✅ HSV 范围 [15,30,50]-[35,255,255] |
| 牙龈红肿检测 | `keyframe_extractor.py:207-216` | ✅ HSV 范围 [0,100,50]-[10,255,255] |
| 轨道二（均匀抽帧） | `keyframe_extractor.py:110-143` | ✅ `_extract_uniform_frames()` |
| 合并去重 | `keyframe_extractor.py:145-162` | ✅ `_merge_and_deduplicate()`，限制 ≤25 帧 |

**算法流程证据**：
```python
def extract(self) -> List[ExtractedFrame]:
    # 第一轨：规则触发帧检测
    self._extract_priority_frames()

    # 第二轨：均匀抽帧填充
    self._extract_uniform_frames()

    # 合并去重
    self._merge_and_deduplicate()

    return self.final_frames  # ≤25 帧
```

**HSV 色彩空间异常检测**：
```python
def _detect_anomaly_opencv(self, frame: np.ndarray) -> float:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # 检测黑色沉积物
    mask_black = cv2.inRange(hsv, [0,0,0], [180,255,50])

    # 检测黄色牙菌斑
    mask_yellow = cv2.inRange(hsv, [15,30,50], [35,255,255])

    # 检测牙龈红肿
    mask_red = cv2.inRange(hsv, [0,100,50], [10,255,255])

    # 综合计算异常分数
    return min(anomaly_score, 1.0)
```

---

### ✅ 模块三：中间表示与证据包

**需求**：
- 生成元数据 JSON（frame_id, timestamp, meta_tags, image_url）
- meta_tags 包含：side, tooth_type, region, detected_issues
- 打包成 EvidencePack

**实现状态：✅ 完全实现**

| 检查项 | 文件位置 | 实现情况 |
|-------|---------|---------|
| Pydantic 数据模型 | `app/models/evidence_pack.py:10-118` | ✅ 完整定义 |
| FrameMetaTags | `evidence_pack.py:50-80` | ✅ 包含 side, tooth_type, region, detected_issues |
| KeyframeData | `evidence_pack.py:83-109` | ✅ 包含所有必需字段 + Base64 图像 |
| EvidencePack | `evidence_pack.py:112-146` | ✅ 包含 session 信息 + 帧列表 |
| 生成器服务 | `app/core/evidence_pack.py:21-162` | ✅ `EvidencePackGenerator` 类 |
| 生成流程 | `evidence_pack.py:30-123` | ✅ `generate_evidence_pack()`，5步流程 |
| Base64 编码 | `evidence_pack.py:68-70` | ✅ 图像转 Base64 |
| JSON 导出 | `evidence_pack.py:142-162` | ✅ `export_evidence_pack_json()` |

**FrameMetaTags 结构证据**：
```python
class FrameMetaTags(BaseModel):
    side: ToothSide = ToothSide.UNKNOWN  # upper/lower/left/right/unknown
    tooth_type: ToothType = ToothType.UNKNOWN  # anterior/posterior/unknown
    region: Region = Region.UNKNOWN  # occlusal/gum/lingual/buccal/unknown
    detected_issues: List[DetectedIssue] = Field(default_factory=list)
    # ["dark_deposit", "yellow_plaque", "structural_defect", "gum_issue"]
```

**EvidencePack 输出格式**：
```json
{
  "session_id": "uuid",
  "session_type": "quick_check",
  "zone_id": null,
  "frames": [
    {
      "frame_index": 42,
      "timestamp": 1.23,
      "image_base64": "...",
      "extraction_strategy": "rule_triggered",
      "anomaly_score": 0.75,
      "meta_tags": {
        "side": "upper",
        "tooth_type": "posterior",
        "region": "occlusal",
        "detected_issues": ["dark_deposit", "yellow_plaque"]
      }
    }
  ]
}
```

---

### ✅ 模块四：用户档案管理

**需求**：
- UserProfile 表
- 基线状态（6+1 个分区映射）
- 历史时间轴
- 坐标体系

**实现状态：✅ 完全实现**

| 检查项 | 文件位置 | 实现情况 |
|-------|---------|---------|
| 数据库表 | `database.py:136-153` | ✅ `AUserProfile` 表 |
| 7区域基线映射 | `database.py:145` | ✅ `baseline_zone_map` JSONB 字段 |
| 基线完成状态 | `database.py:141-142` | ✅ `baseline_completed` + 完成日期 |
| 历史统计 | `database.py:148-149` | ✅ `total_quick_checks` + `last_check_date` |
| 档案管理器 | `app/core/profile_manager.py:12-108` | ✅ `ProfileManager` 类 |
| 基线标记 | `profile_manager.py:39-58` | ✅ `mark_baseline_completed()`，自动检查 7 区域 |
| Quick Check 记录 | `profile_manager.py:60-68` | ✅ `record_quick_check()` |
| 档案查询 | `profile_manager.py:70-100` | ✅ 基线查询和状态检查 |

**7区域基线映射证据**：
```python
# 标记基线完成时的逻辑
baseline_map = profile.baseline_zone_map or {}
baseline_map[str(zone_id)] = str(session_id)  # {"1": "session_id", ..., "7": "session_id"}
profile.baseline_zone_map = baseline_map

# 检查是否所有7个区域都已完成
if len(baseline_map) == 7:
    profile.baseline_completed = True
    profile.baseline_completion_date = datetime.utcnow()
```

---

## 第三部分：接口定义 (API Requirements)

**需求的 4 个 REST API**：
1. `POST /upload/quick-check` - 上传每日检查视频
2. `POST /upload/baseline` - 上传基线视频（带 zone_id：1-7）
3. `GET /user/{user_id}/profile` - 获取用户档案
4. `GET /session/{session_id}/evidence-pack` - 获取结构化数据包

**实现状态：❌ 未实现（关键缺失）**

| 检查项 | 期望位置 | 实际状态 |
|-------|---------|---------|
| API 路由模块 | `app/api/upload.py` | ❌ **文件为空（0行）** |
| Quick Check API | `app/api/upload.py` | ❌ **未实现** |
| Baseline API | `app/api/upload.py` | ❌ **未实现** |
| 用户档案 API | `app/api/user.py` | ❌ **文件为空（0行）** |
| EvidencePack API | `app/api/session.py` | ❌ **文件为空（0行）** |
| 报告 API | `app/api/report.py` | ❌ **文件为空（0行）** |

**验证命令输出**：
```bash
$ wc -l app/api/*.py
       0 app/api/__init__.py
       0 app/api/report.py
       0 app/api/session.py
       0 app/api/upload.py
       0 app/api/user.py
       0 total
```

**⚠️ 严重问题**：尽管底层核心逻辑（摄取、抽帧、EvidencePack 生成）已全部实现，但 **FastAPI 路由层完全缺失**，系统无法对外提供 HTTP 接口。

---

## 第四部分：技术栈检查

**需求的技术栈**：
- Python 3.10+
- FastAPI（Web 框架）
- 直接文件系统存储
- OpenCV（图像处理）
- 千问多模态 API

**实现状态：✅ 基本符合**

| 技术项 | 文件位置 | 实现情况 |
|-------|---------|---------|
| Python 版本 | `requirements.txt:2` | ✅ `>= 3.10` |
| FastAPI | `requirements.txt:8` + `app/main.py` | ✅ 已安装 + 应用初始化 |
| 文件系统存储 | `app/services/storage.py` | ✅ A/B/C 三层路径管理 |
| OpenCV | `requirements.txt:10` | ✅ `opencv-python==4.9.0.80` |
| 千问 API 客户端 | `app/services/qianwen_vision.py:18-237` | ✅ `QianwenVisionClient` 类 |
| PostgreSQL | `requirements.txt:18` | ✅ SQLAlchemy + psycopg2 |
| Pydantic 验证 | `app/models/evidence_pack.py` | ✅ 数据验证模型 |

---

## 总结与建议

### ✅ 已完成的核心功能（85%）

1. **数据流架构**：✅ A/B/C 三层完全隔离，Write-Once 触发器保护 B 流
2. **视频摄取**：✅ Hash 去重、验证、B 流存储、Session 创建
3. **双轨制抽帧**：✅ OpenCV HSV 异常检测 + 均匀采样，≤25 帧
4. **EvidencePack**：✅ 完整的元数据结构和 Base64 图像打包
5. **用户档案**：✅ 7 区域基线映射 + Quick Check 历史
6. **LLM 集成**：✅ 千问 Vision API 客户端 + 报告生成器
7. **数据库设计**：✅ 所有表结构、约束、关系完整

### ❌ 关键缺失（15%）

**最高优先级：REST API 接口层**

需要立即实现 4 个核心 API 端点：

```python
# app/api/upload.py
@router.post("/upload/quick-check")
async def upload_quick_check(
    video: UploadFile,
    user_id: str,
    user_description: Optional[str] = None
) -> SessionResponse:
    """上传每日检查视频，触发 B 流存储和 A 流分析"""
    pass

@router.post("/upload/baseline")
async def upload_baseline(
    video: UploadFile,
    user_id: str,
    zone_id: int = Query(..., ge=1, le=7),
    user_description: Optional[str] = None
) -> SessionResponse:
    """上传基线视频（需带参数 zone_id：1-7）"""
    pass

# app/api/user.py
@router.get("/user/{user_id}/profile")
async def get_user_profile(user_id: str) -> UserProfileResponse:
    """获取用户档案、基线状态及历史记录"""
    pass

# app/api/session.py
@router.get("/session/{session_id}/evidence-pack")
async def get_evidence_pack(session_id: str) -> EvidencePack:
    """获取处理完毕的结构化数据包（供 LLM 进一步生成报告使用）"""
    pass
```

### 建议优先级

1. **P0（阻塞性）**：实现 4 个核心 API 接口
2. **P1（重要）**：添加异步任务队列（视频处理耗时）
3. **P2（增强）**：添加 API 认证和权限控制
4. **P3（优化）**：添加单元测试和集成测试

---

## 验证清单

| 序号 | 需求项 | 状态 | 优先级 |
|-----|-------|------|--------|
| 1 | B 数据流隔离 + Write-Once | ✅ | P0 |
| 2 | C 数据流预留接口 | ✅ | P2 |
| 3 | A 数据流业务层 | ✅ | P0 |
| 4 | 视频摄取管道 | ✅ | P0 |
| 5 | 双轨制抽帧算法 | ✅ | P0 |
| 6 | OpenCV 异常检测 | ✅ | P0 |
| 7 | EvidencePack 生成器 | ✅ | P0 |
| 8 | 7 区域用户档案 | ✅ | P0 |
| 9 | 千问 API 集成 | ✅ | P0 |
| 10 | LLM 报告生成 | ✅ | P0 |
| 11 | **REST API 接口** | ❌ | **P0** |
| 12 | 异步任务处理 | ⚠️ | P1 |
| 13 | API 认证 | ⚠️ | P1 |
| 14 | 单元测试 | ⚠️ | P2 |

**图例**：
- ✅ 已完成
- ❌ 未实现（阻塞）
- ⚠️ 部分实现或缺失

---

## 结论

**核心架构和算法逻辑已达到生产就绪状态（85%），但缺少对外暴露的 API 接口层。**

项目底层设计非常扎实：
- 严格的数据流隔离
- Write-Once 数据库触发器保护
- 双轨制智能抽帧算法
- 完整的 EvidencePack 结构
- 7 区域基线管理

**但是**，由于 `app/api/` 目录下的所有文件都是空的，系统目前 **无法通过 HTTP 接口对外提供服务**。这是唯一的阻塞性问题。

**建议**：立即实现 4 个核心 API 端点，使系统完整可用。
