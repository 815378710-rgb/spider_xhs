"""
AI 改写路由
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from core.config import settings
from core.deps import get_current_user
from loguru import logger

router = APIRouter()


class RewriteRequest(BaseModel):
    title: str
    desc: str
    style: str = "小红书爆款"
    rewrite_ratio: int = 60


class SmartRewriteRequest(BaseModel):
    title: str
    desc: str


class BatchRewriteRequest(BaseModel):
    notes: list[dict]  # [{title, desc, images, ...}]
    style: str = "小红书爆款"
    rewrite_ratio: int = 60


@router.post("/rewrite")
async def rewrite_note(req: RewriteRequest, user=Depends(get_current_user)):
    """AI rewrite a single note."""
    try:
        from utils.rewrite import create_backend, rewrite_note
        llm = settings.get_llm_config()
        backend = create_backend(llm["provider"], llm["api_key"],
                                model=llm["model"], base_url=llm["base_url"])
        if not backend:
            return {"success": False, "message": "AI 后端未配置"}
        result = rewrite_note(req.title, req.desc, backend,
                              style=req.style, ratio=req.rewrite_ratio)
        return {"success": True, "data": result}
    except Exception as e:
        logger.exception(f"改写异常: {e}")
        return {"success": False, "message": f"改写失败: {str(e)[:100]}"}


@router.post("/rewrite_smart")
async def rewrite_smart(req: SmartRewriteRequest, user=Depends(get_current_user)):
    """Smart rewrite with Agent debate."""
    try:
        from utils.rewrite import create_backend, rewrite_with_debate
        llm = settings.get_llm_config()
        backend = create_backend(llm["provider"], llm["api_key"],
                                model=llm["model"], base_url=llm["base_url"])
        if not backend:
            return {"success": False, "message": "AI 后端未配置"}
        result = rewrite_with_debate(req.title, req.desc, backend)
        return {"success": True, "data": result}
    except Exception as e:
        logger.exception(f"智能改写异常: {e}")
        return {"success": False, "message": f"智能改写失败: {str(e)[:100]}"}


@router.post("/batch_rewrite")
async def batch_rewrite(req: BatchRewriteRequest, user=Depends(get_current_user)):
    """Batch rewrite multiple notes."""
    try:
        from utils.rewrite import create_backend, rewrite_note
        llm = settings.get_llm_config()
        backend = create_backend(llm["provider"], llm["api_key"],
                                model=llm["model"], base_url=llm["base_url"])
        if not backend:
            return {"success": False, "message": "AI 后端未配置"}

        results = []
        for note in req.notes[:20]:  # max 20
            try:
                result = rewrite_note(note.get("title", ""), note.get("desc", ""), backend,
                                      style=req.style, ratio=req.rewrite_ratio)
                results.append({"success": True, "data": result, "original": note})
            except Exception as e:
                results.append({"success": False, "message": str(e), "original": note})

        return {"success": True, "data": results, "total": len(results)}
    except Exception as e:
        return {"success": False, "message": f"批量改写异常: {str(e)[:100]}"}
