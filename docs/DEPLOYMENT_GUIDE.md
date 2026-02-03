# 智能口腔健康监测系统 - 部署与配置指南

> 版本: V1.0  
> 更新日期: 2026-02-03

---

## 目录

1. [环境要求](#环境要求)
2. [快速开始](#快速开始)
3. [详细安装步骤](#详细安装步骤)
4. [数据库配置](#数据库配置)
5. [环境变量配置](#环境变量配置)
6. [API Key 获取与配置](#api-key-获取与配置)
7. [启动服务](#启动服务)
8. [Docker 部署](#docker-部署)
9. [生产环境配置](#生产环境配置)
10. [常见问题排查](#常见问题排查)

---

## 环境要求

### 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|---------|---------|
| CPU | 2 核心 | 4 核心 |
| 内存 | 4 GB | 8 GB |
| 磁盘 | 50 GB | 100 GB+ |
| 操作系统 | Ubuntu 20.04 / macOS 12+ / Windows 10+ | Ubuntu 22.04 LTS |

### 软件依赖

| 软件 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 编程语言运行时 |
| PostgreSQL | 15+ | 关系型数据库 |
| FFmpeg | 4.4+ | 视频处理工具 |
| Git | 2.30+ | 版本控制 |

---

## 快速开始

如果你已经熟悉环境配置，可以使用以下快速启动命令：

```bash
# 1. 克隆仓库
git clone <repository-url>
cd oral_algorithm

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或: venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入数据库密码和 API Key

# 5. 创建数据库
createdb oral_health_db  # 需要先安装 PostgreSQL

# 6. 运行迁移
alembic upgrade head

# 7. 启动服务
uvicorn app.main:app --reload
```

服务将在 `http://localhost:8000` 启动。

---

## 详细安装步骤

### 1. 安装 Python 3.10+

#### Ubuntu/Debian

```bash
# 添加 deadsnakes PPA
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update

# 安装 Python 3.10
sudo apt install -y python3.10 python3.10-venv python3.10-dev python3-pip

# 验证安装
python3.10 --version
```

#### macOS

```bash
# 使用 Homebrew 安装
brew install python@3.10

# 验证安装
python3.10 --version
```

#### Windows

1. 访问 [Python 官网](https://www.python.org/downloads/)
2. 下载 Python 3.10+ 安装程序
3. 安装时勾选 "Add Python to PATH"

---

### 2. 安装 PostgreSQL 15+

#### Ubuntu/Debian

```bash
# 添加 PostgreSQL 官方仓库
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt update

# 安装 PostgreSQL
sudo apt install -y postgresql-15 postgresql-contrib-15

# 启动服务
sudo systemctl enable postgresql
sudo systemctl start postgresql

# 验证安装
psql --version
```

#### macOS

```bash
# 使用 Homebrew 安装
brew install postgresql@15

# 启动服务
brew services start postgresql@15

# 验证安装
psql --version
```

#### Windows

1. 访问 [PostgreSQL 官网](https://www.postgresql.org/download/windows/)
2. 下载安装程序并运行
3. 记住安装时设置的密码

---

### 3. 安装 FFmpeg

#### Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y ffmpeg
ffmpeg -version
```

#### macOS

```bash
brew install ffmpeg
ffmpeg -version
```

#### Windows

1. 访问 [FFmpeg 官网](https://ffmpeg.org/download.html)
2. 下载 Windows build
3. 解压并添加到系统 PATH

---

## 数据库配置

### 1. 创建数据库

#### Linux/macOS

```bash
# 切换到 postgres 用户
sudo -u postgres psql

# 在 psql 命令行中执行:
CREATE DATABASE oral_health_db;
CREATE USER oraluser WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE oral_health_db TO oraluser;
\q
```

#### Windows

```cmd
# 打开 SQL Shell (psql)
# 输入安装时设置的密码

CREATE DATABASE oral_health_db;
CREATE USER oraluser WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE oral_health_db TO oraluser;
\q
```

### 2. 验证数据库连接

```bash
# 使用新用户连接
psql -U oraluser -d oral_health_db -h localhost -W
# 输入密码

# 测试连接
\conninfo
\q
```

### 3. 数据库迁移

项目使用 Alembic 进行数据库迁移管理。

```bash
# 确保在项目根目录
cd /path/to/oral_algorithm

# 激活虚拟环境
source venv/bin/activate

# 运行迁移（创建所有表）
alembic upgrade head

# 查看当前版本
alembic current

# 如需回滚（谨慎操作）
# alembic downgrade -1
```

### 4. 数据库结构

迁移完成后，数据库将包含以下表：

| 表名 | 说明 |
|------|------|
| `auser` | 用户基础信息 |
| `aprofile` | 用户档案详情 |
| `bvideo` | 原始视频元数据 |
| `asession` | 检查会话 |
| `akeyframe` | 关键帧信息 |
| `aevidencepack` | 证据包数据 |
| `areport` | 分析报告 |
| `auserevent` | 用户就诊事件 |
| `aconcernpoint` | 用户关注点 |
| `asetting` | 用户设置 |

---

## 环境变量配置

### 1. 创建 .env 文件

```bash
# 复制示例文件
cp .env.example .env

# 编辑配置文件
nano .env  # 或使用你喜欢的编辑器
```

### 2. 配置项详解

#### 应用设置

```env
# 应用名称和版本
APP_NAME=OralHealthMonitor
APP_VERSION=1.0.0

# 调试模式 (开发设为 true，生产设为 false)
DEBUG=false

# API 前缀
API_PREFIX=/api/v1
```

#### 数据库配置

```env
# PostgreSQL 连接配置
DB_HOST=localhost
DB_PORT=5432
DB_USER=oraluser
DB_PASSWORD=your_secure_password  # 替换为你设置的密码
DB_NAME=oral_health_db
```

#### 数据存储路径

```env
# 数据根目录（留空使用默认的 ./data）
DATA_ROOT=

# 如需自定义存储路径:
# DATA_ROOT=/mnt/storage/oral_health_data
```

#### 视频处理参数

```env
# 视频大小限制 (MB)
MAX_VIDEO_SIZE_MB=100

# 视频时长限制 (秒)
MAX_VIDEO_DURATION_SEC=30

# 关键帧数量限制
MAX_KEYFRAMES=25
MIN_KEYFRAMES=5

# 均匀采样帧数
UNIFORM_SAMPLE_COUNT=20

# 优先帧阈值 (异常分数高于此值的帧优先保留)
PRIORITY_FRAME_THRESHOLD=0.5

# 关键帧质量 (JPEG 质量 1-100)
KEYFRAME_QUALITY=85
```

#### LLM 服务配置

```env
# 通义千问 API Key (必填)
# 获取方式见下方 "API Key 获取与配置" 章节
QIANWEN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 模型设置
QIANWEN_VISION_MODEL=qwen-vl-max
QIANWEN_TEXT_MODEL=qwen-max
QIANWEN_API_BASE=https://dashscope.aliyuncs.com/api/v1

# API 客户端设置
QIANWEN_TIMEOUT=30
QIANWEN_MAX_RETRIES=3
```

#### 安全配置

```env
# JWT 密钥 (生产环境必须修改！)
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# CORS 设置 (开发可用 *，生产需指定域名)
CORS_ORIGINS=*
# 生产示例: CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# 日志级别 (DEBUG/INFO/WARNING/ERROR)
LOG_LEVEL=INFO
```

### 3. 完整 .env 示例

```env
# ========================================
# Oral Health Monitoring System - Environment Config
# ========================================

# Application
APP_NAME=OralHealthMonitor
APP_VERSION=1.0.0
DEBUG=false
API_PREFIX=/api/v1

# Database
DB_HOST=localhost
DB_PORT=5432
DB_USER=oraluser
DB_PASSWORD=YourStrongPassword123!
DB_NAME=oral_health_db

# Storage
DATA_ROOT=

# Video Processing
MAX_VIDEO_SIZE_MB=100
MAX_VIDEO_DURATION_SEC=30
MAX_KEYFRAMES=25
MIN_KEYFRAMES=5
UNIFORM_SAMPLE_COUNT=20
PRIORITY_FRAME_THRESHOLD=0.5
KEYFRAME_QUALITY=85

# LLM Service
QIANWEN_API_KEY=sk-your-actual-api-key-here
QIANWEN_VISION_MODEL=qwen-vl-max
QIANWEN_TEXT_MODEL=qwen-max
QIANWEN_API_BASE=https://dashscope.aliyuncs.com/api/v1
QIANWEN_TIMEOUT=30
QIANWEN_MAX_RETRIES=3

# Security
JWT_SECRET_KEY=change-this-to-a-random-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# CORS
CORS_ORIGINS=*

# Logging
LOG_LEVEL=INFO
```

---

## API Key 获取与配置

### 1. 注册阿里云账号

1. 访问 [阿里云官网](https://www.aliyun.com/)
2. 点击右上角 "免费注册"
3. 完成实名认证（个人或企业）

### 2. 开通 DashScope 服务

1. 访问 [DashScope 控制台](https://dashscope.console.aliyun.com/)
2. 点击 "开通服务"
3. 同意服务协议

### 3. 创建 API Key

1. 在 DashScope 控制台，点击左侧 "API-KEY 管理"
2. 点击 "创建新的 API-KEY"
3. 输入名称（如：oral-health-monitor）
4. 点击确定
5. **立即复制显示的 API Key**（只显示一次！）

### 4. 配置到项目

将复制的 API Key 填入 `.env` 文件：

```env
QIANWEN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 5. 验证 API Key

```bash
# 激活虚拟环境
source venv/bin/activate

# 测试 API 连接
python -c "
from app.services.qianwen_vision import QianwenVisionClient
from app.config import settings

client = QianwenVisionClient(api_key=settings.QIANWEN_API_KEY)
print('API Key 配置成功！')
"
```

### 6. 费用说明

通义千问 Vision 模型按 Token 计费，大致价格：

| 模型 | 输入 | 输出 |
|------|------|------|
| qwen-vl-max | ~0.003元/千tokens | ~0.006元/千tokens |

单次分析报告约消耗 2000-3000 tokens，成本约 0.02-0.03 元。

---

## 启动服务

### 开发模式

```bash
# 确保在项目根目录
cd /path/to/oral_algorithm

# 激活虚拟环境
source venv/bin/activate

# 启动开发服务器 (带热重载)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000/docs 查看自动生成的 API 文档。

### 生产模式

```bash
# 使用 Gunicorn + Uvicorn 工作进程
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

参数说明：
- `-w 4`: 4 个工作进程（根据 CPU 核心数调整）
- `-k uvicorn.workers.UvicornWorker`: 使用 Uvicorn worker

### 后台运行 (Linux)

```bash
# 使用 nohup
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &

# 或使用 systemd (推荐)
# 见下方 "生产环境配置" 章节
```

---

## Docker 部署

### 1. 使用 Docker Compose (推荐)

项目已包含 `docker-compose.yml` 文件：

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: oraluser
      POSTGRES_PASSWORD: yourpassword
      POSTGRES_DB: oral_health_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  app:
    build: .
    environment:
      - DB_HOST=db
      - DB_PORT=5432
      - DB_USER=oraluser
      - DB_PASSWORD=yourpassword
      - DB_NAME=oral_health_db
      - QIANWEN_API_KEY=${QIANWEN_API_KEY}
    ports:
      - "8000:8000"
    depends_on:
      - db
    volumes:
      - ./data:/app/data

volumes:
  postgres_data:
```

### 2. 构建并启动

```bash
# 确保已配置 .env 文件
export QIANWEN_API_KEY=your-api-key

# 构建并启动
docker-compose up --build -d

# 查看日志
docker-compose logs -f app

# 停止服务
docker-compose down

# 停止并删除数据卷（谨慎操作）
docker-compose down -v
```

---

## 生产环境配置

### 1. 使用 Systemd 管理服务

创建服务文件 `/etc/systemd/system/oral-health.service`：

```ini
[Unit]
Description=Oral Health Monitoring System
After=network.target postgresql.service

[Service]
Type=simple
User=oraluser
Group=oraluser
WorkingDirectory=/opt/oral_algorithm
Environment="PATH=/opt/oral_algorithm/venv/bin"
EnvironmentFile=/opt/oral_algorithm/.env
ExecStart=/opt/oral_algorithm/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用并启动服务：

```bash
# 重载 systemd
sudo systemctl daemon-reload

# 启用开机自启
sudo systemctl enable oral-health

# 启动服务
sudo systemctl start oral-health

# 查看状态
sudo systemctl status oral-health

# 查看日志
sudo journalctl -u oral-health -f
```

### 2. 使用 Nginx 反向代理

安装 Nginx：

```bash
sudo apt install -y nginx
```

创建配置文件 `/etc/nginx/sites-available/oral-health`：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # 静态文件（如有需要）
    location /static {
        alias /opt/oral_algorithm/static;
        expires 30d;
    }

    # 上传文件大小限制
    client_max_body_size 150M;
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/oral-health /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 3. HTTPS 配置 (Let's Encrypt)

```bash
# 安装 Certbot
sudo apt install -y certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期测试
sudo certbot renew --dry-run
```

### 4. 生产环境 .env 调整

```env
# 关闭调试模式
DEBUG=false

# 强密码
JWT_SECRET_KEY=use-a-randomly-generated-32-char-secret

# 限制 CORS
CORS_ORIGINS=https://your-domain.com

# 错误日志级别
LOG_LEVEL=WARNING
```

---

## 常见问题排查

### 1. 数据库连接失败

**问题现象:**
```
sqlalchemy.exc.OperationalError: could not connect to server: Connection refused
```

**解决方案:**
```bash
# 检查 PostgreSQL 服务状态
sudo systemctl status postgresql

# 如果没运行，启动它
sudo systemctl start postgresql

# 检查监听配置
sudo nano /etc/postgresql/15/main/postgresql.conf
# 确保: listen_addresses = 'localhost'

# 检查认证配置
sudo nano /etc/postgresql/15/main/pg_hba.conf
# 确保有: host all all 127.0.0.1/32 md5

# 重启 PostgreSQL
sudo systemctl restart postgresql
```

### 2. 迁移失败

**问题现象:**
```
alembic.util.exc.CommandError: Can't locate revision identified by 'xxx'
```

**解决方案:**
```bash
# 重置迁移（会丢失数据，谨慎操作）
alembic downgrade base
alembic upgrade head

# 或者创建新的迁移
alembic revision --autogenerate -m "fix migration"
alembic upgrade head
```

### 3. API Key 无效

**问题现象:**
```
Error: 401 Authentication failed
```

**解决方案:**
```bash
# 1. 检查 .env 文件中的 API Key
cat .env | grep QIANWEN_API_KEY

# 2. 确认 Key 格式正确（以 sk- 开头）
# 3. 检查 Key 是否有余额
# 4. 重新生成 Key 并更新
```

### 4. 视频上传失败

**问题现象:**
```
Error: Video processing failed
```

**解决方案:**
```bash
# 检查 FFmpeg 是否安装
ffmpeg -version

# 检查数据目录权限
ls -la data/
sudo chown -R $USER:$USER data/

# 检查视频格式
ffprobe -v error your-video.mp4

# 检查磁盘空间
df -h
```

### 5. 端口被占用

**问题现象:**
```
Error: [Errno 98] Address already in use
```

**解决方案:**
```bash
# 查找占用 8000 端口的进程
lsof -i :8000

# 或 netstat
netstat -tulpn | grep 8000

# 结束进程
kill -9 <PID>

# 或使用其他端口
uvicorn app.main:app --port 8001
```

### 6. 权限问题

**问题现象:**
```
PermissionError: [Errno 13] Permission denied: 'data/B/videos/'
```

**解决方案:**
```bash
# 创建数据目录并设置权限
mkdir -p data/B/videos data/A/keyframes data/A/evidence data/A/reports
chmod -R 755 data/

# 如果运行服务的用户不同
sudo chown -R service-user:service-user data/
```

---

## 附录

### A. 环境检查脚本

创建 `check_env.py`：

```python
#!/usr/bin/env python3
"""环境检查脚本"""

import sys
import subprocess

def check_python():
    print(f"Python版本: {sys.version}")
    assert sys.version_info >= (3, 10), "需要 Python 3.10+"
    print("✅ Python 版本检查通过")

def check_postgres():
    try:
        result = subprocess.run(['psql', '--version'], capture_output=True, text=True)
        print(f"PostgreSQL: {result.stdout.strip()}")
        print("✅ PostgreSQL 已安装")
    except FileNotFoundError:
        print("❌ PostgreSQL 未安装")

def check_ffmpeg():
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        version = result.stdout.split('\n')[0]
        print(f"FFmpeg: {version}")
        print("✅ FFmpeg 已安装")
    except FileNotFoundError:
        print("❌ FFmpeg 未安装")

def check_env():
    from pathlib import Path
    env_file = Path('.env')
    if env_file.exists():
        print("✅ .env 文件存在")
        content = env_file.read_text()
        if 'your-' in content or 'change-this' in content:
            print("⚠️  .env 文件包含默认值，请修改")
        else:
            print("✅ .env 文件已配置")
    else:
        print("❌ .env 文件不存在")

if __name__ == '__main__':
    print("=" * 50)
    print("智能口腔健康监测系统 - 环境检查")
    print("=" * 50)
    
    check_python()
    check_postgres()
    check_ffmpeg()
    check_env()
    
    print("=" * 50)
```

运行检查：
```bash
python check_env.py
```

### B. 数据库备份脚本

```bash
#!/bin/bash
# backup_db.sh

BACKUP_DIR="/backup/oral_health_db"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="oral_health_db"
DB_USER="oraluser"

mkdir -p $BACKUP_DIR

# 执行备份
pg_dump -U $DB_USER -d $DB_NAME | gzip > $BACKUP_DIR/backup_$DATE.sql.gz

# 保留最近 30 天的备份
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete

echo "备份完成: backup_$DATE.sql.gz"
```

添加到 crontab：
```bash
# 每天凌晨 2 点备份
0 2 * * * /path/to/backup_db.sh >> /var/log/db_backup.log 2>&1
```
