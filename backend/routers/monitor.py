"""
竞品监控路由
"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, func, delete as sql_delete
from core.deps import get_current_user
from core.database import async_session
from models.monitor import MonitorItem, MonitorSnapshot

router = APIRouter()


class MonitorCreate(BaseModel):
    name: str = ""
    monitor_type: str = "keyword"  # keyword, account, brand, url
    target: str = ""
    interval_minutes: int = 60


@router.get("")
async def list_monitors(user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(MonitorItem).order_by(MonitorItem.created_at.desc()))
        items = result.scalars().all()
        return {
            "success": True,
            "data": [
                {"id": m.id, "name": m.name, "monitor_type": m.monitor_type,
                 "target": m.target, "interval_minutes": m.interval_minutes,
                 "is_active": m.is_active, "last_check": str(m.last_check) if m.last_check else None,
                 "created_at": str(m.created_at)} for m in items
            ],
        }


@router.post("")
async def create_monitor(req: MonitorCreate, user=Depends(get_current_user)):
    async with async_session() as db:
        item = MonitorItem(name=req.name, monitor_type=req.monitor_type,
                           target=req.target, interval_minutes=req.interval_minutes)
        db.add(item)
        await db.flush()
        await db.commit()
        return {"success": True, "id": item.id}


@router.delete("/{item_id}")
async def delete_monitor(item_id: int, user=Depends(get_current_user)):
    async with async_session() as db:
        await db.execute(sql_delete(MonitorSnapshot).where(MonitorSnapshot.item_id == item_id))
        await db.execute(sql_delete(MonitorItem).where(MonitorItem.id == item_id))
        await db.commit()
        return {"success": True}


@router.post("/{item_id}/toggle")
async def toggle_monitor(item_id: int, user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(MonitorItem).where(MonitorItem.id == item_id))
        item = result.scalar_one_or_none()
        if item:
            item.is_active = not item.is_active
            await db.commit()
        return {"success": True, "is_active": item.is_active if item else False}


@router.get("/{item_id}/snapshots")
async def list_snapshots(item_id: int, limit: int = 50, user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(
            select(MonitorSnapshot).where(MonitorSnapshot.item_id == item_id)
            .order_by(MonitorSnapshot.created_at.desc()).limit(limit)
        )
        snapshots = result.scalars().all()
        return {
            "success": True,
            "data": [
                {"id": s.id, "data_json": s.data_json, "created_at": str(s.created_at)}
                for s in snapshots
            ],
        }


@router.post("/{item_id}/check")
async def check_monitor(item_id: int, user=Depends(get_current_user)):
    """Manually trigger a monitoring check."""
    async with async_session() as db:
        result = await db.execute(select(MonitorItem).where(MonitorItem.id == item_id))
        item = result.scalar_one_or_none()
        if not item:
            return {"success": False, "message": "监控项不存在"}

        try:
            from core.config import settings
            from apis.xhs_pc_apis import XHS_Apis
            xhs = XHS_Apis()
            if item.monitor_type == "keyword":
                ok, msg, data = xhs.search_note(item.target, settings.COOKIES)
                snapshot_data = {"items": data.get("data", {}).get("items", [])[:10]} if ok else {"error": msg}
            else:
                snapshot_data = {"message": "暂只支持关键词监控"}

            snap = MonitorSnapshot(item_id=item.id, data_json=json.dumps(snapshot_data, ensure_ascii=False))
            db.add(snap)
            item.last_check = datetime.utcnow()
            await db.commit()
            return {"success": True, "data": snapshot_data}
        except Exception as e:
            return {"success": False, "message": str(e)}


@router.delete("/{item_id}/snapshots")
async def clear_snapshots(item_id: int, user=Depends(get_current_user)):
    async with async_session() as db:
        await db.execute(sql_delete(MonitorSnapshot).where(MonitorSnapshot.item_id == item_id))
        await db.commit()
        return {"success": True}
