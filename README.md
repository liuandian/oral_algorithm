# 智能口腔健康监测系统 (Oral Health Monitor V1)

基于 A/B/C 三层数据流架构的智能口腔视频分析后端系统。

## 核心架构

- **B 数据流 (Base)**: 原始视频资产库，物理级 Write-Once（只读/不可篡改）。
- **A 数据流 (Application)**: 业务层，存储关键帧、结构化 EvidencePack 和用户档案。
- **C 数据流 (Copy)**: 训练沙盒，仅允许从 B 流复制数据（V1 接口预留）。

## 快速开始

### 1. 环境准备

确保已安装 `Python 3.10+` 和 `PostgreSQL 15+`。

```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 2. 安装依赖
pip install -r requirements.txt


#postgre账户密码
miracleliuan@gmail.com
123456