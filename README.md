<p align="center">
    <img width="220" src="./author/logo.jpg" alt="Spider_XHS logo">
</p>

<div align="center">

# 🥔 土豆小红书助手 (Spider_XHS Fork)

**小红书笔记采集 + AI 改写 + 图片防重处理 一站式工具**

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/nodejs-20%2B-green)](https://nodejs.org/)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

</div>

> 基于 [cv-cat/Spider_XHS](https://github.com/cv-cat/Spider_XHS) 二次开发，增加了完整的 Web UI、AI 改写、图片防重处理等功能。

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

### 📊 Cookie 管理
- 扫码登录自动获取 Cookie
- 手机验证码登录
- Cookie 池管理（自动验证、清理失效、轮换使用）

### 🛠️ 设置
- 多 AI 模型支持（DeepSeek / MiMo / OpenAI 兼容）
- 模型自动发现
- 配置持久化（容器重启不丢失）

## 🚀 快速开始

### Docker 部署（推荐）

```bash
# 克隆项目
git clone https://github.com/815378710-rgb/Spider_XHS.git
cd Spider_XHS

# 配置
cp web/.env.example web/.env
# 编辑 web/.env 填入你的 AI API Key

# 构建并运行
docker build -t spider-xhs .
docker run -d --name spider-xhs --network host -v $(pwd)/config:/app/config spider-xhs
```

访问 `http://localhost:5000`

### 本地运行

```bash
# 安装依赖
pip install -r requirements.txt
npm install

# 配置
cp web/.env.example web/.env
# 编辑 web/.env

# 启动
python web/app.py
```

## 📁 项目结构

```
Spider_XHS/
├── apis/                    # 小红书 API 封装
│   ├── xhs_pc_apis.py       # PC 端 API（采集、搜索等）
│   ├── xhs_pc_login_apis.py # 登录 API（扫码、手机验证码）
│   ├── xhs_creator_apis.py  # 创作者平台 API
│   └── xhs_qianfan_apis.py  # 千帆分销 API
├── web/                     # Web 应用
│   ├── app.py               # Flask 主应用
│   ├── templates/index.html # 前端 SPA
│   └── api/                 # API 蓝图模块
├── utils/                   # 工具模块
│   ├── rewrite.py           # AI 改写引擎
│   └── image_processor.py   # 图片防重处理
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
