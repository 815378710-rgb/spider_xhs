"""
APScheduler integration — background task scheduling
"""
import asyncio
from loguru import logger

_scheduler = None


def get_scheduler():
    """Get the APScheduler instance (may be None if not started)."""
    return _scheduler


async def start_scheduler():
    """Start the APScheduler instance."""
    global _scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        _scheduler = AsyncIOScheduler()
        _scheduler.start()
        logger.info("✅ APScheduler started")

        # 注册Cookie健康巡检任务（每2小时）
        try:
            from services.health_checker import health_checker

            async def _cookie_health_job():
                await health_checker.check_cookie_health()

            _scheduler.add_job(
                _cookie_health_job,
                IntervalTrigger(hours=2),
                id='cookie_health_check',
                replace_existing=True,
            )
            logger.info("✅ Cookie健康巡检任务已注册 (每2小时)")
        except Exception as e:
            logger.warning(f"Cookie巡检任务注册失败（非致命）: {e}")

        # 启动时加载所有活跃的自动化流水线定时任务
        try:
            await _load_automation_jobs()
        except Exception as e:
            logger.warning(f"加载自动化定时任务失败（非致命）: {e}")

        # 启动定时发布检查器（每60秒扫描到期任务）
        try:
            async def _scheduled_publish_check():
                await _check_scheduled_publishes()
            _scheduler.add_job(
                _scheduled_publish_check,
                IntervalTrigger(seconds=60),
                id='scheduled_publish_check',
                replace_existing=True,
            )
            logger.info("✅ 定时发布检查器已注册 (每60秒)")
        except Exception as e:
            logger.warning(f"定时发布检查器注册失败（非致命）: {e}")

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
        logger.info(f"✅ Cron job registered: {job_id} ({cron_str})")
    except Exception as e:
        logger.error(f"Failed to add job {job_id}: {e}")


def remove_job(job_id: str):
    """Remove a job from the scheduler."""
    if not _scheduler:
        return
    try:
        _scheduler.remove_job(job_id)
        logger.info(f"Cron job removed: {job_id}")
    except Exception:
        pass


# ── 自动化流水线定时任务 ─────────────────────────────────────────────────────

async def _load_automation_jobs():
    """启动时从DB加载所有活跃的自动化流水线并注册到APScheduler"""
    from core.database import async_session
    from models.automation import Automation
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(
            select(Automation).where(Automation.is_active == True, Automation.schedule_cron != "")
        )
        automations = result.scalars().all()
        for auto in automations:
            _register_automation_job(auto.id, auto.schedule_cron)
        if automations:
            logger.info(f"✅ 加载了 {len(automations)} 个自动化定时任务")


def _register_automation_job(auto_id: int, cron_str: str):
    """注册单个自动化流水线的定时任务"""
    if not cron_str or not cron_str.strip():
        return

    async def _run_pipeline():
        try:
            from routers.automation import _execute_pipeline
            await _execute_pipeline(auto_id)
        except Exception as e:
            logger.error(f"自动化流水线 #{auto_id} 定时执行失败: {e}")

    add_scheduled_job(f"automation_{auto_id}", cron_str.strip(), _run_pipeline)


def unregister_automation_job(auto_id: int):
    """移除自动化流水线的定时任务"""
    remove_job(f"automation_{auto_id}")


# ── 定时发布检查 ─────────────────────────────────────────────────────────────

async def _check_scheduled_publishes():
    """扫描到期的定时发布任务并触发执行"""
    from core.database import async_session
    from models.publish_task import PublishTask
    from sqlalchemy import select
    from datetime import datetime

    async with async_session() as db:
        now = datetime.utcnow()
        result = await db.execute(
            select(PublishTask).where(
                PublishTask.status == "pending",
                PublishTask.scheduled_at != None,  # noqa: E711
                PublishTask.scheduled_at <= now,
            ).limit(10)
        )
        tasks = result.scalars().all()
        for task in tasks:
            logger.info(f"⏰ 定时发布触发: #{task.id} - {task.title[:30]}")
            try:
                # Import and run inline to avoid circular imports
                from routers.publish import _execute_publish
                asyncio.create_task(_execute_publish(task.id))
            except Exception as e:
                logger.error(f"定时发布 #{task.id} 启动失败: {e}")
