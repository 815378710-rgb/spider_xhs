"""
AI 检测路由 — AI味检测 + 去AI味 + 原创度评估
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from core.config import settings
from core.deps import get_current_user

router = APIRouter()


class DetectRequest(BaseModel):
    text: str


class RemoveRequest(BaseModel):
    text: str
    provider: str = ""
    api_key: str = ""
    model: str = ""
    base_url: str = ""


class OriginalityRequest(BaseModel):
    text: str


class FullCheckRequest(BaseModel):
    text: str
    provider: str = ""
    api_key: str = ""
    model: str = ""
    base_url: str = ""


def _get_backend(req):
    """从请求或全局配置创建 LLM 后端"""
    from utils.rewrite import create_backend
    provider = req.provider or settings.LLM_PROVIDER
    api_key = req.api_key or settings.LLM_API_KEY
    model = req.model or settings.LLM_MODEL
    base_url = req.base_url or settings.LLM_BASE_URL

    if not api_key:
        return None
    kwargs = {}
    if model:
        kwargs["model"] = model
    if base_url:
        kwargs["base_url"] = base_url
    return create_backend(provider, api_key, **kwargs)


@router.post("/detect")
async def detect_ai_trace(req: DetectRequest):
    """AI味检测"""
    from utils.ai_detector import detect_ai_trace as _detect
    result = _detect(req.text)
    return {"success": True, "data": result}


@router.post("/remove")
async def remove_ai_trace(req: RemoveRequest, user=Depends(get_current_user)):
    """去AI味（调用LLM处理）"""
    from utils.ai_detector import remove_ai_trace as _remove
    backend = _get_backend(req)
    if not backend:
        return {"success": False, "message": "LLM API Key 未配置，请先在设置中配置"}

    result = _remove(req.text, backend)
    return {"success": True, "data": {"text": result}}


@router.post("/originality")
async def estimate_originality(req: OriginalityRequest):
    """原创度评估"""
    from utils.ai_detector import estimate_originality as _estimate
    result = _estimate(req.text)
    return {"success": True, "data": result}


@router.post("/full")
async def full_ai_check(req: FullCheckRequest, user=Depends(get_current_user)):
    """完整检测：AI味 + 原创度"""
    from utils.ai_detector import detect_ai_trace as _detect, estimate_originality as _estimate
    detect_result = _detect(req.text)
    originality_result = _estimate(req.text)

    return {
        "success": True,
        "data": {
            "ai_trace": detect_result,
            "originality": originality_result,
        },
    }
