"""
搜索路由
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from core.config import settings
from core.deps import get_current_user

router = APIRouter()


class SearchNoteRequest(BaseModel):
    query: str
    sort_type: int = 0  # 0=综合 1=最新 2=最热
    note_type: int = 0  # 0=全部 1=视频 2=图文
    note_time: int = 0  # 0=全部 1=一天 2=一周 3=半年
    page: int = 1


class SearchUserRequest(BaseModel):
    query: str
    page: int = 1


@router.post("/notes")
async def search_notes(req: SearchNoteRequest, user=Depends(get_current_user)):
    """Search XHS notes."""
    try:
        from apis.xhs_pc_apis import XHS_Apis
        xhs = XHS_Apis()
        success, msg, data = xhs.search_note(
            req.query, settings.COOKIES,
            page=req.page, sort_type_choice=req.sort_type,
            note_type=req.note_type, note_time=req.note_time,
        )
        if not success:
            return {"success": False, "message": f"搜索失败: {msg}"}

        items = data.get("data", {}).get("items", [])
        results = []
        for item in items:
            note_card = item.get("note_card", {})
            results.append({
                "note_id": item.get("id", ""),
                "title": note_card.get("display_title", ""),
                "desc": note_card.get("desc", ""),
                "note_type": note_card.get("type", ""),
                "author": note_card.get("user", {}).get("nickname", ""),
                "author_id": note_card.get("user", {}).get("user_id", ""),
                "likes": note_card.get("interact_info", {}).get("liked_count", "0"),
                "images": [img.get("url", "") for img in note_card.get("image_list", [])],
                "url": f"https://www.xiaohongshu.com/explore/{item.get('id', '')}",
            })
        return {"success": True, "data": results, "total": len(results)}
    except Exception as e:
        return {"success": False, "message": f"搜索异常: {str(e)[:100]}"}


@router.post("/users")
async def search_users(req: SearchUserRequest, user=Depends(get_current_user)):
    """Search XHS users."""
    try:
        from apis.xhs_pc_apis import XHS_Apis
        xhs = XHS_Apis()
        success, msg, data = xhs.search_user(req.query, settings.COOKIES, page=req.page)
        if not success:
            return {"success": False, "message": f"搜索失败: {msg}"}

        items = data.get("data", {}).get("items", [])
        results = []
        for item in items:
            user_info = item.get("user_info", {})
            results.append({
                "user_id": user_info.get("user_id", ""),
                "nickname": user_info.get("nickname", ""),
                "avatar": user_info.get("images", ""),
                "desc": user_info.get("desc", ""),
                "fans": user_info.get("fstatus", ""),
            })
        return {"success": True, "data": results, "total": len(results)}
    except Exception as e:
        return {"success": False, "message": f"搜索异常: {str(e)[:100]}"}
