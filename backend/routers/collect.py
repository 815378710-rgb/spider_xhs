"""
笔记采集路由
"""
import json
import time
import random
import threading
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from core.config import settings
from core.deps import get_current_user
from loguru import logger

router = APIRouter()

# Task status tracking (in-memory, same as original)
TASK_STATUS = {}
PROXY_QUEUE = []
PROXY_RESULTS = {}
PROXY_LOCK = threading.Lock()


class CollectRequest(BaseModel):
    url: str = ""


@router.post("/collect")
async def collect_note(req: CollectRequest, user=Depends(get_current_user)):
    """Collect a single note by URL."""
    note_url = req.url.strip()
    if not note_url:
        return {"success": False, "message": "请输入笔记链接"}

    # Resolve short URL
    if "xhslink.com" in note_url:
        import requests as req_lib
        try:
            resp = req_lib.head(note_url, allow_redirects=False, timeout=10,
                                headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"})
            if resp.status_code in (301, 302):
                note_url = resp.headers.get("Location", note_url)
        except Exception:
            pass

    try:
        from apis.xhs_pc_apis import XHS_Apis
        xhs = XHS_Apis()
        cookies = settings.COOKIES
        success, msg, data = xhs.get_note_info(note_url, cookies)
        if not success:
            return {"success": False, "message": f"采集失败: {msg}"}

        note_data = data.get("data", {})
        items = note_data.get("items", [])
        if not items:
            return {"success": False, "message": "未找到笔记数据"}

        note = items[0].get("note_card", {})

        # Extract structured data
        from xhs_utils.data_util import handle_note_info
        result = handle_note_info(data)

        # Save to database
        from core.database import async_session
        from models.note import Note
        from sqlalchemy import select
        async with async_session() as db:
            existing = await db.execute(select(Note).where(Note.note_id == result.get("note_id", "")))
            if existing.scalar_one_or_none():
                return {"success": True, "data": result, "message": "笔记已存在"}

            note_obj = Note(
                note_id=result.get("note_id", ""),
                title=result.get("title", ""),
                desc=result.get("desc", ""),
                note_type=result.get("note_type", "normal"),
                url=result.get("url", note_url),
                author_name=result.get("author_name", ""),
                author_id=result.get("author_id", ""),
                likes=result.get("likes", 0),
                collects=result.get("collects", 0),
                comments=result.get("comments", 0),
                shares=result.get("shares", 0),
                images_json=json.dumps(result.get("images", [])),
                tags_json=json.dumps(result.get("tags", [])),
                source="collect",
            )
            db.add(note_obj)
            await db.commit()

        # Download images
        images = result.get("images", [])
        saved_images = []
        for img_url in images[:10]:
            try:
                local_path = _download_image(img_url)
                saved_images.append(local_path)
            except Exception as e:
                logger.warning(f"图片下载失败: {e}")

        result["local_images"] = saved_images
        return {"success": True, "data": result, "message": "采集成功"}
    except Exception as e:
        logger.exception(f"采集笔记异常: {e}")
        return {"success": False, "message": f"采集异常: {str(e)[:100]}"}


def _download_image(url: str) -> str:
    """Download XHS CDN image to local."""
    import requests as req
    import os
    save_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "images")
    os.makedirs(save_dir, exist_ok=True)
    filename = f"img_{int(time.time() * 1000)}_{random.randint(1000, 9999)}.jpg"
    filepath = os.path.join(save_dir, filename)

    headers_sets = [
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
         "Referer": "https://www.xiaohongshu.com/"},
        {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"},
        {},
    ]
    for headers in headers_sets:
        try:
            resp = req.request("GET", url, headers=headers, timeout=20)
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                return f"/data/images/{filename}"
        except Exception:
            continue
    raise RuntimeError(f"图片下载失败: {url[:60]}")


# ── WebSocket task progress ───────────────────────────────────────────────────
import asyncio
from fastapi import WebSocket

_ws_connections = []


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _ws_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle task requests from client
    except Exception:
        pass
    finally:
        _ws_connections.remove(websocket)


async def broadcast_progress(task_id: str, progress: int, message: str):
    """Broadcast task progress to all connected WebSocket clients."""
    data = json.dumps({"task_id": task_id, "progress": progress, "message": message})
    for ws in _ws_connections[:]:
        try:
            await ws.send_text(data)
        except Exception:
            _ws_connections.remove(ws)
