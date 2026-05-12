"""
任务审计日志路由 — 查看所有操作的审计追踪
"""
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, delete as sql_delete
from core.deps import get_current_user
from core.database import async_session
from models.task_log import TaskLog

router = APIRouter()


@router.get("")
async def list_tasks(
    page: int = 1, page_size: int = 20,
    task_type: str = "", status: str = "",
    start_date: str = "", end_date: str = "",
    user=Depends(get_current_user),
):
    """分页查询审计日志，支持类型/状态/日期过滤"""
    async with async_session() as db:
        q = select(TaskLog)
        count_q = select(func.count()).select_from(TaskLog)

        filters = []
        if task_type:
            filters.append(TaskLog.task_type == task_type)
        if status:
            filters.append(TaskLog.status == status)
        if start_date:
            try:
                filters.append(TaskLog.created_at >= datetime.fromisoformat(start_date))
            except ValueError:
                pass
        if end_date:
            try:
                filters.append(TaskLog.created_at <= datetime.fromisoformat(end_date))
            except ValueError:
                pass

        for f in filters:
            q = q.where(f)
            count_q = count_q.where(f)

        q = q.order_by(TaskLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(q)
        tasks = result.scalars().all()
        total = (await db.execute(count_q)).scalar() or 0

        return {
            "success": True, "total": total,
            "data": [
                {
                    "id": t.id,
                    "task_type": t.task_type,
                    "status": t.status,
                    "detail": t.detail,
                    "input_summary": t.input_summary,
                    "output_summary": t.output_summary,
                    "error_detail": t.error_detail,
                    "triggered_by": t.triggered_by,
                    "duration_seconds": t.duration_seconds,
                    "account_id": t.account_id,
                    "created_at": str(t.created_at),
                } for t in tasks
            ],
        }


@router.get("/types")
async def list_task_types(user=Depends(get_current_user)):
    """查询所有任务类型"""
    async with async_session() as db:
        result = await db.execute(select(TaskLog.task_type).distinct())
        types = [r[0] for r in result.all() if r[0]]
        return {"success": True, "data": types}


@router.get("/stats")
async def task_stats(days: int = 7, user=Depends(get_current_user)):
    """按类型统计任务数量和耗时"""
    async with async_session() as db:
        since = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(
                TaskLog.task_type,
                TaskLog.status,
                func.count(),
                func.avg(TaskLog.duration_seconds),
            )
            .where(TaskLog.created_at >= since)
            .group_by(TaskLog.task_type, TaskLog.status)
        )
        rows = result.all()

        # Aggregate by type
        type_stats = {}
        for r in rows:
            t = r[0] or "unknown"
            if t not in type_stats:
                type_stats[t] = {"type": t, "total": 0, "success": 0, "failed": 0, "running": 0, "avg_duration": 0}
            type_stats[t]["total"] += r[2]
            type_stats[t][r[1]] = type_stats[t].get(r[1], 0) + r[2]
            type_stats[t]["avg_duration"] = round(r[3] or 0, 1)

        return {
            "success": True,
            "data": list(type_stats.values()),
        }


@router.delete("/{task_id}")
async def delete_task_log(task_id: int, user=Depends(get_current_user)):
    """删除单条审计日志"""
    async with async_session() as db:
        await db.execute(sql_delete(TaskLog).where(TaskLog.id == task_id))
        await db.commit()
        return {"success": True, "message": "已删除"}


@router.delete("")
async def clear_old_logs(days: int = 30, user=Depends(get_current_user)):
    """清理N天前的审计日志"""
    async with async_session() as db:
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(sql_delete(TaskLog).where(TaskLog.created_at < cutoff))
        await db.commit()
        return {"success": True, "message": f"已清理 {result.rowcount} 条旧日志"}
