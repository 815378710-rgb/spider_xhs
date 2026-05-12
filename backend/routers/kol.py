"""
蒲公英 KOL 搜索路由
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from core.config import settings
from core.deps import get_current_user

router = APIRouter()


class KOLSearchRequest(BaseModel):
    page: int = 1
    category: str = ""


@router.get("/categories")
async def get_categories(user=Depends(get_current_user)):
    try:
        from apis.xhs_pugongying_apis import PuGongYingAPI
        api = PuGongYingAPI()
        ok, msg, data = api.get_all_categories(settings.COOKIES)
        if isinstance(data, str):
            return {"success": False, "message": f"蒲公英API返回异常: {data[:100]}", "data": []}
        return {"success": ok, "data": data if ok else [], "message": msg}
    except Exception as e:
        return {"success": False, "message": str(e), "data": []}


@router.post("/search")
async def search_kol(req: KOLSearchRequest, user=Depends(get_current_user)):
    try:
        from apis.xhs_pugongying_apis import PuGongYingAPI
        api = PuGongYingAPI()
        ok, msg, data = api.get_user_by_page(req.page, settings.COOKIES, contentTag=req.category)
        return {"success": ok, "data": data if ok else [], "message": msg}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{user_id}/profile")
async def kol_profile(user_id: str, user=Depends(get_current_user)):
    try:
        from apis.xhs_pugongying_apis import PuGongYingAPI
        api = PuGongYingAPI()
        ok, msg, data = api.get_user_detail(user_id, settings.COOKIES)
        return {"success": ok, "data": data if ok else {}, "message": msg}
    except Exception as e:
        return {"success": False, "message": str(e)}


class InviteRequest(BaseModel):
    user_id: str
    product: str = ""
    timeline: str = ""
    contact: str = ""
    content: str = ""


@router.post("/invite")
async def invite_kol(req: InviteRequest, user=Depends(get_current_user)):
    try:
        from apis.xhs_pugongying_apis import PuGongYingAPI
        api = PuGongYingAPI()
        ok, msg, data = api.send_invite(req.user_id, settings.COOKIES,
                                         product=req.product, timeline=req.timeline,
                                         contact=req.contact, content=req.content)
        return {"success": ok, "message": msg}
    except Exception as e:
        return {"success": False, "message": str(e)}
