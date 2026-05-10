"""
浏览器代理转发路由 — Chrome 扩展从这里拉取请求
"""
import time
import uuid
import threading
from fastapi import APIRouter, Depends
from core.deps import get_current_user

router = APIRouter()

PROXY_QUEUE = []
PROXY_RESULTS = {}
PROXY_LOCK = threading.Lock()


@router.get("/pending")
async def proxy_pending(user=Depends(get_current_user)):
    """Chrome 扩展轮询：获取待转发的请求"""
    with PROXY_LOCK:
        now = time.time()
        PROXY_QUEUE[:] = [r for r in PROXY_QUEUE if now - r.get("created_at", 0) < 60]
        pending = list(PROXY_QUEUE[:5])
        PROXY_QUEUE[:] = PROXY_QUEUE[5:]
    return {
        "success": True,
        "requests": [{k: v for k, v in r.items() if k != "created_at"} for r in pending],
    }


@router.post("/result")
async def proxy_result(body: dict, user=Depends(get_current_user)):
    """Chrome 扩展回传请求结果"""
    request_id = body.get("request_id", "")
    with PROXY_LOCK:
        PROXY_RESULTS[request_id] = {
            "success": body.get("success", False),
            "status": body.get("status", 0),
            "data": body.get("data"),
            "error": body.get("error", ""),
        }
    return {"success": True}


def enqueue_browser_request(method: str, url: str, headers: dict = None, body: str = "", timeout: int = 30):
    """将请求加入浏览器代理队列，等待 Chrome 扩展转发"""
    request_id = str(uuid.uuid4())[:12]
    with PROXY_LOCK:
        PROXY_QUEUE.append({
            "request_id": request_id,
            "method": method,
            "url": url,
            "headers": headers or {},
            "body": body,
            "created_at": time.time(),
        })
    deadline = time.time() + timeout
    while time.time() < deadline:
        with PROXY_LOCK:
            result = PROXY_RESULTS.pop(request_id, None)
        if result is not None:
            return result
        time.sleep(0.3)
    return {"success": False, "error": "timeout: 浏览器代理未响应"}
