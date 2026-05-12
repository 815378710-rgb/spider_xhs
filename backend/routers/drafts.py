"""
草稿工作台路由
"""
import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, func
from core.deps import get_current_user
from core.database import async_session
from models.draft import Draft

router = APIRouter()


class DraftCreate(BaseModel):
    title: str = ""
    content: str = ""
    images_json: str = "[]"
    tags_json: str = "[]"
    source_note_id: str = ""


class DraftUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    images_json: Optional[str] = None
    tags_json: Optional[str] = None
    status: Optional[str] = None


@router.get("")
async def list_drafts(page: int = 1, page_size: int = 20, user=Depends(get_current_user)):
    async with async_session() as db:
        q = select(Draft).order_by(Draft.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(q)
        drafts = result.scalars().all()
        count_q = select(func.count()).select_from(Draft)
        total = (await db.execute(count_q)).scalar() or 0
        return {
            "success": True, "total": total,
            "data": [
                {
                    "id": d.id, "title": d.title, "content": d.content,
                    "images_json": d.images_json, "tags_json": d.tags_json,
                    "source_note_id": d.source_note_id, "status": d.status,
                    "created_at": str(d.created_at), "updated_at": str(d.updated_at),
                } for d in drafts
            ],
        }


@router.post("")
async def create_draft(req: DraftCreate, user=Depends(get_current_user)):
    async with async_session() as db:
        try:
            draft = Draft(
                title=req.title, content=req.content,
                images_json=req.images_json, tags_json=req.tags_json,
                source_note_id=req.source_note_id,
            )
            db.add(draft)
            await db.flush()
            await db.commit()
            return {"success": True, "id": draft.id, "message": "草稿已创建"}
        except Exception as e:
            await db.rollback()
            from loguru import logger
            logger.error(f"创建草稿失败: {e}")
            return {"success": False, "message": f"创建草稿失败: {str(e)[:100]}"}


@router.put("/{draft_id}")
async def update_draft(draft_id: int, req: DraftUpdate, user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(Draft).where(Draft.id == draft_id))
        draft = result.scalar_one_or_none()
        if not draft:
            return {"success": False, "message": "草稿不存在"}
        if req.title is not None:
            draft.title = req.title
        if req.content is not None:
            draft.content = req.content
        if req.images_json is not None:
            draft.images_json = req.images_json
        if req.tags_json is not None:
            draft.tags_json = req.tags_json
        if req.status is not None:
            draft.status = req.status
        await db.commit()
        return {"success": True, "message": "草稿已更新"}


@router.delete("/{draft_id}")
async def delete_draft(draft_id: int, user=Depends(get_current_user)):
    async with async_session() as db:
        await db.execute(select(Draft).where(Draft.id == draft_id))
        from sqlalchemy import delete as sql_delete
        await db.execute(sql_delete(Draft).where(Draft.id == draft_id))
        await db.commit()
        return {"success": True, "message": "草稿已删除"}


@router.post("/from-library/{note_id}")
async def copy_from_library(note_id: int, user=Depends(get_current_user)):
    """Deep copy a library note into drafts."""
    from models.note import Note
    async with async_session() as db:
        result = await db.execute(select(Note).where(Note.id == note_id))
        note = result.scalar_one_or_none()
        if not note:
            return {"success": False, "message": "素材不存在"}
        title = note.rewritten_title or note.title
        content = note.rewritten_desc or note.desc
        draft = Draft(
            title=title, content=content,
            images_json=note.images_json, tags_json=note.tags_json,
            source_note_id=note.note_id,
        )
        db.add(draft)
        await db.flush()
        await db.commit()
        return {"success": True, "id": draft.id, "message": "已复制到草稿"}
