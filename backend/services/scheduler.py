"""
APScheduler integration — background task scheduling
"""
import asyncio
from loguru import logger

_scheduler = None


async def start_scheduler():
    """Start the APScheduler instance."""
    global _scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger

        _scheduler = AsyncIOScheduler()
        _scheduler.start()
        logger.info("✅ APScheduler started")
    except ImportError:
        logger.warning("APScheduler not installed, scheduling disabled")
    except Exception as e:
        logger.error(f"Scheduler start failed: {e}")


async def stop_scheduler():
    """Stop the APScheduler instance."""
    global _scheduler
    if _scheduler:
        try:
            _scheduler.shutdown(wait=False)
            logger.info("APScheduler stopped")
        except Exception:
            pass


def add_scheduled_job(job_id: str, cron_str: str, func, **kwargs):
    """Add a cron job to the scheduler."""
    if not _scheduler:
        return
    try:
        from apscheduler.triggers.cron import CronTrigger
        parts = cron_str.split()
        trigger = CronTrigger(
            minute=parts[0] if len(parts) > 0 else "*",
            hour=parts[1] if len(parts) > 1 else "*",
            day=parts[2] if len(parts) > 2 else "*",
            month=parts[3] if len(parts) > 3 else "*",
            day_of_week=parts[4] if len(parts) > 4 else "*",
        )
        _scheduler.add_job(func, trigger, id=job_id, replace_existing=True, **kwargs)
    except Exception as e:
        logger.error(f"Failed to add job {job_id}: {e}")


def remove_job(job_id: str):
    """Remove a job from the scheduler."""
    if not _scheduler:
        return
    try:
        _scheduler.remove_job(job_id)
    except Exception:
        pass
