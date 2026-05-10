"""
通知系统路由
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, update
from core.deps import get_current_user
from core.database import async_session
from models.notification import Notification

router = APIRouter()


@router.get("")
async def list_notifications(page: int = 1, page_size: int = 20, user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(
            select(Notification).order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
        notis = result.scalars().all()
        total = (await db.execute(select(func.count()).select_from(Notification))).scalar() or 0
        unread = (await db.execute(select(func.count()).select_from(Notification).where(Notification.is_read == False))).scalar() or 0
        return {
            "success": True, "total": total, "unread": unread,
            "data": [
                {"id": n.id, "title": n.title, "message": n.message,
                 "noti_type": n.noti_type, "is_read": n.is_read,
                 "link": n.link, "created_at": str(n.created_at)}
                for n in notis
            ],
        }


@router.post("/{noti_id}/read")
async def mark_read(noti_id: int, user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(Notification).where(Notification.id == noti_id))
        noti = result.scalar_one_or_none()
        if noti:
            noti.is_read = True
            await db.commit()
        return {"success": True}


@router.post("/read-all")
async def mark_all_read(user=Depends(get_current_user)):
    async with async_session() as db:
        await db.execute(update(Notification).where(Notification.is_read == False).values(is_read=True))
        await db.commit()
        return {"success": True}


async def create_notification(title: str, message: str, noti_type: str = "info", link: str = ""):
    """Helper to create a notification (called from services)."""
    async with async_session() as db:
        noti = Notification(title=title, message=message, noti_type=noti_type, link=link)
        db.add(noti)
        await db.commit()
