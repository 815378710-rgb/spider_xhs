"""
自动化流水线路由 — 全自动：搜索→改写→图片处理→发布
增强版：执行日志、失败重试、步骤级追踪
"""
import json
import time
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, func, delete as sql_delete
from core.deps import get_current_user
from core.database import async_session
from models.automation import Automation, AutomationLog
from loguru import logger

router = APIRouter()


class AutomationCreate(BaseModel):
    name: str = ""
    keywords: str = ""  # comma-separated
    schedule_cron: str = "0 9 * * *"
    pipeline_config: str = "{}"
    account_id: Optional[int] = None


class AutomationUpdate(BaseModel):
    name: Optional[str] = None
    keywords: Optional[str] = None
    schedule_cron: Optional[str] = None
    pipeline_config: Optional[str] = None
    is_active: Optional[bool] = None


# ── CRUD ─────────────────────────────────────────────────────────────────────

@router.get("")
async def list_automations(user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(Automation).order_by(Automation.created_at.desc()))
        items = result.scalars().all()
        return {
            "success": True,
            "data": [
                {
                    "id": a.id, "name": a.name, "keywords": a.keywords,
                    "is_active": a.is_active, "schedule_cron": a.schedule_cron,
                    "pipeline_config": a.pipeline_config,
                    "last_run": str(a.last_run) if a.last_run else None,
                    "next_run": str(a.next_run) if a.next_run else None,
                    "run_count": a.run_count,
                    "success_count": a.success_count,
                    "fail_count": a.fail_count,
                    "created_at": str(a.created_at),
                } for a in items
            ],
        }


@router.post("")
async def create_automation(req: AutomationCreate, user=Depends(get_current_user)):
    async with async_session() as db:
        auto = Automation(
            name=req.name, keywords=req.keywords,
            schedule_cron=req.schedule_cron,
            pipeline_config=req.pipeline_config,
            account_id=req.account_id,
        )
        db.add(auto)
        await db.flush()
        await db.commit()
        # Register cron job if schedule is set
        if auto.schedule_cron and auto.is_active:
            from services.scheduler import _register_automation_job
            _register_automation_job(auto.id, auto.schedule_cron)
        return {"success": True, "id": auto.id, "message": "流水线已创建"}


@router.put("/{auto_id}")
async def update_automation(auto_id: int, req: AutomationUpdate, user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(Automation).where(Automation.id == auto_id))
        auto = result.scalar_one_or_none()
        if not auto:
            return {"success": False, "message": "流水线不存在"}
        for field in ["name", "keywords", "schedule_cron", "pipeline_config", "is_active"]:
            val = getattr(req, field)
            if val is not None:
                setattr(auto, field, val)
        await db.commit()
        # Update scheduler job
        from services.scheduler import _register_automation_job, unregister_automation_job
        unregister_automation_job(auto_id)
        if auto.is_active and auto.schedule_cron:
            _register_automation_job(auto_id, auto.schedule_cron)
        return {"success": True, "message": "已更新"}


@router.delete("/{auto_id}")
async def delete_automation(auto_id: int, user=Depends(get_current_user)):
    async with async_session() as db:
        await db.execute(sql_delete(AutomationLog).where(AutomationLog.automation_id == auto_id))
        await db.execute(sql_delete(Automation).where(Automation.id == auto_id))
        await db.commit()
        # Remove scheduler job
        from services.scheduler import unregister_automation_job
        unregister_automation_job(auto_id)
        return {"success": True, "message": "已删除"}


@router.post("/{auto_id}/run")
async def run_automation(auto_id: int, user=Depends(get_current_user)):
    """手动触发流水线执行"""
    async with async_session() as db:
        result = await db.execute(select(Automation).where(Automation.id == auto_id))
        auto = result.scalar_one_or_none()
        if not auto:
            return {"success": False, "message": "流水线不存在"}
    import asyncio
    # P1-6 修复：包装asyncio.create_task，处理异常
    try:
        asyncio.create_task(_execute_pipeline(auto_id))
    except Exception as e:
        logger.exception(f"启动流水线失败: {e}")
        return {"success": False, "message": f"启动失败: {str(e)[:100]}"}
    return {"success": True, "message": "流水线已启动"}


@router.post("/{auto_id}/toggle")
async def toggle_automation(auto_id: int, user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(Automation).where(Automation.id == auto_id))
        auto = result.scalar_one_or_none()
        if not auto:
            return {"success": False, "message": "流水线不存在"}
        auto.is_active = not auto.is_active
        await db.commit()
        # Update scheduler job
        from services.scheduler import _register_automation_job, unregister_automation_job
        unregister_automation_job(auto_id)
        if auto.is_active and auto.schedule_cron:
            _register_automation_job(auto_id, auto.schedule_cron)
        return {"success": True, "is_active": auto.is_active}


# ── 执行日志 ─────────────────────────────────────────────────────────────────

@router.get("/{auto_id}/logs")
async def list_logs(auto_id: int, limit: int = 50, user=Depends(get_current_user)):
    """获取流水线执行日志"""
    async with async_session() as db:
        result = await db.execute(
            select(AutomationLog).where(AutomationLog.automation_id == auto_id)
            .order_by(AutomationLog.created_at.desc()).limit(limit)
        )
        logs = result.scalars().all()
        return {
            "success": True,
            "data": [
                {
                    "id": l.id, "keyword": l.keyword, "step": l.step,
                    "status": l.status, "message": l.message,
                    "duration_ms": l.duration_ms, "created_at": str(l.created_at),
                } for l in logs
            ],
        }


@router.delete("/{auto_id}/logs")
async def clear_logs(auto_id: int, user=Depends(get_current_user)):
    """清空执行日志"""
    async with async_session() as db:
        await db.execute(sql_delete(AutomationLog).where(AutomationLog.automation_id == auto_id))
        await db.commit()
        return {"success": True, "message": "日志已清空"}


@router.get("/stats/summary")
async def pipeline_stats(user=Depends(get_current_user)):
    """所有流水线的统计概览"""
    async with async_session() as db:
        result = await db.execute(
            select(
                func.count(Automation.id),
                func.sum(Automation.run_count),
                func.sum(Automation.success_count),
                func.sum(Automation.fail_count),
            )
        )
        row = result.one()
        return {
            "success": True,
            "data": {
                "total_pipelines": row[0] or 0,
                "total_runs": row[1] or 0,
                "total_success": row[2] or 0,
                "total_failed": row[3] or 0,
            },
        }


# ── 核心执行引擎 ─────────────────────────────────────────────────────────────

async def _log_step(db, auto_id: int, keyword: str, step: str,
                    status: str, message: str, duration_ms: int = 0):
    """记录执行步骤日志"""
    log = AutomationLog(
        automation_id=auto_id, keyword=keyword,
        step=step, status=status, message=message,
        duration_ms=duration_ms,
    )
    db.add(log)


async def _execute_pipeline(auto_id: int):
    """执行完整流水线，带步骤日志和失败重试"""
    from core.config import settings
    from core.database import async_session
    from services.audit import log_task
    import json as _json

    audit_id = await log_task(
        task_type="automation",
        status="running",
        detail=f"自动化流水线 #{auto_id}",
        triggered_by="system",
    )

    async with async_session() as db:
        result = await db.execute(select(Automation).where(Automation.id == auto_id))
        auto = result.scalar_one_or_none()
        if not auto or not auto.is_active:
            return

        keywords = [kw.strip() for kw in auto.keywords.split(",") if kw.strip()]
        pipeline = json.loads(auto.pipeline_config) if auto.pipeline_config else {}
        max_retries = pipeline.get("max_retries", 1)

        total_success = 0
        total_fail = 0

        for keyword in keywords[:5]:
            # Step 1: Search
            t0 = time.time()
            try:
                from apis.xhs_pc_apis import XHS_Apis
                xhs = XHS_Apis()
                ok, msg, data = xhs.search_note(keyword, settings.COOKIES)
                search_ms = int((time.time() - t0) * 1000)

                if not ok:
                    await _log_step(db, auto_id, keyword, "search", "failed",
                                    f"搜索失败: {msg}", search_ms)
                    total_fail += 1
                    continue

                items = data.get("data", {}).get("items", [])[:3]
                await _log_step(db, auto_id, keyword, "search", "success",
                                f"找到 {len(items)} 条笔记", search_ms)
            except Exception as e:
                search_ms = int((time.time() - t0) * 1000)
                await _log_step(db, auto_id, keyword, "search", "failed",
                                f"搜索异常: {str(e)[:80]}", search_ms)
                total_fail += 1
                continue

            for item in items:
                note_card = item.get("note_card", {})
                title = note_card.get("display_title", "")
                desc = note_card.get("desc", "")
                note_success = True

                # Step 2: AI Rewrite（带重试）
                rewritten_title, rewritten_desc = title, desc
                if pipeline.get("rewrite", True):
                    for attempt in range(max_retries + 1):
                        t1 = time.time()
                        try:
                            from utils.rewrite import create_backend_from_env, rewrite_note
                            llm_backend = create_backend_from_env()
                            if llm_backend:
                                rw_result = rewrite_note(llm_backend, title, desc)
                                rewritten_title = rw_result.get("title", title)
                                rewritten_desc = rw_result.get("desc", desc)
                                rw_ms = int((time.time() - t1) * 1000)
                                await _log_step(db, auto_id, keyword, "rewrite", "success",
                                                f"改写完成 (尝试{attempt + 1})", rw_ms)
                                break
                        except Exception as e:
                            rw_ms = int((time.time() - t1) * 1000)
                            if attempt == max_retries:
                                await _log_step(db, auto_id, keyword, "rewrite", "failed",
                                                f"改写失败(重试{max_retries}次): {str(e)[:60]}", rw_ms)
                                note_success = False
                            else:
                                logger.warning(f"[automation] Rewrite attempt {attempt + 1} failed: {e}")

                # Step 3: Publish
                if pipeline.get("publish", False) and note_success:
                    t2 = time.time()
                    try:
                        from models.publish_task import PublishTask
                        task = PublishTask(
                            title=rewritten_title, content=rewritten_desc,
                            account_id=auto.account_id,
                            images_json=json.dumps(
                                [img.get("url", "") for img in note_card.get("image_list", [])[:9]]),
                            status="pending",
                        )
                        db.add(task)
                        await db.flush()
                        pub_ms = int((time.time() - t2) * 1000)
                        await _log_step(db, auto_id, keyword, "publish", "success",
                                        f"发布任务已创建: {rewritten_title[:30]}", pub_ms)
                    except Exception as e:
                        pub_ms = int((time.time() - t2) * 1000)
                        await _log_step(db, auto_id, keyword, "publish", "failed",
                                        f"创建发布任务失败: {str(e)[:60]}", pub_ms)
                        note_success = False

                if note_success:
                    total_success += 1
                else:
                    total_fail += 1

            # Commit after each keyword
            await db.commit()

        # Update automation stats
        auto.last_run = datetime.utcnow()
        auto.run_count += 1
        auto.success_count += total_success
        auto.fail_count += total_fail
        await db.commit()

        # Write audit summary
        await log_task(
            task_type="automation",
            status="success" if total_fail == 0 else "failed",
            detail=f"流水线 #{auto_id}: 成功={total_success}, 失败={total_fail}",
            output_summary=_json.dumps({"success": total_success, "failed": total_fail}),
        )
        logger.info(f"[automation] Pipeline #{auto_id} 完成: 成功={total_success}, 失败={total_fail}")
