"""
千帆分销路由
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from core.config import settings
from core.deps import get_current_user
from loguru import logger

router = APIRouter()


class DistributorSearchRequest(BaseModel):
    page: int = 1
    category: str = ""


@router.get("/categories")
async def get_categories(user=Depends(get_current_user)):
    try:
        from apis.xhs_qianfan_apis import QianFanAPI
        api = QianFanAPI()
        data = api.get_all_categories(settings.COOKIES)
        if isinstance(data, str):
            return {"success": False, "message": f"千帆API返回异常: {data[:100]}", "data": []}
        return {"success": True, "data": data, "message": "ok"}
    except Exception as e:
        logger.warning(f"[qianfan] categories error: {e}")
        return {"success": False, "message": str(e), "data": []}


@router.post("/search")
async def search_distributors(req: DistributorSearchRequest, user=Depends(get_current_user)):
    try:
        from apis.xhs_qianfan_apis import QianFanAPI
        api = QianFanAPI()
        # QianFan API requires categories first, then uses them for search
        try:
            categories = api.get_all_categories(settings.COOKIES)
        except Exception as e:
            return {"success": False, "message": f"获取分类失败: {str(e)[:100]}", "data": []}

        if not isinstance(categories, list) or len(categories) == 0:
            return {"success": False, "message": "无可用分类数据", "data": []}

        # Use first category as default if no category specified
        choice = req.category if req.category else ""
        user_list, total = api.get_user_by_page(choice, categories, req.page, settings.COOKIES)
        return {"success": True, "data": user_list, "total": total, "message": "ok"}
    except Exception as e:
        logger.warning(f"[qianfan] search error: {e}")
        return {"success": False, "message": str(e)[:200], "data": []}


@router.get("/{user_id}/detail")
async def distributor_detail(user_id: str, user=Depends(get_current_user)):
    try:
        from apis.xhs_qianfan_apis import QianFanAPI
        api = QianFanAPI()
        ok, msg, data = api.get_user_detail(user_id, settings.COOKIES)
        return {"success": ok, "data": data if ok else {}, "message": msg}
    except Exception as e:
        return {"success": False, "message": str(e)}
