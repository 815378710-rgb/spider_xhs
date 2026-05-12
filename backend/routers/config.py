"""
配置管理路由 — Cookie 按用户隔离，LLM 配置全局
"""
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from core.config import settings
from core.deps import get_current_user
from core.database import async_session

router = APIRouter()


class ConfigUpdate(BaseModel):
    cookies: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None


@router.get("")
async def get_config(user=Depends(get_current_user)):
    """Get configuration. Cookie is per-user; LLM is global."""
    user_id = int(user["sub"])
    user_cookie = ""
    async with async_session() as db:
        from models.user import User
        result = await db.execute(select(User).where(User.id == user_id))
        u = result.scalar_one_or_none()
        if u:
            user_cookie = u.cookie or ""

    return {
        "cookies_configured": bool(user_cookie),
        "cookies": user_cookie,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_api_key": "",  # Don't expose API key to users
        "llm_model": settings.LLM_MODEL,
        "llm_configured": bool(settings.LLM_API_KEY),
        "llm_base_url": settings.LLM_BASE_URL,
    }


@router.get("/admin")
async def get_admin_config(user=Depends(get_current_user)):
    """Admin gets full config including API key."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    user_id = int(user["sub"])
    user_cookie = ""
    async with async_session() as db:
        from models.user import User
        result = await db.execute(select(User).where(User.id == user_id))
        u = result.scalar_one_or_none()
        if u:
            user_cookie = u.cookie or ""

    return {
        "cookies_configured": bool(user_cookie),
        "cookies": user_cookie,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_api_key": settings.LLM_API_KEY,
        "llm_model": settings.LLM_MODEL,
        "llm_configured": bool(settings.LLM_API_KEY),
        "llm_base_url": settings.LLM_BASE_URL,
    }


@router.post("")
async def update_config(req: ConfigUpdate, user=Depends(get_current_user)):
    """Update configuration. Cookie per-user; LLM global."""
    user_id = int(user["sub"])

    # Handle cookie update (per-user)
    if req.cookies is not None:
        cookies_str = req.cookies.strip().replace('\n', '').replace('\r', '')
        cookies_str = re.sub(r'\s*;\s*', '; ', cookies_str)
        cookies_str = re.sub(r'\s+', ' ', cookies_str).strip()

        if cookies_str and '=' in cookies_str:
            async with async_session() as db:
                from models.user import User
                result = await db.execute(select(User).where(User.id == user_id))
                u = result.scalar_one_or_none()
                if u:
                    u.cookie = cookies_str
        elif cookies_str == "":
            # Allow clearing cookie
            async with async_session() as db:
                from models.user import User
                result = await db.execute(select(User).where(User.id == user_id))
                u = result.scalar_one_or_none()
                if u:
                    u.cookie = ""
        else:
            raise HTTPException(status_code=400, detail="Cookie 格式无效，请检查后重试")

    # Handle LLM config (global, admin only)
    if user.get("role") == "admin":
        update_kwargs = {}
        if req.llm_provider is not None:
            update_kwargs["LLM_PROVIDER"] = req.llm_provider
        if req.llm_api_key is not None:
            update_kwargs["LLM_API_KEY"] = req.llm_api_key
        if req.llm_model is not None:
            update_kwargs["LLM_MODEL"] = req.llm_model
        if req.llm_base_url is not None:
            update_kwargs["LLM_BASE_URL"] = req.llm_base_url
        if update_kwargs:
            settings.update(**update_kwargs)

    return {"success": True, "message": "配置已更新"}


@router.post("/test-cookie")
async def test_cookie(user=Depends(get_current_user)):
    """Test if current user's cookie is valid."""
    from apis.xhs_pc_apis import XHS_Apis
    user_id = int(user["sub"])

    async with async_session() as db:
        from models.user import User
        result = await db.execute(select(User).where(User.id == user_id))
        u = result.scalar_one_or_none()
        cookies_str = u.cookie if u else ""

    if not cookies_str:
        return {"success": False, "message": "Cookie 未配置，请先提交你的 Cookie"}
    try:
        xhs = XHS_Apis()
        success, msg, data = xhs.get_user_self_info(cookies_str)
        if success:
            nickname = data.get("data", {}).get("basic_info", {}).get("nickname", "未知")
            return {"success": True, "message": f"Cookie 有效，用户: {nickname}"}
        return {"success": False, "message": f"Cookie 无效: {msg}"}
    except Exception as e:
        return {"success": False, "message": f"测试失败: {str(e)[:100]}"}
