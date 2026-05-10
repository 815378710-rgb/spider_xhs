"""
配置管理路由
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from core.config import settings
from core.deps import get_current_user

router = APIRouter()


class ConfigUpdate(BaseModel):
    cookies: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None


@router.get("")
async def get_config(user=Depends(get_current_user)):
    """Get current configuration."""
    return {
        "cookies_configured": bool(settings.COOKIES),
        "cookies": settings.COOKIES,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_api_key": settings.LLM_API_KEY,
        "llm_model": settings.LLM_MODEL,
        "llm_configured": bool(settings.LLM_API_KEY),
        "llm_base_url": settings.LLM_BASE_URL,
    }


@router.post("")
async def update_config(req: ConfigUpdate, user=Depends(get_current_user)):
    """Update configuration."""
    update_kwargs = {}
    if req.cookies is not None:
        update_kwargs["COOKIES"] = req.cookies
    if req.llm_provider is not None:
        update_kwargs["LLM_PROVIDER"] = req.llm_provider
    if req.llm_api_key is not None:
        update_kwargs["LLM_API_KEY"] = req.llm_api_key
    if req.llm_model is not None:
        update_kwargs["LLM_MODEL"] = req.llm_model
    if req.llm_base_url is not None:
        update_kwargs["LLM_BASE_URL"] = req.llm_base_url
    settings.update(**update_kwargs)
    return {"success": True, "message": "配置已更新"}


@router.post("/test-cookie")
async def test_cookie(user=Depends(get_current_user)):
    """Test if current cookie is valid."""
    from apis.xhs_pc_apis import XHS_Apis
    cookies_str = settings.COOKIES
    if not cookies_str:
        return {"success": False, "message": "Cookie 未配置"}
    try:
        xhs = XHS_Apis()
        success, msg, data = xhs.get_user_self_info(cookies_str)
        if success:
            nickname = data.get("data", {}).get("basic_info", {}).get("nickname", "未知")
            return {"success": True, "message": f"Cookie 有效，用户: {nickname}"}
        return {"success": False, "message": f"Cookie 无效: {msg}"}
    except Exception as e:
        return {"success": False, "message": f"测试失败: {str(e)}"}


@router.post("/test-ai")
async def test_ai(body: dict = {}, user=Depends(get_current_user)):
    """Test AI model connection."""
    from utils.rewrite import create_backend
    provider = body.get("provider", settings.LLM_PROVIDER)
    api_key = body.get("api_key", settings.LLM_API_KEY)
    model = body.get("model", settings.LLM_MODEL)
    base_url = body.get("base_url", settings.LLM_BASE_URL)

    if not api_key:
        return {"success": False, "message": "API Key 未配置"}
    try:
        kwargs = {}
        if model:
            kwargs["model"] = model
        if base_url:
            kwargs["base_url"] = base_url
        backend = create_backend(provider, api_key, **kwargs)
        if not backend:
            return {"success": False, "message": "创建后端失败"}
        result = backend.chat("你是一个助手", "请回复'连接成功'两个字")
        return {"success": True, "message": f"{backend.name} 连接成功！模型回复: {result[:50]}"}
    except Exception as e:
        return {"success": False, "message": f"{provider}/{model} 连接失败: {str(e)[:100]}"}


@router.post("/models")
async def list_models(body: dict = {}, user=Depends(get_current_user)):
    """List available models from provider API."""
    import requests as req
    provider = body.get("provider", "mimo")
    api_key = body.get("api_key", "")
    base_url = body.get("base_url", "")

    if not api_key:
        return {"success": False, "message": "API Key 未配置", "models": []}

    if provider == "mimo":
        default_base = "https://token-plan-cn.xiaomimimo.com/v1"
        headers = {"api-key": api_key}
    elif provider == "deepseek":
        default_base = "https://api.deepseek.com/v1"
        headers = {"Authorization": f"Bearer {api_key}"}
    else:
        default_base = base_url or ""
        headers = {"Authorization": f"Bearer {api_key}"}

    target_url = (base_url or default_base).rstrip("/") + "/models"
    try:
        resp = req.request("GET", target_url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        models = [{"id": m.get("id", ""), "name": m.get("id", "")} for m in data.get("data", []) if m.get("id")]
        # Filter out TTS models for mimo
        if provider == "mimo":
            models = [m for m in models if "tts" not in m["id"]]
        return {"success": True, "models": models}
    except Exception:
        return {"success": True, "models": [], "message": "自动获取失败，使用默认列表"}
