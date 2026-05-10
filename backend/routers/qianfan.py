"""
千帆分销路由
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from core.config import settings
from core.deps import get_current_user

router = APIRouter()


class DistributorSearchRequest(BaseModel):
    page: int = 1
    category: str = ""


@router.get("/categories")
async def get_categories(user=Depends(get_current_user)):
    try:
        from apis.xhs_qianfan_apis import QianFanAPI
        api = QianFanAPI()
        ok, msg, data = api.get_all_categories(settings.COOKIES)
        return {"success": ok, "data": data if ok else [], "message": msg}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/search")
async def search_distributors(req: DistributorSearchRequest, user=Depends(get_current_user)):
    try:
        from apis.xhs_qianfan_apis import QianFanAPI
        api = QianFanAPI()
        ok, msg, data = api.get_user_by_page(req.page, settings.COOKIES, category=req.category)
        return {"success": ok, "data": data if ok else [], "message": msg}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/{user_id}/detail")
async def distributor_detail(user_id: str, user=Depends(get_current_user)):
    try:
        from apis.xhs_qianfan_apis import QianFanAPI
        api = QianFanAPI()
        ok, msg, data = api.get_user_detail(user_id, settings.COOKIES)
        return {"success": ok, "data": data if ok else {}, "message": msg}
    except Exception as e:
        return {"success": False, "message": str(e)}
