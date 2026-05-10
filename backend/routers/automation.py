"""
自动化流水线路由 — 全自动：搜索→改写→图片处理→发布
"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, func
from core.deps import get_current_user
from core.database import async_session
from models.automation import Automation
from loguru import logger

router = APIRouter()


class AutomationCreate(BaseModel):
    name: str = ""
    keywords: str = ""  # comma-separated
    schedule_cron: str = "0 9 * * *"  # default daily at 9am
    pipeline_config: str = "{}"
    account_id: Optional[int] = None


class AutomationUpdate(BaseModel):
    name: Optional[str] = None
    keywords: Optional[str] = None
    schedule_cron: Optional[str] = None
    pipeline_config: Optional[str] = None
    is_active: Optional[bool] = None


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
                    "pipeline_config": a.pipeline_config, "last_run": str(a.last_run) if a.last_run else None,
                    "next_run": str(a.next_run) if a.next_run else None,
                    "run_count": a.run_count, "created_at": str(a.created_at),
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
        return {"success": True, "message": "已更新"}


@router.delete("/{auto_id}")
async def delete_automation(auto_id: int, user=Depends(get_current_user)):
    from sqlalchemy import delete as sql_delete
    async with async_session() as db:
        await db.execute(sql_delete(Automation).where(Automation.id == auto_id))
        await db.commit()
        return {"success": True, "message": "已删除"}


@router.post("/{auto_id}/run")
async def run_automation(auto_id: int, user=Depends(get_current_user)):
    """Manually trigger an automation pipeline."""
    async with async_session() as db:
        result = await db.execute(select(Automation).where(Automation.id == auto_id))
        auto = result.scalar_one_or_none()
        if not auto:
            return {"success": False, "message": "流水线不存在"}
    import asyncio
    asyncio.create_task(_execute_pipeline(auto_id))
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
        return {"success": True, "is_active": auto.is_active}


async def _execute_pipeline(auto_id: int):
    """Execute the full automation pipeline."""
    from core.config import settings
    from core.database import async_session
    async with async_session() as db:
        result = await db.execute(select(Automation).where(Automation.id == auto_id))
        auto = result.scalar_one_or_none()
        if not auto or not auto.is_active:
            return

        keywords = [kw.strip() for kw in auto.keywords.split(",") if kw.strip()]
        pipeline = json.loads(auto.pipeline_config) if auto.pipeline_config else {}

        for keyword in keywords[:5]:  # max 5 keywords per run
            try:
                # Step 1: Search
                from apis.xhs_pc_apis import XHS_Apis
                xhs = XHS_Apis()
                ok, msg, data = xhs.search_note(keyword, settings.COOKIES)
                if not ok:
                    logger.warning(f"[automation] Search failed for '{keyword}': {msg}")
                    continue

                items = data.get("data", {}).get("items", [])[:3]  # top 3 results
                for item in items:
                    note_card = item.get("note_card", {})
                    title = note_card.get("display_title", "")
                    desc = note_card.get("desc", "")

                    # Step 2: AI Rewrite
                    rewritten_title, rewritten_desc = title, desc
                    if pipeline.get("rewrite", True):
                        try:
                            from utils.rewrite import create_backend, rewrite_note
                            llm = settings.get_llm_config()
                            backend = create_backend(llm["provider"], llm["api_key"],
                                                    model=llm["model"], base_url=llm["base_url"])
                            if backend:
                                result = rewrite_note(backend, title, desc)
                                rewritten_title = result.get("title", title)
                                rewritten_desc = result.get("desc", desc)
                        except Exception as e:
                            logger.warning(f"[automation] Rewrite failed: {e}")

                    # Step 3: Publish (if enabled)
                    if pipeline.get("publish", False):
                        from models.publish_task import PublishTask
                        task = PublishTask(
                            title=rewritten_title, content=rewritten_desc,
                            account_id=auto.account_id,
                            images_json=json.dumps([img.get("url", "") for img in note_card.get("image_list", [])[:9]]),
                            status="running",
                        )
                        db.add(task)
                        await db.flush()

                auto.last_run = datetime.utcnow()
                auto.run_count += 1
                await db.commit()
            except Exception as e:
                logger.exception(f"[automation] Pipeline error for '{keyword}': {e}")
