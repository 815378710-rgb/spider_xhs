"""
Cookie 池管理路由
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from core.config import settings
from core.deps import get_current_user

router = APIRouter()


@router.get("")
async def cookie_pool_info(user=Depends(get_current_user)):
    """Get cookie pool overview."""
    try:
        from xhs_utils.xhs_cookie import XhsCookie
        pool = XhsCookie()
        info = pool.get_pool_info()
    except Exception:
        info = {"pool": [], "total": 0, "valid": 0}
    # Include active cookie
    active_a1 = ""
    if settings.COOKIES:
        try:
            from xhs_utils.cookie_util import trans_cookies
            active_a1 = trans_cookies(settings.COOKIES).get("a1", "")
        except Exception:
            pass
    info["active_cookie"] = {"a1": active_a1, "is_active": True}
    return {"success": True, "data": info}


@router.post("/validate")
async def cookie_pool_validate(user=Depends(get_current_user)):
    try:
        from xhs_utils.xhs_cookie import XhsCookie
        pool = XhsCookie()
        results = pool.validate_all()
        return {"success": True, "data": results}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/auto-update")
async def cookie_pool_auto_update(user=Depends(get_current_user)):
    try:
        from xhs_utils.xhs_cookie import XhsCookie
        pool = XhsCookie()
        results = pool.auto_update()
        return {"success": True, "data": results}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/use-best")
async def cookie_pool_use_best(body: dict = {}, user=Depends(get_current_user)):
    try:
        from xhs_utils.xhs_cookie import XhsCookie
        pool = XhsCookie()
        index = body.get("index")
        if index is not None and 0 <= index < len(pool.pool):
            settings.update(COOKIES=pool.pool[index]["cookies_str"])
            return {"success": True, "message": f"已应用 Cookie [{index}]"}
        best = pool.get_best_cookie()
        if not best:
            return {"success": False, "message": "Cookie 池中没有有效 Cookie"}
        settings.update(COOKIES=best)
        return {"success": True, "message": "已应用池中最佳 Cookie"}
    except Exception as e:
        return {"success": False, "message": str(e)}


class CookieAddRequest(BaseModel):
    cookies: str = ""
    username: str = "手动添加"


@router.post("/add")
async def cookie_pool_add(req: CookieAddRequest, user=Depends(get_current_user)):
    cookies_str = req.cookies.strip()
    if not cookies_str:
        return {"success": False, "message": "请输入 Cookie"}
    try:
        from xhs_utils.xhs_cookie import XhsCookie
        pool = XhsCookie()
        pool.add_cookie(cookies_str, username=req.username, is_valid=True)
        return {"success": True, "message": f"已添加到 Cookie 池（共 {len(pool.pool)} 条）"}
    except Exception as e:
        return {"success": False, "message": str(e)}


class CookieRemoveRequest(BaseModel):
    index: int = None
    a1: str = None


@router.post("/remove")
async def cookie_pool_remove(req: CookieRemoveRequest, user=Depends(get_current_user)):
    if req.index is None and not req.a1:
        return {"success": False, "message": "请指定 index 或 a1"}
    try:
        from xhs_utils.xhs_cookie import XhsCookie
        pool = XhsCookie()
        pool.remove_cookie(index=req.index, a1=req.a1)
        return {"success": True, "message": f"已移除（剩余 {len(pool.pool)} 条）"}
    except Exception as e:
        return {"success": False, "message": str(e)}
