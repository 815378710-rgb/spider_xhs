"""
笔记采集路由 — 带超时保护 + 错误分类
"""
import json
import time
import random
import asyncio
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

# 采集超时时间（秒）
COLLECT_TIMEOUT = 20


class CollectRequest(BaseModel):
    url: str = ""


class NoteDetailRequest(BaseModel):
    note_id: str = ""


async def _fetch_note_info_with_timeout(note_url: str, cookies: str, timeout: float = COLLECT_TIMEOUT):
    """带超时保护的笔记信息获取"""
    def _sync_fetch():
        from apis.xhs_pc_apis import XHS_Apis
        xhs = XHS_Apis()
        return xhs.get_note_info(note_url, cookies)

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_sync_fetch),
            timeout=timeout,
        )
        return result
    except asyncio.TimeoutError:
        logger.warning(f"采集超时 ({timeout}s): {note_url[:80]}")
        return False, f"采集超时（超过{timeout}秒），请检查网络或Cookie", {}
    except Exception as e:
        logger.error(f"采集异常: {e}")
        error_str = str(e).lower()
        if "cookie" in error_str or "login" in error_str or "401" in error_str:
            return False, f"Cookie已过期，请重新登录: {str(e)[:80]}", {}
        if "connect" in error_str or "timeout" in error_str or "network" in error_str:
            return False, f"网络连接失败: {str(e)[:80]}", {}
        return False, f"采集异常: {str(e)[:100]}", {}


def _resolve_short_url(note_url: str) -> str:
    """解析短链接"""
    if "xhslink.com" in note_url:
        import requests as req_lib
        try:
            resp = req_lib.head(note_url, allow_redirects=False, timeout=10,
                                headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"})
            if resp.status_code in (301, 302):
                note_url = resp.headers.get("Location", note_url)
        except Exception:
            pass
    return note_url


def _classify_error(msg: str) -> str:
    """根据错误信息分类错误类型"""
    msg_lower = msg.lower()
    if "cookie" in msg_lower or "login" in msg_lower or "过期" in msg or "401" in msg_lower:
        return "cookie_expired"
    if "超时" in msg or "timeout" in msg_lower:
        return "timeout"
    if "connect" in msg_lower or "network" in msg_lower or "连接" in msg:
        return "network_error"
    if "反爬" in msg or "captcha" in msg_lower or "verify" in msg_lower:
        return "anti_crawl"
    if "not found" in msg_lower or "不存在" in msg or "未找到" in msg:
        return "not_found"
    return "unknown_error"


@router.post("/detail")
async def get_note_detail(req: NoteDetailRequest, user=Depends(get_current_user)):
    """Get note detail by note_id (带超时保护)."""
    note_id = req.note_id.strip()
    if not note_id:
        return {"success": False, "message": "note_id 不能为空", "error_type": "invalid_input"}

    note_url = f"https://www.xiaohongshu.com/explore/{note_id}"

    # 检查Cookie
    cookies = settings.COOKIES
    if not cookies:
        return {"success": False, "message": "Cookie 未配置，请先登录", "error_type": "cookie_expired"}

    success, msg, data = await _fetch_note_info_with_timeout(note_url, cookies)
    if not success:
        return {
            "success": False,
            "message": msg,
            "error_type": _classify_error(msg),
        }

    note_data = data.get("data", {})
    items = note_data.get("items", [])
    if items:
        note_card = items[0].get("note_card", {})
    else:
        note_card = note_data.get("note_card", {})
        if not note_card:
            return {"success": False, "message": "笔记数据为空", "error_type": "not_found"}

    return {"success": True, "data": note_card}


@router.post("/collect")
async def collect_note(req: CollectRequest, user=Depends(get_current_user)):
    """Collect a single note by URL (带超时保护)."""
    note_url = req.url.strip()
    if not note_url:
        return {"success": False, "message": "请输入笔记链接", "error_type": "invalid_input"}

    # 检查Cookie
    cookies = settings.COOKIES
    if not cookies:
        return {"success": False, "message": "Cookie 未配置，请先登录", "error_type": "cookie_expired"}

    # Resolve short URL
    note_url = _resolve_short_url(note_url)

    success, msg, data = await _fetch_note_info_with_timeout(note_url, cookies)
    if not success:
        return {
            "success": False,
            "message": msg,
            "error_type": _classify_error(msg),
        }

    note_data = data.get("data", {})
    items = note_data.get("items", [])
    if not items:
        return {"success": False, "message": "未找到笔记数据", "error_type": "not_found"}

    note = items[0].get("note_card", {})

    # Extract structured data
    try:
        from xhs_utils.data_util import handle_note_info
        result = handle_note_info(data)
    except Exception as e:
        logger.error(f"解析笔记数据异常: {e}")
        return {"success": False, "message": f"解析笔记数据异常: {str(e)[:80]}", "error_type": "parse_error"}

    # Save to database
    try:
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
    except Exception as e:
        logger.error(f"保存笔记到数据库异常: {e}")
        # 仍然返回成功，只是没有保存
        return {"success": True, "data": result, "message": "采集成功（数据库保存失败，请重试）"}

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
from fastapi import WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from core.config import settings

_ws_connections = []


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # P1-7 修复：WebSocket认证 - 从查询参数获取token
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="未授权：缺少token")
        return
    
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise JWTError("Invalid token")
    except (JWTError, Exception):
        await websocket.close(code=4001, reason="未授权：token无效")
        return
    
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
