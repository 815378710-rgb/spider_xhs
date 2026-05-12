"""
实时日志系统 — 分页查询 + SSE 实时推送
使用 loguru 自定义 sink 捕获日志，存储在内存环形缓冲区（最近1000条）
"""
import json
import time
import asyncio
from datetime import datetime, timezone, timedelta
from collections import deque
from fastapi import APIRouter, Query, Depends
from fastapi.responses import StreamingResponse
from loguru import logger

from core.deps import get_current_user

router = APIRouter()

# 中国时区 UTC+8
CHINA_TZ = timezone(timedelta(hours=8))

# ── 内存环形缓冲区 ──────────────────────────────────────────────────────────
LOG_BUFFER: deque = deque(maxlen=1000)
_log_id_counter: int = 0
_sse_subscribers: list = []

# ── Loguru 自定义 sink ─────────────────────────────────────────────────────
def _log_sink(message):
    """自定义 loguru sink，将日志存入内存缓冲区并通知 SSE 订阅者"""
    global _log_id_counter
    record = message.record
    level = record["level"].name
    if level not in ("INFO", "WARNING", "ERROR", "SUCCESS", "DEBUG"):
        level = "INFO"

    _log_id_counter += 1
    entry = {
        "id": _log_id_counter,
        "level": level,
        "message": record["message"],
        "time": record["time"].astimezone(CHINA_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "module": record["module"],
        "function": record["function"],
    }
    LOG_BUFFER.append(entry)

    # 通知所有 SSE 订阅者
    for q in _sse_subscribers[:]:
        try:
            q.put_nowait(entry)
        except asyncio.QueueFull:
            pass


# 添加 loguru sink
logger.add(_log_sink, format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {module}:{function}:{line} - {message}", level="INFO")


@router.get("")
async def get_logs(
    level: str = Query("", description="按级别过滤 (INFO/WARNING/ERROR/SUCCESS/DEBUG)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user),
):
    """分页查询日志"""
    logs = list(LOG_BUFFER)
    if level:
        logs = [l for l in logs if l["level"] == level.upper()]

    total = len(logs)
    start = (page - 1) * page_size
    end = start + page_size
    logs_page = logs[::-1][start:end]  # 最新的在前

    return {
        "success": True,
        "data": logs_page,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/stream")
async def log_stream(user=Depends(get_current_user)):
    """SSE 实时日志推送"""
    queue = asyncio.Queue(maxsize=200)
    _sse_subscribers.append(queue)

    async def event_generator():
        try:
            # 先发送最近20条历史日志
            recent = list(LOG_BUFFER)[-20:]
            for entry in recent:
                yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"

            while True:
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    # 心跳保活
                    yield f": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in _sse_subscribers:
                _sse_subscribers.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
