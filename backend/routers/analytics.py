"""
数据洞察路由
"""
from datetime import datetime, timedelta
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


@router.get("/trend")
async def get_trend(days: int = 7, user=Depends(get_current_user)):
    """最近 N 天的每日采集/发布趋势"""
    async with async_session() as db:
        today = datetime.utcnow().date()
        labels = []
        collect_data = []
        publish_data = []
        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            label = f"{d.month:02d}-{d.day:02d}"
            labels.append(label)
            day_start = datetime.combine(d, datetime.min.time())
            day_end = datetime.combine(d, datetime.max.time())
            # Count notes created on this day
            note_count = (await db.execute(
                select(func.count()).select_from(Note)
                .where(Note.created_at >= day_start, Note.created_at <= day_end)
            )).scalar() or 0
            # Count publish tasks created on this day
            pub_count = (await db.execute(
                select(func.count()).select_from(PublishTask)
                .where(PublishTask.created_at >= day_start, PublishTask.created_at <= day_end)
            )).scalar() or 0
            collect_data.append(note_count)
            publish_data.append(pub_count)
        return {"success": True, "data": {"labels": labels, "collect": collect_data, "publish": publish_data}}


@router.get("/category-dist")
async def get_category_dist(user=Depends(get_current_user)):
    """素材库笔记的类型分布"""
    async with async_session() as db:
        result = await db.execute(
            select(Note.note_type, func.count()).select_from(Note)
            .where(Note.in_library == True)
            .group_by(Note.note_type)
        )
        rows = result.all()
        data = [{"type": r[0] or "normal", "count": r[1]} for r in rows]
        return {"success": True, "data": data}
