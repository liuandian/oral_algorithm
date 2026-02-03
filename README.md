# 智能口腔健康监测系统 (Oral Health Monitor V1)

基于 A/B/C 三层数据流架构的智能口腔视频分析后端系统。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 🏗️ 核心架构

系统采用 A/B/C 三层数据流架构，确保数据安全性和可追溯性：

| 数据流 | 用途 | 特性 | 路径 |
|--------|------|------|------|
| **B-Stream** | 原始视频资产库 | Write-Once（只读/不可篡改） | `./data/B/` |
| **A-Stream** | 业务数据层 | 可读写，支持更新 | `./data/A/` |
| **C-Stream** | 训练沙盒 | 预留，用于模型训练 | `./data/C/` |

### 系统流程

```
用户上传视频 → 视频摄入 → 关键帧提取 → 帧匹配 → 
EvidencePack 构建 → LLM 分析 → 生成报告
```

---

## ✨ 核心功能

- 📹 **视频采集与存储** - 安全存储原始口腔视频（B-Stream）
- 🎯 **智能关键帧提取** - 双轨提取策略（规则+随机），最多 25 帧
- 🔍 **帧匹配与对比** - 与基线数据进行对比分析
- 🤖 **LLM 智能分析** - 基于通义千问 Vision 生成专业报告
- 📊 **用户档案管理** - 追踪历史检查记录、就诊事件和关注点
- 📈 **趋势分析** - 结合时间线提供个性化健康建议

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- PostgreSQL 15+
- FFmpeg 4.4+

### 1. 克隆项目

```bash
git clone <repository-url>
cd oral_algorithm
```

### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或: venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，配置数据库密码和 API Key
```

### 5. 创建数据库

```bash
# 创建数据库和用户
sudo -u postgres psql -c "CREATE DATABASE oral_health_db;"
sudo -u postgres psql -c "CREATE USER oraluser WITH PASSWORD 'yourpassword';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE oral_health_db TO oraluser;"
```

### 6. 运行数据库迁移

```bash
alembic upgrade head
```

### 7. 启动服务

```bash
uvicorn app.main:app --reload
```

服务将在 `http://localhost:8000` 启动，访问 `/docs` 查看 API 文档。

---

## 📚 文档

| 文档 | 说明 |
|------|------|
| [技术架构文档](docs/TECHNICAL_ARCHITECTURE.md) | 系统架构、数据流、数据库设计 |
| [API 使用指南](docs/API_GUIDE.md) | 完整的 API 接口文档和调用示例 |
| [部署配置指南](docs/DEPLOYMENT_GUIDE.md) | 详细部署步骤、环境配置、生产部署 |
| [EvidencePack Schema](docs/EVIDENCEPACK_SCHEMA.md) | EvidencePack 结构、数据模型、JSON Schema |

---

## 🔧 配置说明

### 环境变量 (.env)

```env
# 数据库配置
DB_HOST=localhost
DB_PORT=5432
DB_USER=oraluser
DB_PASSWORD=yourpassword
DB_NAME=oral_health_db

# 千问 API Key（必填）
# 从 https://dashscope.console.aliyun.com/ 获取
QIANWEN_API_KEY=sk-your-api-key-here

# JWT 密钥（生产环境请修改）
JWT_SECRET_KEY=your-secret-key

# 其他配置...
```

### 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_VIDEO_SIZE_MB` | 100 | 最大视频文件大小 |
| `MAX_VIDEO_DURATION_SEC` | 30 | 最大视频时长 |
| `MAX_KEYFRAMES` | 25 | 最大关键帧数量 |
| `PRIORITY_FRAME_THRESHOLD` | 0.5 | 优先帧异常分数阈值 |

---

## 📡 API 概览

### 主要端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/users/register` | POST | 用户注册 |
| `/users/login` | POST | 用户登录 |
| `/upload/video` | POST | 上传视频 |
| `/sessions` | GET | 列出 Sessions |
| `/sessions/{id}` | GET | 查询 Session 状态 |
| `/sessions/{id}/report` | GET | 获取分析报告 |
| `/profile` | GET/PUT | 用户档案管理 |
| `/profile/events` | POST | 添加就诊事件 |
| `/profile/concerns` | POST | 添加关注点 |

更多详情见 [API 使用指南](docs/API_GUIDE.md)。

---

## 🐳 Docker 部署

```bash
# 配置环境变量
export QIANWEN_API_KEY=your-api-key

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

---

## 🏭 生产部署

生产环境建议使用：
- **进程管理**: Systemd 或 Supervisor
- **反向代理**: Nginx
- **HTTPS**: Let's Encrypt 证书
- **数据库**: 独立 PostgreSQL 服务器
- **监控**: 日志轮转和性能监控

详细步骤见 [部署配置指南](docs/DEPLOYMENT_GUIDE.md)。

---

## 📁 项目结构

```
oral_algorithm/
├── app/                    # 应用代码
│   ├── api/               # API 路由
│   ├── core/              # 核心逻辑
│   │   ├── ingestion.py       # 视频摄入
│   │   ├── keyframe_extractor.py  # 关键帧提取
│   │   ├── frame_matcher.py     # 帧匹配
│   │   ├── evidence_pack.py     # EvidencePack 生成
│   │   ├── llm_client.py        # LLM 客户端
│   │   └── llm_prompt_builder.py # Prompt 构建器
│   ├── models/            # 数据模型
│   ├── services/          # 外部服务
│   └── utils/             # 工具函数
├── data/                  # A/B/C 数据流存储
│   ├── A/                 # 应用层数据
│   ├── B/                 # 基础层数据（原始视频）
│   └── C/                 # 训练层数据（预留）
├── docs/                  # 文档
├── migrations/            # 数据库迁移
├── tests/                 # 测试代码
├── .env.example           # 环境变量示例
├── docker-compose.yml     # Docker 配置
└── requirements.txt       # Python 依赖
```

---

## 🧪 开发

### 运行测试

```bash
pytest tests/ -v
```

### 代码格式

```bash
# 使用 ruff 格式化
ruff format app/

# 使用 ruff 检查
ruff check app/
```

### 数据库迁移

```bash
# 创建新迁移
alembic revision --autogenerate -m "description"

# 应用迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

---

## 🤝 贡献

1. Fork 项目
2. 创建分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 💬 支持

如有问题，请：

1. 查阅 [文档](docs/)
2. 提交 [Issue](../../issues)
3. 联系维护团队

---

## 🙏 致谢

- [FastAPI](https://fastapi.tiangolo.com/) - Web 框架
- [SQLAlchemy](https://www.sqlalchemy.org/) - ORM
- [OpenCV](https://opencv.org/) - 计算机视觉
- [阿里云 DashScope](https://dashscope.aliyun.com/) - LLM 服务
