"""
多账号矩阵管理路由
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, delete
from core.deps import get_current_user
from core.database import async_session
from models.account import Account
from models.cookie import Cookie
from core.security import encrypt_value, decrypt_value

router = APIRouter()


class AccountCreate(BaseModel):
    platform: str = "xhs"
    nickname: str = ""
    cookies: str = ""


@router.get("")
async def list_accounts(user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(Account))
        accounts = result.scalars().all()
        return {
            "success": True,
            "data": [
                {
                    "id": a.id, "platform": a.platform, "nickname": a.nickname,
                    "avatar_url": a.avatar_url, "user_id": a.user_id,
                    "status": a.status, "last_check": str(a.last_check) if a.last_check else None,
                    "created_at": str(a.created_at),
                }
                for a in accounts
            ],
            "total": len(accounts),
        }


@router.post("")
async def create_account(req: AccountCreate, user=Depends(get_current_user)):
    async with async_session() as db:
        account = Account(platform=req.platform, nickname=req.nickname)
        db.add(account)
        await db.flush()
        if req.cookies:
            cookie = Cookie(
                account_id=account.id,
                cookies_encrypted=encrypt_value(req.cookies),
                username=req.nickname,
                is_active=True,
            )
            db.add(cookie)
        await db.commit()
        return {"success": True, "id": account.id, "message": "账号已添加"}


@router.delete("/{account_id}")
async def delete_account(account_id: int, user=Depends(get_current_user)):
    async with async_session() as db:
        await db.execute(delete(Cookie).where(Cookie.account_id == account_id))
        await db.execute(delete(Account).where(Account.id == account_id))
        await db.commit()
        return {"success": True, "message": "账号已删除"}


@router.get("/{account_id}/cookies")
async def get_account_cookies(account_id: int, user=Depends(get_current_user)):
    async with async_session() as db:
        result = await db.execute(select(Cookie).where(Cookie.account_id == account_id))
        cookies = result.scalars().all()
        return {
            "success": True,
            "data": [
                {
                    "id": c.id, "username": c.username, "a1": c.a1,
                    "is_valid": c.is_valid, "is_active": c.is_active,
                    "last_validated": str(c.last_validated) if c.last_validated else None,
                }
                for c in cookies
            ],
        }


@router.post("/{account_id}/check")
async def check_account_health(account_id: int, user=Depends(get_current_user)):
    """Health check: validate cookie for this account."""
    from apis.xhs_pc_apis import XHS_Apis
    from core.config import settings
    async with async_session() as db:
        result = await db.execute(select(Cookie).where(Cookie.account_id == account_id, Cookie.is_active == True))
        cookie = result.scalar_one_or_none()
        if not cookie:
            return {"success": False, "message": "该账号没有有效 Cookie"}
        try:
            cookies_str = decrypt_value(cookie.cookies_encrypted)
            xhs = XHS_Apis()
            ok, msg, data = xhs.get_user_self_info(cookies_str)
            from datetime import datetime
            cookie.last_validated = datetime.utcnow()
            if not ok:
                cookie.is_valid = False
            await db.commit()
            return {"success": ok, "message": msg}
        except Exception as e:
            return {"success": False, "message": str(e)}
