"""
审计日志服务 — 记录所有关键操作的审计追踪
"""
import time
from datetime import datetime
from loguru import logger


async def log_task(
    task_type: str,
    status: str = "running",
    detail: str = "",
    account_id: int = None,
    input_summary: str = "",
    output_summary: str = "",
    error_detail: str = "",
    triggered_by: str = "system",
    duration_seconds: float = 0,
):
    """Write a task audit log entry to the database."""
    try:
        from core.database import async_session
        from models.task_log import TaskLog

        async with async_session() as db:
            log = TaskLog(
                task_type=task_type,
                status=status,
                detail=detail,
                account_id=account_id,
                input_summary=input_summary[:500] if input_summary else "",
                output_summary=output_summary[:500] if output_summary else "",
                error_detail=error_detail[:1000] if error_detail else "",
                triggered_by=triggered_by,
                duration_seconds=int(duration_seconds),
            )
            db.add(log)
            await db.commit()
            return log.id
    except Exception as e:
        logger.warning(f"Failed to write audit log: {e}")
        return None


class TaskTimer:
    """Context manager for timing task execution and auto-logging."""

    def __init__(self, task_type: str, detail: str = "", account_id: int = None,
                 triggered_by: str = "system"):
        self.task_type = task_type
        self.detail = detail
        self.account_id = account_id
        self.triggered_by = triggered_by
        self.start_time = 0
        self.task_id = None
        self.status = "running"
        self.output_summary = ""
        self.error_detail = ""

    async def __aenter__(self):
        self.start_time = time.time()
        self.task_id = await log_task(
            task_type=self.task_type,
            status="running",
            detail=self.detail,
            account_id=self.account_id,
            triggered_by=self.triggered_by,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if exc_type:
            self.status = "failed"
            self.error_detail = str(exc_val)[:500]
        await log_task(
            task_type=self.task_type,
            status=self.status,
            detail=self.detail,
            account_id=self.account_id,
            triggered_by=self.triggered_by,
            output_summary=self.output_summary,
            error_detail=self.error_detail,
            duration_seconds=duration,
        )
        return False  # Don't suppress exceptions
