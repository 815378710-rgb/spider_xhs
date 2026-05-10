<p align="center">
    <img width="220" src="./author/logo.jpg" alt="土豆小红书助手 logo">
</p>

<div align="center">

# 🥔 土豆小红书助手

**小红书笔记采集 + AI 改写 + 图片防重处理 + 多账号管理 + 定时发布 一站式工具**

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/nodejs-20%2B-green)](https://nodejs.org/)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

</div>

> 基于 [cv-cat/Spider_XHS](https://github.com/cv-cat/Spider_XHS) 二次开发，v2 全栈升级版：FastAPI + React SPA + SQLite + APScheduler。

## ✨ 功能特性

### 📝 笔记改写
- 一键采集小红书笔记（标题 + 正文 + 图片）
- AI 智能改写（支持 DeepSeek / MiMo / OpenAI 兼容接口）
- 6 种改写风格：保持原风格、种草带货风、测评种草风、教程攻略风、情绪共鸣风、小红书爆款风
- 图片防重处理（3 级强度），避免平台查重

### 🔍 批量采集
- 关键词搜索笔记
- 多维度排序（综合、点赞、最新、收藏）
- 支持图文 / 视频 / 全部类型筛选
- 批量选中改写（队列式自动处理）

### 📊 多账号管理
- 多账号 Cookie 管理
- Cookie 池自动轮换
- 账号健康检查

### ⏰ 定时发布
- 一键定时发布（单次 / Cron）
- 批量发布进度追踪
- 自动图片处理 + 防重

### 🛠️ 设置
- 多 AI 模型支持（DeepSeek / MiMo / OpenAI 兼容）
- 模型自动发现
- 配置持久化（容器重启不丢失）

## 🚀 快速开始

### Docker 部署（推荐）

```bash
# 克隆项目
git clone https://github.com/815378710-rgb/potato-xhs.git
cd potato-xhs

# 构建并运行
docker build -t potato-xhs .
docker run -d --name potato-xhs --network host potato-xhs
```

访问 `http://localhost:5000`

### 本地运行

```bash
# 后端
cd backend
pip install -r ../requirements.txt
python main.py

# 前端
cd frontend
npm install
npm run dev
```

## 📁 项目结构

```
potato-xhs/
├── backend/                 # FastAPI 后端
│   ├── main.py              # 入口
│   ├── core/                # 配置、安全、数据库
│   ├── routers/             # API 路由
│   ├── models/              # SQLAlchemy 模型
│   └── services/            # 定时任务等
├── frontend/                # React SPA
│   ├── src/
│   │   ├── pages/           # 页面组件
│   │   ├── components/      # 公共组件
│   │   ├── stores/          # Zustand 状态管理
│   │   └── api/             # Axios 封装
│   └── package.json
├── apis/                    # 小红书 API 封装
├── utils/                   # 图片处理、AI改写
├── xhs_utils/               # 小红书签名工具
├── static/                  # JS 签名模块
├── config/                  # 配置文件（持久化）
├── Dockerfile               # Docker 构建文件
└── requirements.txt         # Python 依赖
```

## ⚠️ 免责声明

本项目仅供学习交流使用，禁止任何商业化行为。使用本工具产生的一切后果由使用者自行承担。

## 🙏 致谢

- [cv-cat/Spider_XHS](https://github.com/cv-cat/Spider_XHS) - 原始项目
