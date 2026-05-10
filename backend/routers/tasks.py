"""
任务中心路由
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from core.deps import get_current_user
from core.database import async_session
from models.task_log import TaskLog

router = APIRouter()


@router.get("")
async def list_tasks(page: int = 1, page_size: int = 20, task_type: str = "", user=Depends(get_current_user)):
    async with async_session() as db:
        q = select(TaskLog)
        if task_type:
            q = q.where(TaskLog.task_type == task_type)
        q = q.order_by(TaskLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(q)
        tasks = result.scalars().all()
        count_q = select(func.count()).select_from(TaskLog)
        if task_type:
            count_q = count_q.where(TaskLog.task_type == task_type)
        total = (await db.execute(count_q)).scalar() or 0
        return {
            "success": True, "total": total,
            "data": [
                {
                    "id": t.id, "task_type": t.task_type, "status": t.status,
                    "detail": t.detail, "duration_seconds": t.duration_seconds,
                    "created_at": str(t.created_at),
                } for t in tasks
            ],
        }


@router.get("/types")
async def list_task_types(user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(TaskLog.task_type).distinct())
        types = [r[0] for r in result.all()]
        return {"success": True, "data": types}


@router.get("/stats")
async def task_stats(user=Depends(get_current_user)):
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
