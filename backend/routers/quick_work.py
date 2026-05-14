"""
One-stop workbench - Collect -> AI rewrite -> Image dedup
Replicates v1 core experience: paste link, one-click complete
Supports async task mode: background thread + task ID + polling API
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
from sqlalchemy import select
from core.config import settings
from core.deps import get_current_user
from core.database import async_session
from loguru import logger

router = APIRouter()

# Async task storage
# Task status: pending / running / completed / failed
# Module-level state - protected by TASK_LOCK (threading.Lock).
# threading.Lock is correct here because _run_quick_work_task runs in
# background threads (not on the async event loop).
ASYNC_TASKS: dict[str, dict] = {}
TASK_LOCK = threading.Lock()


class QuickWorkRequest(BaseModel):
    url: str
    style: str = "maintain original style"
    ratio: int = 50
    debate: bool = True
    image_level: str = "medium"
    model: str = ""
    industry: str = ""


def _resolve_short_url(url: str) -> str:
    """Resolve XHS short link"""
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


def _download_image(url: str, cookies_str: str = "") -> str:
    """Download XHS CDN image to local (with Cookie + multi-header strategy)"""
    from curl_cffi import requests as req
    if url.startswith("http://"):
        url = url.replace("http://", "https://", 1)
    if not cookies_str:
        cookies_str = settings.COOKIES or ""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    save_dir = os.path.join(project_root, "backend", "data", "images")
    os.makedirs(save_dir, exist_ok=True)
    filename = f"img_{int(time.time() * 1000)}_{random.randint(1000, 9999)}.jpg"
    filepath = os.path.join(save_dir, filename)

    cookie_dict = {}
    for pair in cookies_str.split(";"):
        pair = pair.strip()
        if "=" in pair:
            k, _, v = pair.partition("=")
            cookie_dict[k.strip()] = v.strip()

    header_sets = [
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
            "Referer": "https://www.xiaohongshu.com/",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "sec-ch-ua": '"Not.A/Brand";v="99", "Google Chrome";v="147", "Chromium";v="147"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site",
        },
        {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "Referer": "https://www.xiaohongshu.com/",
            "Accept": "image/*,*/*",
        },
    ]
    for headers in header_sets:
        try:
            resp = req.request("GET", url, headers=headers, cookies=cookie_dict, 
                             impersonate="chrome120", timeout=20)
            logger.info(f"[_download_image] {url[:60]} status={resp.status_code} len={len(resp.content)}")
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                logger.info(f"[_download_image] saved: {filepath} ({len(resp.content)} bytes)")
                return f"/data/images/{filename}"
        except Exception as e:
            logger.warning(f"[_download_image] attempt failed: {url[:60]} -> {e}")
            continue
    raise RuntimeError(f"Image download failed: {url[:60]}")


def _process_image_bytes(img_bytes: bytes, level: str) -> bytes:
    """Call image dedup processing"""
    from utils.image_processor import process_image
    return process_image(img_bytes, level)


@router.post("/run")
async def quick_work_run(req: QuickWorkRequest, user=Depends(get_current_user)):
    """One-stop: collect note -> AI rewrite -> image dedup, return full result"""
    user_id = int(user["sub"])
    user_cookie = ""
    async with async_session() as db:
        from models.user import User
        result = await db.execute(select(User).where(User.id == user_id))
        u = result.scalar_one_or_none()
        if u:
            user_cookie = u.cookie or ""
    cookies = user_cookie or settings.COOKIES
    if not cookies:
        return {"success": False, "message": "Cookie not configured"}

    note_url = _resolve_short_url(req.url.strip())
    result = {
        "original": None,
        "rewritten": None,
        "images_original": [],
        "images_processed": [],
        "debate": None,
    }

    # Step 1: Collect note
    try:
        await asyncio.sleep(random.uniform(0.5, 1.5))
        from apis.xhs_pc_apis import XHS_Apis
        xhs = XHS_Apis()
        success, msg, note_info = xhs.get_note_info(note_url, cookies)
        if not success:
            return {"success": False, "message": f"Collection failed: {msg}"}

        items = note_info.get("data", {}).get("items", [])
        if items:
            note = items[0]
            note_card = note["note_card"]
        else:
            note_card = note_info.get("data", {}).get("note_card", None)
            if not note_card:
                return {"success": False, "message": "Note data is empty"}
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

    except Exception as e:
        logger.exception(f"Collection error: {e}")
        return {"success": False, "message": f"Collection error: {str(e)[:100]}"}

    # Step 2: Download original images
    images = []
    for img_url in raw_images:
        try:
            local_path = _download_image(img_url, cookies)
            images.append(local_path)
        except Exception as e:
            logger.warning(f"Image download failed: {img_url[:60]} -> {e}")
            images.append(img_url)
    result["images_original"] = images

    # Step 3: AI rewrite
    llm = settings.get_llm_config()
    if not llm.get("api_key"):
        return {
            "success": True,
            "data": result,
            "message": "Collection complete (AI API Key not configured, skip rewrite)",
        }

    try:
        from utils.rewrite import create_backend, rewrite_note, rewrite_with_debate
        model_override = req.model or llm["model"]
        backend = create_backend(llm["provider"], llm["api_key"],
                                 model=model_override, base_url=llm["base_url"])
        if not backend:
            result["rewritten"] = {"title": "(AI backend creation failed)", "desc": ""}
        elif req.debate:
            debate_result = await rewrite_with_debate(title, desc, backend,
                                                style=req.style, ratio=req.ratio)
            result["debate"] = debate_result
            result["rewritten"] = debate_result.get("winner", {})
        else:
            result["rewritten"] = await rewrite_note(title, desc, backend,
                                               style=req.style, ratio=req.ratio)
    except Exception as e:
        logger.exception(f"AI rewrite error: {e}")
        result["rewritten"] = {"title": f"(Rewrite failed: {str(e)[:50]})", "desc": ""}

    # Step 4: Image dedup
    processed_images = []
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(project_root, "backend", "data")
    processed_dir = os.path.join(data_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)

    step4_cookies = cookies
    cookie_dict = {}
    for pair in step4_cookies.split(";"):
        pair = pair.strip()
        if "=" in pair:
            k, _, v = pair.partition("=")
            cookie_dict[k.strip()] = v.strip()

    for i, img_path in enumerate(images):
        try:
            if img_path.startswith("/data/") or img_path.startswith("/"):
                fs_path = os.path.join(project_root, "backend", img_path.lstrip("/"))
                logger.info(f"[Step4] Reading local image: {fs_path}")
                if not os.path.exists(fs_path):
                    logger.warning(f"[Step4] Local file not found: {fs_path}")
                    img_bytes = None
                else:
                    with open(fs_path, "rb") as f:
                        img_bytes = f.read()
            else:
                img_bytes = None

            if not img_bytes or len(img_bytes) < 100:
                logger.info(f"[Step4] Trying CDN download: {img_path[:80]}")
                from curl_cffi import requests as req
                cdn_url = img_path
                if cdn_url.startswith("http://"):
                    cdn_url = cdn_url.replace("http://", "https://", 1)
                for headers in [
                    {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
                        "Referer": "https://www.xiaohongshu.com/",
                        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    },
                    {
                        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
                        "Referer": "https://www.xiaohongshu.com/",
                        "Accept": "image/*,*/*",
                    },
                ]:
                    try:
                        resp = req.request("GET", cdn_url, headers=headers, cookies=cookie_dict,
                                         impersonate="chrome120", timeout=20)
                        logger.info(f"[Step4] CDN download status: {resp.status_code} len={len(resp.content)}")
                        if resp.status_code == 200 and len(resp.content) > 1000:
                            img_bytes = resp.content
                            break
                    except Exception as e:
                        logger.warning(f"[Step4] CDN download failed: {e}")
                        continue

            if not img_bytes or len(img_bytes) < 100:
                logger.error(f"[Step4] Invalid image data: {img_path[:80]} (bytes={len(img_bytes) if img_bytes else 0})")
                processed_images.append({"original": img_path, "processed": None, "error": "Invalid image data"})
                continue

            logger.info(f"[Step4] Processing image {i+1}: {len(img_bytes)} bytes, level={req.image_level}")
            processed_bytes = _process_image_bytes(img_bytes, req.image_level)
            filename = f"processed_{int(time.time())}_{i}.jpg"
            filepath = os.path.join(processed_dir, filename)
            with open(filepath, "wb") as f:
                f.write(processed_bytes)
            logger.info(f"[Step4] Image processing successful: {filepath} ({len(processed_bytes)} bytes)")
            processed_images.append({
                "original": img_path,
                "processed": f"/data/processed/{filename}",
            })
        except Exception as e:
            logger.exception(f"[Step4] Image dedup failed: {img_path[:60]} -> {e}")
            processed_images.append({"original": img_path, "processed": None, "error": str(e)[:80]})

    result["images_processed"] = processed_images

    # Stats update
    try:
        from core.database import async_session as _async_session
        from models.task_log import TaskLog
        async with _async_session() as db:
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
        "message": f"Complete! Collection: {title[:20]}... | {len(images)} images | {'Rewritten' if result['rewritten'] else 'Not rewritten'}",
    }


# ==============================================================================
#  Async task mode - background thread + task ID + polling
# ==============================================================================

def _run_quick_work_task(task_id: str, req_data: dict):
    """Execute one-stop workbench task in background thread"""
    cookies = req_data.get("_cookies", "") or settings.COOKIES
    if not cookies:
        with TASK_LOCK:
            ASYNC_TASKS[task_id].update(status="failed", error="Cookie not configured")
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

    # Step 1: Collect note
    try:
        _update("Collecting note...", 10)
        time.sleep(random.uniform(0.5, 1.5))
        from apis.xhs_pc_apis import XHS_Apis
        xhs = XHS_Apis()
        success, msg, note_info = xhs.get_note_info(note_url, cookies)
        if not success:
            with TASK_LOCK:
                ASYNC_TASKS[task_id].update(status="failed", error=f"Collection failed: {msg}")
            return

        items = note_info.get("data", {}).get("items", [])
        if items:
            note = items[0]
            note_card = note["note_card"]
        else:
            note_card = note_info.get("data", {}).get("note_card", None)
            if not note_card:
                with TASK_LOCK:
                    ASYNC_TASKS[task_id].update(status="failed", error="Note data is empty")
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
        _update("Collection complete, downloading images...", 30)
    except Exception as e:
        logger.exception(f"Collection error: {e}")
        with TASK_LOCK:
            ASYNC_TASKS[task_id].update(status="failed", error=f"Collection error: {str(e)[:100]}")
        return

    # Step 2: Download original images
    images = []
    for img_url in raw_images:
        try:
            local_path = _download_image(img_url, cookies)
            images.append(local_path)
        except Exception as e:
            logger.warning(f"Image download failed: {img_url[:60]} -> {e}")
            images.append(img_url)
    result["images_original"] = images
    _update("Images downloaded, AI rewriting...", 40)

    # Step 3: AI rewrite
    llm = settings.get_llm_config()
    if llm.get("api_key"):
        try:
            from utils.rewrite import create_backend, rewrite_note, rewrite_with_debate
            model_override = req_data.get("model", "") or llm["model"]
            backend = create_backend(llm["provider"], llm["api_key"],
                                     model=model_override, base_url=llm["base_url"])
            if not backend:
                result["rewritten"] = {"title": "(AI backend creation failed)", "desc": ""}
            elif req_data.get("debate", True):
                _update("AI Agent debating...", 55)
                debate_result = asyncio.run(rewrite_with_debate(title, desc, backend,
                                                    style=req_data.get("style", "maintain original style"),
                                                    ratio=req_data.get("ratio", 50)))
                result["debate"] = debate_result
                result["rewritten"] = debate_result.get("winner", {})
            else:
                _update("AI rewriting...", 55)
                result["rewritten"] = asyncio.run(rewrite_note(title, desc, backend,
                                                   style=req_data.get("style", "maintain original style"),
                                                   ratio=req_data.get("ratio", 50)))
        except Exception as e:
            logger.exception(f"AI rewrite error: {e}")
            result["rewritten"] = {"title": f"(Rewrite failed: {str(e)[:50]})", "desc": ""}
    _update("AI rewrite complete, image dedup...", 70)

    # Step 4: Image dedup
    processed_images = []
    project_root2 = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.path.join(project_root2, "backend", "data")
    processed_dir = os.path.join(data_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)

    image_level = req_data.get("image_level", "medium")
    total_images = len(images)
    for i, img_path in enumerate(images):
        try:
            _update(f"Image dedup ({i+1}/{total_images})...", 70 + int(25 * (i / max(total_images, 1))))
            if img_path.startswith("/data/") or img_path.startswith("/"):
                fs_path = os.path.join(project_root2, "backend", img_path.lstrip("/"))
                if os.path.exists(fs_path):
                    with open(fs_path, "rb") as f:
                        img_bytes = f.read()
                else:
                    img_bytes = None
            else:
                img_bytes = None

            if not img_bytes or len(img_bytes) < 100:
                from curl_cffi import requests as req
                cookie_dict2 = {}
                for pair in cookies.split(";"):
                    pair = pair.strip()
                    if "=" in pair:
                        k, _, v = pair.partition("=")
                        cookie_dict2[k.strip()] = v.strip()
                for headers in [
                    {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
                        "Referer": "https://www.xiaohongshu.com/",
                        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    },
                    {
                        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
                        "Referer": "https://www.xiaohongshu.com/",
                        "Accept": "image/*,*/*",
                    },
                ]:
                    try:
                        resp = req.request("GET", img_path, headers=headers, cookies=cookie_dict2,
                                         impersonate="chrome120", timeout=20)
                        if resp.status_code == 200 and len(resp.content) > 1000:
                            img_bytes = resp.content
                            break
                    except Exception:
                        continue

            if not img_bytes or len(img_bytes) < 100:
                processed_images.append({"original": img_path, "processed": None, "error": "Invalid image data"})
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
            logger.warning(f"Image dedup failed: {img_path[:60]} -> {e}")
            processed_images.append({"original": img_path, "processed": None, "error": str(e)[:80]})

    result["images_processed"] = processed_images

    # Stats update
    try:
        from core.database import async_session as _async_session
        from models.task_log import TaskLog
        loop = asyncio.new_event_loop()
        async def _save_log():
            async with _async_session() as db:
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

    msg = f"Complete! Collection: {title[:20]}... | {len(images)} images | {'Rewritten' if result['rewritten'] else 'Not rewritten'}"
    with TASK_LOCK:
        ASYNC_TASKS[task_id].update(
            status="completed",
            progress=100,
            step="Complete",
            result=result,
            message=msg,
        )


@router.post("/run-async")
async def quick_work_run_async(req: QuickWorkRequest, user=Depends(get_current_user)):
    """Start async task: collect note -> AI rewrite -> image dedup, returns task_id for polling"""
    user_id = int(user["sub"])
    user_cookie = ""
    async with async_session() as db:
        from models.user import User
        result = await db.execute(select(User).where(User.id == user_id))
        u = result.scalar_one_or_none()
        if u:
            user_cookie = u.cookie or ""
    cookies = user_cookie or settings.COOKIES
    if not cookies:
        return {"success": False, "message": "Cookie not configured"}

    task_id = f"qw_{uuid.uuid4().hex[:12]}"
    with TASK_LOCK:
        ASYNC_TASKS[task_id] = {
            "task_id": task_id,
            "status": "running",
            "progress": 0,
            "step": "Task created...",
            "result": None,
            "error": None,
            "message": None,
            "created_at": time.time(),
        }

    req_data = req.dict()
    req_data["_cookies"] = cookies
    thread = threading.Thread(target=_run_quick_work_task, args=(task_id, req_data), daemon=True)
    thread.start()

    return {"success": True, "task_id": task_id, "message": "Task submitted"}


@router.get("/task/{task_id}")
async def get_task_status(task_id: str, user=Depends(get_current_user)):
    """Poll async task status"""
    with TASK_LOCK:
        task = ASYNC_TASKS.get(task_id)
    if not task:
        return {"success": False, "message": "Task not found"}
    return {"success": True, "data": task}


@router.get("/tasks")
async def list_recent_tasks(user=Depends(get_current_user)):
    """List recent async tasks"""
    with TASK_LOCK:
        tasks = sorted(ASYNC_TASKS.values(), key=lambda t: t["created_at"], reverse=True)[:20]
    return {"success": True, "data": tasks}
