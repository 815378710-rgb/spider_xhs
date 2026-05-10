"""
数据洞察路由
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from core.deps import get_current_user
from core.database import async_session
from models.note import Note
from models.publish_task import PublishTask
from models.task_log import TaskLog

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(user=Depends(get_current_user)):
    """Overview dashboard data."""
    async with async_session() as db:
        total_notes = (await db.execute(select(func.count()).select_from(Note))).scalar() or 0
        library_notes = (await db.execute(select(func.count()).select_from(Note).where(Note.in_library == True))).scalar() or 0
        total_publish = (await db.execute(select(func.count()).select_from(PublishTask))).scalar() or 0
        success_publish = (await db.execute(select(func.count()).select_from(PublishTask).where(PublishTask.status == "success"))).scalar() or 0
        total_tasks = (await db.execute(select(func.count()).select_from(TaskLog))).scalar() or 0
        return {
            "success": True,
            "data": {
                "total_notes": total_notes,
                "library_notes": library_notes,
                "total_publish": total_publish,
                "success_publish": success_publish,
                "publish_rate": f"{success_publish / total_publish * 100:.1f}%" if total_publish > 0 else "0%",
                "total_tasks": total_tasks,
            },
        }


@router.get("/top-notes")
async def top_notes(limit: int = 10, user=Depends(get_current_user)):
    """Top notes by engagement."""
    async with async_session() as db:
        result = await db.execute(
            select(Note).where(Note.in_library == True)
            .order_by(Note.likes.desc()).limit(limit)
        )
        notes = result.scalars().all()
        return {
            "success": True,
            "data": [
                {"title": n.title, "author": n.author_name, "likes": n.likes,
                 "collects": n.collects, "comments": n.comments}
                for n in notes
            ],
        }


@router.get("/task-summary")
async def task_summary(user=Depends(get_current_user)):
    """Task execution summary by type."""
    async with async_session() as db:
        result = await db.execute(
            select(TaskLog.task_type, func.count(), func.avg(TaskLog.duration_seconds))
            .group_by(TaskLog.task_type)
        )
        rows = result.all()
        return {
            "success": True,
            "data": [
                {"type": r[0], "count": r[1], "avg_duration": round(r[2] or 0, 1)}
                for r in rows
            ],
        }
