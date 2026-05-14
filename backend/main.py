"""
土豆小红书助手 - FastAPI Backend
"""
import os
import sys

# Ensure backend package is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Also add parent Spider_XHS dir  so routers can import apis/, xhs_utils/, utils/
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
    # Initialize admin user and license keys
    await _init_admin_and_keys()
    # Start scheduler
    from services.scheduler import start_scheduler
    await start_scheduler()
    logger.info("✅ Scheduler started")
    yield
    # Shutdown
    from services.scheduler import stop_scheduler
    await stop_scheduler()
    logger.info("🛑 土豆小红书助手 backend stopped")


async def _init_admin_and_keys():
    """Create default admin user and initial license keys if needed."""
    from sqlalchemy import select, func
    from core.database import async_session
    from models.user import User, LicenseKey
    from core.security import hash_password, generate_license_key

    async with async_session() as db:
        # Check if admin exists
        result = await db.execute(select(User).where(User.role == "admin"))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password("congshaoyu102@"),
                role="admin",
                status="active",
            )
            db.add(admin)
            await db.flush()
            logger.info("✅ Created default admin user (admin / congshaoyu102@)")

        # Generate initial license keys if none exist
        count = (await db.execute(select(func.count()).select_from(LicenseKey))).scalar() or 0
        if count == 0:
            admin_id = admin.id if admin else 1
            keys = []
            for _ in range(10):
                key = generate_license_key()
                lk = LicenseKey(key=key, valid_days=30, created_by=admin_id, status="unused")
                db.add(lk)
                keys.append(key)
            await db.flush()
            logger.info(f"✅ Generated 10 initial license keys:")
            for k in keys:
                logger.info(f"   {k}")

        await db.commit()


app = FastAPI(
    title="土豆小红书助手 API",
    description="土豆小红书助手 API",
    version="2.2.0",
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

# ── Register routers ─────────────────────────────────────────────────
from routers import (
    auth, config, login, accounts, cookies,
    collect, search, content, drafts, rewrite, images,
    publish, automation, monitor, analytics,
    kol, qianfan, anti_crawl, proxy, tasks, notifications,
    quick_work, logs, content_check, ai_check, crawl_monitor,
    topic_recommend, admin,
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
    (logs.router,          "/api/logs",           "日志系统"),
    (content_check.router, "/api/content-check",  "内容检测"),
    (ai_check.router,      "/api/ai-check",       "AI检测"),
    (crawl_monitor.router, "/api/crawl-monitor",  "反爬监控"),
    (topic_recommend.router, "/api/topics",       "选题推荐"),
    (admin.router,          "/api/admin",         "管理员"),
]

for router, prefix, tag in router_prefix_map:
    app.include_router(router, prefix=prefix, tags=[tag])


# ── Health check ──────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.2.0"}


# ── Serve data files (images, processed) ────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

app.mount("/data/images", StaticFiles(directory=IMAGES_DIR), name="data-images")
app.mount("/data/processed", StaticFiles(directory=PROCESSED_DIR), name="data-processed")


# ── Serve frontend (built React apps) ─────────────────────────
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
ADMIN_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend-admin", "dist")

# Mount user frontend assets
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

# Mount admin frontend assets
if os.path.isdir(ADMIN_DIST):
    app.mount("/admin/assets", StaticFiles(directory=os.path.join(ADMIN_DIST, "assets")), name="admin-assets")

# Serve admin frontend for /admin/* routes
if os.path.isdir(ADMIN_DIST):
    @app.get("/admin/{full_path:path}")
    async def serve_admin_spa(full_path: str):
        """Serve Admin frontend for /admin/* routes."""
        from pathlib import Path
        
        static_dir = Path(ADMIN_DIST).resolve()
        requested_path = (static_dir / full_path).resolve()
        
        # 防止路径遍历攻击
        if not str(requested_path).startswith(str(static_dir)):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Forbidden")
        
        if requested_path.is_file():
            return FileResponse(requested_path)
        return FileResponse(os.path.join(ADMIN_DIST, "index.html"))

# Serve user frontend for all other non-API routes
if os.path.isdir(FRONTEND_DIST):
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve User frontend for all other non-API routes."""
        from pathlib import Path
        
        static_dir = Path(FRONTEND_DIST).resolve()
        requested_path = (static_dir / full_path).resolve()
        
        # 防止路径遍历攻击
        if not str(requested_path).startswith(str(static_dir)):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Forbidden")
        
        if requested_path.is_file():
            return FileResponse(requested_path)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


# ── Entry point ─────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    # 禁用reload，避免文件变化导致重启失败
    uvicorn.run("main:app", host="0.0.0.0", port=5005, reload=False)
