"""
一站式工作台 — 采集 → AI改写 → 图片降重
复刻 v1 核心体验：粘贴链接，一键完成
支持异步任务模式：后台线程执行 + 任务ID + 轮询接口
"""
import os
import time
import random
import json
import asyncio
import threading
import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from core.config import settings
from core.deps import get_current_user
from loguru import logger

router = APIRouter()

# ── 异步任务存储 ──────────────────────────────────────────────────────────
# 任务状态: pending / running / completed / failed
ASYNC_TASKS: dict[str, dict] = {}
TASK_LOCK = threading.Lock()


class QuickWorkRequest(BaseModel):
    url: str
    style: str = "保持原风格"
    ratio: int = 50
    debate: bool = True
    image_level: str = "medium"
    model: str = ""
    industry: str = ""


def _resolve_short_url(url: str) -> str:
    """解析小红书短链接"""
    if "xhslink.com" not in url:
        return url
    try:
        import requests as req
        resp = req.head(url, allow_redirects=False, timeout=10,
                        headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"})
        if resp.status_code in (301, 302):
            return resp.headers.get("Location", url)
        resp = req.request("GET", url, allow_redirects=True, timeout=10,
                           headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"})
        return resp.url if resp.url != url else url
    except Exception:
        return url


def _download_image(url: str) -> str:
    """下载小红书CDN图片到本地"""
    import requests as req
    save_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "images")
    os.makedirs(save_dir, exist_ok=True)
    filename = f"img_{int(time.time() * 1000)}_{random.randint(1000, 9999)}.jpg"
    filepath = os.path.join(save_dir, filename)

    header_sets = [
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
         "Referer": "https://www.xiaohongshu.com/"},
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
         "Referer": "https://www.xiaohongshu.com/"},
        {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"},
        {},
    ]
    for headers in header_sets:
        try:
            resp = req.request("GET", url, headers=headers, timeout=20)
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                return f"/data/images/{filename}"
        except Exception:
            continue
    raise RuntimeError(f"图片下载失败: {url[:60]}")


def _process_image_bytes(img_bytes: bytes, level: str) -> bytes:
    """调用图片防重处理"""
    from utils.image_processor import process_image
    return process_image(img_bytes, level)


@router.post("/run")
async def quick_work_run(req: QuickWorkRequest, user=Depends(get_current_user)):
    """
    一站式：采集笔记 → AI改写 → 图片降重
    返回完整结果
    """
    cookies = settings.COOKIES
    if not cookies:
        return {"success": False, "message": "Cookie 未配置，请先在设置中添加小红书 Cookie"}

    note_url = _resolve_short_url(req.url.strip())
    result = {
        "original": None,
        "rewritten": None,
        "images_original": [],
        "images_processed": [],
        "debate": None,
    }

    # ── Step 1: 采集笔记 ──────────────────────────────────────────────────
    try:
        # P1-3 修复：使用await asyncio.sleep代替time.sleep，避免阻塞事件循环
        await asyncio.sleep(random.uniform(0.5, 1.5))
        from apis.xhs_pc_apis import XHS_Apis
        xhs = XHS_Apis()
        success, msg, note_info = xhs.get_note_info(note_url, cookies)
        if not success:
            return {"success": False, "message": f"采集失败: {msg}"}

        items = note_info.get("data", {}).get("items", [])
        if items:
            note = items[0]
            note_card = note["note_card"]
        else:
            note_card = note_info.get("data", {}).get("note_card", None)
            if not note_card:
                return {"success": False, "message": "笔记数据为空，请检查链接是否有效"}
            note = note_info["data"]

        title = note_card.get("title", "")
        desc = note_card.get("desc", "")
        author = note_card.get("user", {}).get("nickname", "")

        # 提取图片
        raw_images = []
        for img in note_card.get("image_list", []):
            info_list = img.get("info_list", [])
            cdn_url = None
            if len(info_list) > 1:
                cdn_url = info_list[1].get("url", "")
            elif len(info_list) > 0:
                cdn_url = info_list[0].get("url", "")
            if not cdn_url:
                cdn_url = img.get("url_default", "") or img.get("url_pre", "") or ""
            if cdn_url:
                raw_images.append(cdn_url)

        result["original"] = {
            "note_id": note.get("id", ""),
            "title": title,
            "desc": desc,
            "author": author,
            "likes": note_card.get("interact_info", {}).get("liked_count", 0),
            "collects": note_card.get("interact_info", {}).get("collected_count", 0),
            "comments": note_card.get("interact_info", {}).get("comment_count", 0),
        }

    except Exception as e:
        logger.exception(f"采集异常: {e}")
        return {"success": False, "message": f"采集异常: {str(e)[:100]}"}

    # ── Step 2: 下载原图 ──────────────────────────────────────────────────
    images = []
    for img_url in raw_images:
        try:
            local_path = _download_image(img_url)
            images.append(local_path)
        except Exception as e:
            logger.warning(f"图片下载失败: {img_url[:60]} -> {e}")
            images.append(img_url)  # fallback to CDN URL
    result["images_original"] = images

    # ── Step 3: AI 改写 ──────────────────────────────────────────────────
    llm = settings.get_llm_config()
    if not llm.get("api_key"):
        return {
            "success": True,
            "data": result,
            "message": "采集完成（AI API Key 未配置，跳过改写）",
        }

    try:
        from utils.rewrite import create_backend, rewrite_note, rewrite_with_debate
        model_override = req.model or llm["model"]
        backend = create_backend(llm["provider"], llm["api_key"],
                                 model=model_override, base_url=llm["base_url"])
        if not backend:
            result["rewritten"] = {"title": "(AI 后端创建失败)", "desc": ""}
        elif req.debate:
            debate_result = rewrite_with_debate(title, desc, backend,
                                                style=req.style, ratio=req.ratio)
            result["debate"] = debate_result
            result["rewritten"] = debate_result.get("winner", {})
        else:
            result["rewritten"] = rewrite_note(title, desc, backend,
                                               style=req.style, ratio=req.ratio)
    except Exception as e:
        logger.exception(f"AI 改写异常: {e}")
        result["rewritten"] = {"title": f"(改写失败: {str(e)[:50]})", "desc": ""}

    # ── Step 4: 图片降重 ──────────────────────────────────────────────────
    processed_images = []
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    processed_dir = os.path.join(data_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)

    for i, img_path in enumerate(images):
        try:
            if img_path.startswith("/data/"):
                fs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), img_path.lstrip("/"))
                with open(fs_path, "rb") as f:
                    img_bytes = f.read()
            elif img_path.startswith("/"):
                fs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), img_path.lstrip("/"))
                with open(fs_path, "rb") as f:
                    img_bytes = f.read()
            else:
                # CDN URL — 尝试下载
                img_bytes = None
                import requests as req
                for headers in [
                    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                     "Referer": "https://www.xiaohongshu.com/"},
                    {},
                ]:
                    try:
                        resp = req.request("GET", img_path, headers=headers, timeout=20)
                        if resp.status_code == 200 and len(resp.content) > 1000:
                            img_bytes = resp.content
                            break
                    except Exception:
                        continue

            if not img_bytes or len(img_bytes) < 100:
                processed_images.append({"original": img_path, "processed": None, "error": "图片数据无效"})
                continue

            processed_bytes = _process_image_bytes(img_bytes, req.image_level)
            filename = f"processed_{int(time.time())}_{i}.jpg"
            filepath = os.path.join(processed_dir, filename)
            with open(filepath, "wb") as f:
                f.write(processed_bytes)
            processed_images.append({
                "original": img_path,
                "processed": f"/data/processed/{filename}",
            })
        except Exception as e:
            logger.warning(f"图片降重失败: {img_path[:60]} -> {e}")
            processed_images.append({"original": img_path, "processed": None, "error": str(e)[:80]})

    result["images_processed"] = processed_images

    # ── 统计更新 ──────────────────────────────────────────────────────────
    try:
        from core.database import async_session
        from models.task_log import TaskLog
        async with async_session() as db:
            log = TaskLog(
                task_type="quick_work",
                status="success",
                detail=json.dumps({
                    "title": title[:50],
                    "images": len(images),
                    "rewritten": bool(result["rewritten"]),
                }, ensure_ascii=False),
            )
            db.add(log)
            await db.commit()
    except Exception:
        pass

    return {
        "success": True,
        "data": result,
        "message": f"完成！采集: {title[:20]}... | {len(images)}张图 | {'已改写' if result['rewritten'] else '未改写'}",
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  异步任务模式 — 后台线程 + 任务ID + 轮询
# ═══════════════════════════════════════════════════════════════════════════════

def _run_quick_work_task(task_id: str, req_data: dict):
    """在后台线程中执行一站式工作台任务"""
    cookies = settings.COOKIES
    if not cookies:
        with TASK_LOCK:
            ASYNC_TASKS[task_id].update(status="failed", error="Cookie 未配置")
        return

    note_url = _resolve_short_url(req_data["url"].strip())
    result = {
        "original": None,
        "rewritten": None,
        "images_original": [],
        "images_processed": [],
        "debate": None,
    }

    def _update(step: str, progress: int = 0):
        with TASK_LOCK:
            ASYNC_TASKS[task_id].update(step=step, progress=progress)

    # ── Step 1: 采集笔记 ──────────────────────────────────────────────────
    try:
        _update("正在采集笔记...", 10)
        time.sleep(random.uniform(0.5, 1.5))
        from apis.xhs_pc_apis import XHS_Apis
        xhs = XHS_Apis()
        success, msg, note_info = xhs.get_note_info(note_url, cookies)
        if not success:
            with TASK_LOCK:
                ASYNC_TASKS[task_id].update(status="failed", error=f"采集失败: {msg}")
            return

        items = note_info.get("data", {}).get("items", [])
        if items:
            note = items[0]
            note_card = note["note_card"]
        else:
            note_card = note_info.get("data", {}).get("note_card", None)
            if not note_card:
                with TASK_LOCK:
                    ASYNC_TASKS[task_id].update(status="failed", error="笔记数据为空")
                return
            note = note_info["data"]

        title = note_card.get("title", "")
        desc = note_card.get("desc", "")
        author = note_card.get("user", {}).get("nickname", "")

        raw_images = []
        for img in note_card.get("image_list", []):
            info_list = img.get("info_list", [])
            cdn_url = None
            if len(info_list) > 1:
                cdn_url = info_list[1].get("url", "")
            elif len(info_list) > 0:
                cdn_url = info_list[0].get("url", "")
            if not cdn_url:
                cdn_url = img.get("url_default", "") or img.get("url_pre", "") or ""
            if cdn_url:
                raw_images.append(cdn_url)

        result["original"] = {
            "note_id": note.get("id", ""),
            "title": title,
            "desc": desc,
            "author": author,
            "likes": note_card.get("interact_info", {}).get("liked_count", 0),
            "collects": note_card.get("interact_info", {}).get("collected_count", 0),
            "comments": note_card.get("interact_info", {}).get("comment_count", 0),
        }
        _update("采集完成，正在下载图片...", 30)
    except Exception as e:
        logger.exception(f"采集异常: {e}")
        with TASK_LOCK:
            ASYNC_TASKS[task_id].update(status="failed", error=f"采集异常: {str(e)[:100]}")
        return

    # ── Step 2: 下载原图 ──────────────────────────────────────────────────
    images = []
    for img_url in raw_images:
        try:
            local_path = _download_image(img_url)
            images.append(local_path)
        except Exception as e:
            logger.warning(f"图片下载失败: {img_url[:60]} -> {e}")
            images.append(img_url)
    result["images_original"] = images
    _update("图片下载完成，正在AI改写...", 40)

    # ── Step 3: AI 改写 ──────────────────────────────────────────────────
    llm = settings.get_llm_config()
    if llm.get("api_key"):
        try:
            from utils.rewrite import create_backend, rewrite_note, rewrite_with_debate
            model_override = req_data.get("model", "") or llm["model"]
            backend = create_backend(llm["provider"], llm["api_key"],
                                     model=model_override, base_url=llm["base_url"])
            if not backend:
                result["rewritten"] = {"title": "(AI 后端创建失败)", "desc": ""}
            elif req_data.get("debate", True):
                _update("AI Agent辩论中...", 55)
                debate_result = rewrite_with_debate(title, desc, backend,
                                                    style=req_data.get("style", "保持原风格"),
                                                    ratio=req_data.get("ratio", 50))
                result["debate"] = debate_result
                result["rewritten"] = debate_result.get("winner", {})
            else:
                _update("AI改写中...", 55)
                result["rewritten"] = rewrite_note(title, desc, backend,
                                                   style=req_data.get("style", "保持原风格"),
                                                   ratio=req_data.get("ratio", 50))
        except Exception as e:
            logger.exception(f"AI 改写异常: {e}")
            result["rewritten"] = {"title": f"(改写失败: {str(e)[:50]})", "desc": ""}
    _update("AI改写完成，正在图片降重...", 70)

    # ── Step 4: 图片降重 ──────────────────────────────────────────────────
    processed_images = []
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    processed_dir = os.path.join(data_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)

    image_level = req_data.get("image_level", "medium")
    total_images = len(images)
    for i, img_path in enumerate(images):
        try:
            _update(f"图片降重 ({i+1}/{total_images})...", 70 + int(25 * (i / max(total_images, 1))))
            if img_path.startswith("/data/"):
                fs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), img_path.lstrip("/"))
                with open(fs_path, "rb") as f:
                    img_bytes = f.read()
            elif img_path.startswith("/"):
                fs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), img_path.lstrip("/"))
                with open(fs_path, "rb") as f:
                    img_bytes = f.read()
            else:
                img_bytes = None
                import requests as req
                for headers in [
                    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                     "Referer": "https://www.xiaohongshu.com/"},
                    {},
                ]:
                    try:
                        resp = req.request("GET", img_path, headers=headers, timeout=20)
                        if resp.status_code == 200 and len(resp.content) > 1000:
                            img_bytes = resp.content
                            break
                    except Exception:
                        continue

            if not img_bytes or len(img_bytes) < 100:
                processed_images.append({"original": img_path, "processed": None, "error": "图片数据无效"})
                continue

            processed_bytes = _process_image_bytes(img_bytes, image_level)
            filename = f"processed_{int(time.time())}_{i}.jpg"
            filepath = os.path.join(processed_dir, filename)
            with open(filepath, "wb") as f:
                f.write(processed_bytes)
            processed_images.append({
                "original": img_path,
                "processed": f"/data/processed/{filename}",
            })
        except Exception as e:
            logger.warning(f"图片降重失败: {img_path[:60]} -> {e}")
            processed_images.append({"original": img_path, "processed": None, "error": str(e)[:80]})

    result["images_processed"] = processed_images

    # ── 统计更新 ──────────────────────────────────────────────────────────
    try:
        from core.database import async_session
        from models.task_log import TaskLog
        # Use a new event loop for the async DB call in the thread
        loop = asyncio.new_event_loop()
        async def _save_log():
            async with async_session() as db:
                log = TaskLog(
                    task_type="quick_work",
                    status="success",
                    detail=json.dumps({
                        "title": title[:50],
                        "images": len(images),
                        "rewritten": bool(result["rewritten"]),
                    }, ensure_ascii=False),
                )
                db.add(log)
                await db.commit()
        loop.run_until_complete(_save_log())
        loop.close()
    except Exception:
        pass

    msg = f"完成！采集: {title[:20]}... | {len(images)}张图 | {'已改写' if result['rewritten'] else '未改写'}"
    with TASK_LOCK:
        ASYNC_TASKS[task_id].update(
            status="completed",
            progress=100,
            step="完成",
            result=result,
            message=msg,
        )


@router.post("/run-async")
async def quick_work_run_async(req: QuickWorkRequest, user=Depends(get_current_user)):
    """启动异步任务：采集笔记 → AI改写 → 图片降重，返回 task_id 供轮询"""
    cookies = settings.COOKIES
    if not cookies:
        return {"success": False, "message": "Cookie 未配置，请先在设置中添加小红书 Cookie"}

    task_id = f"qw_{uuid.uuid4().hex[:12]}"
    with TASK_LOCK:
        ASYNC_TASKS[task_id] = {
            "task_id": task_id,
            "status": "running",
            "progress": 0,
            "step": "任务已创建...",
            "result": None,
            "error": None,
            "message": None,
            "created_at": time.time(),
        }

    # 启动后台线程
    req_data = req.dict()
    thread = threading.Thread(target=_run_quick_work_task, args=(task_id, req_data), daemon=True)
    thread.start()

    return {"success": True, "task_id": task_id, "message": "任务已提交，可在工作台查看进度"}


@router.get("/task/{task_id}")
async def get_task_status(task_id: str, user=Depends(get_current_user)):
    """轮询异步任务状态"""
    with TASK_LOCK:
        task = ASYNC_TASKS.get(task_id)
    if not task:
        return {"success": False, "message": "任务不存在"}
    return {"success": True, "data": task}


@router.get("/tasks")
async def list_recent_tasks(user=Depends(get_current_user)):
    """列出最近的异步任务"""
    with TASK_LOCK:
        tasks = sorted(ASYNC_TASKS.values(), key=lambda t: t["created_at"], reverse=True)[:20]
    return {"success": True, "data": tasks}
