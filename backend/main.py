"""
土豆小红书助手 - FastAPI Backend
"""
import os
import sys

# Ensure backend package is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Also add parent Spider_XHS dir so routers can import apis/, xhs_utils/, utils/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from loguru import logger

from core.config import settings
from core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("🚀 土豆小红书助手 backend starting...")
    # Initialize database
    await init_db()
    logger.info("✅ Database initialized")
    # Start scheduler
    from services.scheduler import start_scheduler
    await start_scheduler()
    logger.info("✅ Scheduler started")
    yield
    # Shutdown
    from services.scheduler import stop_scheduler
    await stop_scheduler()
    logger.info("🛑 土豆小红书助手 backend stopped")


app = FastAPI(
    title="土豆小红书助手 API",
    description="土豆小红书助手 API",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS - allow all origins for dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ──────────────────────────────────────────────────────────
from routers import (
    auth, config, login, accounts, cookies,
    collect, search, content, drafts, rewrite, images,
    publish, automation, monitor, analytics,
    kol, qianfan, anti_crawl, proxy, tasks, notifications,
    quick_work,
)

router_prefix_map = [
    (auth.router,          "/api/auth",          "认证"),
    (config.router,        "/api/config",        "配置"),
    (login.router,         "/api/login",         "登录"),
    (accounts.router,      "/api/accounts",      "账号管理"),
    (cookies.router,       "/api/cookie/pool",   "Cookie池"),
    (collect.router,       "/api/note",          "笔记采集"),
    (search.router,        "/api/search",        "搜索"),
    (content.router,       "/api/content",       "内容素材库"),
    (drafts.router,        "/api/drafts",        "草稿工作台"),
    (rewrite.router,       "/api/note",          "AI改写"),
    (images.router,        "/api/images",        "图片处理"),
    (publish.router,       "/api/publish",       "发布中心"),
    (automation.router,    "/api/automation",    "自动化流水线"),
    (monitor.router,       "/api/monitor",       "竞品监控"),
    (analytics.router,     "/api/analytics",     "数据洞察"),
    (kol.router,           "/api/kol",           "KOL搜索"),
    (qianfan.router,       "/api/qianfan",       "千帆分销"),
    (anti_crawl.router,    "/api/anti-crawl",    "反爬配置"),
    (proxy.router,         "/api/proxy",         "浏览器代理"),
    (tasks.router,         "/api/tasks",         "任务中心"),
    (notifications.router, "/api/notifications",  "通知系统"),
    (quick_work.router,    "/api/quick-work",     "一站式工作台"),
]

for router, prefix, tag in router_prefix_map:
    app.include_router(router, prefix=prefix, tags=[tag])


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


# ── Serve frontend (built React app) ─────────────────────────────────────────
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve React SPA for all non-API routes."""
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
