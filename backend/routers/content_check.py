"""
内容检测路由 — 违禁词检测 + 全面内容审查
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from core.deps import get_current_user

router = APIRouter()


class BannedWordsRequest(BaseModel):
    text: str


class FullCheckRequest(BaseModel):
    title: str = ""
    content: str = ""


@router.post("/banned-words")
async def check_banned_words(req: BannedWordsRequest, user=Depends(get_current_user)):
    """检测文本中的违禁词"""
    from utils.banned_words import check_banned_words as _check, suggest_replacement
    result = _check(req.text)
    suggestions = suggest_replacement(req.text)
    return {
        "success": True,
        "data": {
            **result,
            "suggestions": suggestions["suggestions"],
            "cleaned_text": suggestions["cleaned_text"],
        },
    }


@router.post("/full")
async def full_content_check(req: FullCheckRequest, user=Depends(get_current_user)):
    """全面检测：违禁词 + 敏感词 + 广告法风险"""
    from utils.banned_words import check_banned_words as _check, suggest_replacement
    text = f"{req.title} {req.content}".strip()

    banned_result = _check(text)
    suggestions = suggest_replacement(text)

    return {
        "success": True,
        "data": {
            "banned_words": banned_result,
            "suggestions": suggestions["suggestions"],
            "cleaned_text": suggestions["cleaned_text"],
            "summary": {
                "total_issues": banned_result["total"],
                "critical": sum(1 for f in banned_result["found"] if f["severity"] == "critical"),
                "warning": sum(1 for f in banned_result["found"] if f["severity"] == "warning"),
                "safety_score": banned_result["score"],
            },
        },
    }
