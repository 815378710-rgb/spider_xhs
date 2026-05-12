"""
发布中心路由 — 即时发布 + 定时发布 + 状态追踪
"""
import json
import time
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, func, update
from core.deps import get_current_user
from core.database import async_session
from core.config import settings
from models.publish_task import PublishTask
from loguru import logger

router = APIRouter()


class PublishCreateRequest(BaseModel):
    draft_id: Optional[int] = None
    account_id: Optional[int] = None
    title: str = ""
    content: str = ""
    images_json: str = "[]"
    tags_json: str = "[]"
    topics_json: str = "[]"
    location: str = ""
    privacy: str = "public"
    scheduled_at: Optional[str] = None  # ISO datetime string for scheduled publish


class PublishCancelRequest(BaseModel):
    task_id: int


@router.get("")
async def list_publish_tasks(page: int = 1, page_size: int = 20, status: str = "", user=Depends(get_current_user)):
    async with async_session() as db:
        q = select(PublishTask)
        if status:
            q = q.where(PublishTask.status == status)
        q = q.order_by(PublishTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(q)
        tasks = result.scalars().all()
        count_q = select(func.count()).select_from(PublishTask)
        if status:
            count_q = count_q.where(PublishTask.status == status)
        total = (await db.execute(count_q)).scalar() or 0
        return {
            "success": True, "total": total,
            "data": [
                {
                    "id": t.id, "draft_id": t.draft_id, "account_id": t.account_id,
                    "status": t.status, "title": t.title, "content": t.content,
                    "note_type": t.note_type, "privacy": t.privacy,
                    "scheduled_at": str(t.scheduled_at) if t.scheduled_at else None,
                    "published_at": str(t.published_at) if t.published_at else None,
                    "xhs_note_id": t.xhs_note_id, "error_msg": t.error_msg,
                    "retry_count": t.retry_count, "created_at": str(t.created_at),
                } for t in tasks
            ],
        }


@router.post("")
async def create_publish_task(req: PublishCreateRequest, user=Depends(get_current_user)):
    """Create a publish task (immediate or scheduled)."""
    async with async_session() as db:
        task = PublishTask(
            draft_id=req.draft_id, account_id=req.account_id,
            title=req.title, content=req.content,
            images_json=req.images_json, tags_json=req.tags_json,
            topics_json=req.topics_json, location=req.location,
            privacy=req.privacy,
        )
        if req.scheduled_at:
            try:
                task.scheduled_at = datetime.fromisoformat(req.scheduled_at)
                task.status = "pending"
            except ValueError:
                return {"success": False, "message": "时间格式无效"}
        else:
            task.status = "running"

        db.add(task)
        await db.flush()
        task_id = task.id
        await db.commit()

        # If immediate, publish now
        if not req.scheduled_at:
            import asyncio
            asyncio.create_task(_execute_publish(task_id))

        return {"success": True, "id": task_id, "message": "发布任务已创建"}


@router.post("/cancel")
async def cancel_publish(req: PublishCancelRequest, user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(PublishTask).where(PublishTask.id == req.task_id))
        task = result.scalar_one_or_none()
        if not task:
            return {"success": False, "message": "任务不存在"}
        if task.status not in ("pending", "running"):
            return {"success": False, "message": "任务已完成或已失败，无法取消"}
        task.status = "cancelled"
        await db.commit()
        return {"success": True, "message": "已取消"}


@router.post("/retry/{task_id}")
async def retry_publish(task_id: int, user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(PublishTask).where(PublishTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return {"success": False, "message": "任务不存在"}
        if task.status != "failed":
            return {"success": False, "message": "只能重试失败的任务"}
        task.status = "running"
        task.retry_count += 1
        await db.commit()
    import asyncio
    asyncio.create_task(_execute_publish(task_id))
    return {"success": True, "message": "重试中"}


async def _execute_publish(task_id: int):
    """Execute a publish task using Creator API."""
    from apis.xhs_creator_apis import XHS_Creator_Apis
    from core.database import async_session
    from services.audit import log_task

    audit_id = await log_task(
        task_type="publish",
        status="running",
        detail=f"发布任务 #{task_id}",
        triggered_by="system",
    )

    async with async_session() as db:
        result = await db.execute(select(PublishTask).where(PublishTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return
        try:
            creator = XHS_Creator_Apis()
            note_info = {
                "title": task.title,
                "desc": task.content,
                "images": json.loads(task.images_json),
                "topics": json.loads(task.topics_json) if task.topics_json else [],
                "location": task.location,
                "privacy": task.privacy,
            }
            ok, msg, data = creator.post_note(note_info, settings.COOKIES)
            if ok:
                task.status = "success"
                task.published_at = datetime.utcnow()
                task.xhs_note_id = data.get("note_id", "")
                await log_task(
                    task_type="publish",
                    status="success",
                    detail=f"发布成功: {task.title[:30]}",
                    output_summary=json.dumps({"note_id": task.xhs_note_id, "title": task.title[:50]}),
                )
            else:
                task.status = "failed"
                task.error_msg = msg
                await log_task(
                    task_type="publish",
                    status="failed",
                    detail=f"发布失败: {task.title[:30]}",
                    error_detail=msg,
                )
                if task.retry_count < task.max_retries:
                    task.status = "pending"  # Will be retried
        except Exception as e:
            task.status = "failed"
            task.error_msg = str(e)[:200]
            await log_task(
                task_type="publish",
                status="failed",
                detail=f"发布异常: {task.title[:30]}",
                error_detail=str(e)[:500],
            )
        await db.commit()
