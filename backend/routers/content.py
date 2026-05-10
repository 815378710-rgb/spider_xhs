"""
内容素材库路由
"""
import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, update, delete, func
from core.deps import get_current_user
from core.database import async_session
from models.note import Note
from models.tag import Tag, NoteTag

router = APIRouter()


class NoteSaveToLibrary(BaseModel):
    note_id: str
    tags: list[str] = []


class TagCreate(BaseModel):
    name: str
    color: str = "#1890ff"


@router.get("")
async def list_notes(page: int = 1, page_size: int = 20, tag: str = "", user=Depends(get_current_user)):
    async with async_session() as db:
        q = select(Note).where(Note.in_library == True)
        if tag:
            q = q.where(Note.library_tags.contains(tag))
        q = q.order_by(Note.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(q)
        notes = result.scalars().all()
        count_q = select(func.count()).select_from(Note).where(Note.in_library == True)
        total = (await db.execute(count_q)).scalar() or 0
        return {
            "success": True, "total": total,
            "data": [
                {
                    "id": n.id, "note_id": n.note_id, "title": n.title, "desc": n.desc,
                    "note_type": n.note_type, "url": n.url, "author_name": n.author_name,
                    "likes": n.likes, "collects": n.collects, "comments": n.comments,
                    "images_json": n.images_json, "library_tags": n.library_tags,
                    "rewritten_title": n.rewritten_title, "rewritten_desc": n.rewritten_desc,
                    "created_at": str(n.created_at),
                } for n in notes
            ],
        }


@router.post("/save")
async def save_to_library(req: NoteSaveToLibrary, user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(Note).where(Note.note_id == req.note_id))
        note = result.scalar_one_or_none()
        if not note:
            return {"success": False, "message": "笔记不存在"}
        note.in_library = True
        note.library_tags = ",".join(req.tags)
        await db.commit()
        return {"success": True, "message": "已保存到素材库"}


@router.delete("/{note_id}")
async def remove_from_library(note_id: int, user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(Note).where(Note.id == note_id))
        note = result.scalar_one_or_none()
        if note:
            note.in_library = False
            await db.commit()
        return {"success": True, "message": "已从素材库移除"}


class BatchDeleteRequest(BaseModel):
    ids: list[int]


@router.post("/batch-delete")
async def batch_delete(req: BatchDeleteRequest, user=Depends(get_current_user)):
    async with async_session() as db:
        for nid in req.ids:
            result = await db.execute(select(Note).where(Note.id == nid))
            note = result.scalar_one_or_none()
            if note:
                note.in_library = False
        await db.commit()
        return {"success": True, "message": f"已移除 {len(req.ids)} 条笔记"}


# ── Tags ──────────────────────────────────────────────────────────────────────

@router.get("/tags")
async def list_tags(user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(Tag).order_by(Tag.name))
        tags = result.scalars().all()
        return {"success": True, "data": [{"id": t.id, "name": t.name, "color": t.color} for t in tags]}


@router.post("/tags")
async def create_tag(req: TagCreate, user=Depends(get_current_user)):
    async with async_session() as db:
        tag = Tag(name=req.name, color=req.color)
        db.add(tag)
        await db.commit()
        return {"success": True, "id": tag.id}


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int, user=Depends(get_current_user)):
    async with async_session() as db:
        await db.execute(delete(NoteTag).where(NoteTag.tag_id == tag_id))
        await db.execute(delete(Tag).where(Tag.id == tag_id))
        await db.commit()
        return {"success": True}


@router.post("/export")
async def export_notes(body: dict = {}, user=Depends(get_current_user)):
    """Export library notes as JSON."""
    async with async_session() as db:
        result = await db.execute(select(Note).where(Note.in_library == True).order_by(Note.created_at.desc()))
        notes = result.scalars().all()
        data = [
            {"title": n.title, "desc": n.desc, "url": n.url, "author": n.author_name,
             "likes": n.likes, "tags": n.library_tags}
            for n in notes
        ]
        return {"success": True, "data": data, "total": len(data)}
