"""
管理员路由 — 用户/卡密/公告管理
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select, func, desc
from core.deps import require_admin
from core.security import hash_password, generate_license_key
from core.database import async_session
from models.user import User, LicenseKey, Announcement

router = APIRouter()


# ── User Management ──────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    user=Depends(require_admin),
):
    """List all users with pagination."""
    async with async_session() as db:
        query = select(User)
        if search:
            query = query.where(User.username.contains(search))
        query = query.order_by(desc(User.created_at))

        # Count
        count_q = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_q)).scalar() or 0

        # Paginate
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        users = result.scalars().all()

        return {
            "success": True,
            "data": {
                "items": [
                    {
                        "id": u.id,
                        "username": u.username,
                        "role": u.role,
                        "status": u.status,
                        "is_active": u.status == "active",
                        "has_cookie": bool(u.cookie),
                        "expires_at": u.expires_at.isoformat() if u.expires_at else None,
                        "created_at": u.created_at.isoformat() if u.created_at else None,
                        "last_login": u.updated_at.isoformat() if u.updated_at else None,
                    }
                    for u in users
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        }


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    body: dict,
    admin=Depends(require_admin),
):
    """Update user (status, role, password)."""
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user.id == int(admin["sub"]):
            raise HTTPException(status_code=400, detail="不能修改自己的状态")

        if "status" in body:
            # P1-9 修复：验证status输入值
            allowed_statuses = ["active", "inactive", "banned"]
            if body["status"] not in allowed_statuses:
                raise HTTPException(status_code=400, detail=f"无效的状态值，允许值: {allowed_statuses}")
            user.status = body["status"]
        if "role" in body and body["role"] in ("admin", "user"):
            user.role = body["role"]
        if body.get("password"):
            # P1-8 修复：添加密码长度验证
            if len(body["password"]) < 6:
                raise HTTPException(status_code=400, detail="密码长度至少6个字符")
            user.password_hash = hash_password(body["password"])

        await db.commit()
        return {"success": True, "message": "用户已更新"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin=Depends(require_admin),
):
    """Delete a user."""
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        if user.id == int(admin["sub"]):
            raise HTTPException(status_code=400, detail="不能删除自己")
        if user.role == "admin":
            raise HTTPException(status_code=400, detail="不能删除管理员")
        await db.delete(user)
        await db.commit()
        return {"success": True, "message": "用户已删除"}


@router.post("/users/{user_id}/renew")
async def renew_user(
    user_id: int,
    body: dict,
    admin=Depends(require_admin),
):
    """Renew / extend user expiry by N days (管理员给用户续期)."""
    days = max(body.get("days", 30), 1)
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        now = datetime.utcnow()
        # Extend from now or from current expiry, whichever is later
        base = max(now, user.expires_at) if user.expires_at else now
        user.expires_at = base + timedelta(days=days)
        await db.commit()
        return {
            "success": True,
            "message": f"已为用户 {user.username} 续期 {days} 天",
            "data": {"expires_at": user.expires_at.isoformat()},
        }


# ── License Key Management ───────────────────────────────────────────────────

@router.post("/license-keys")
async def generate_keys(
    body: dict,
    admin=Depends(require_admin),
):
    """Generate license keys (支持自定义有效天数)."""
    count = min(max(body.get("count", 1), 1), 100)
    valid_days = max(body.get("expires_days", body.get("valid_days", 30)), 0)  # 0 = 永久
    keys = []
    async with async_session() as db:
        for _ in range(count):
            key = generate_license_key()
            lk = LicenseKey(key=key, valid_days=valid_days, created_by=int(admin["sub"]), status="unused")
            db.add(lk)
            keys.append(key)
        await db.flush()
        await db.commit()
    return {
        "success": True,
        "message": f"已生成 {count} 张卡密（有效 {valid_days if valid_days else '永久'} 天）",
        "data": {"keys": keys, "valid_days": valid_days},
    }


@router.get("/license-keys")
async def list_keys(
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    status: str = "",
    user=Depends(require_admin),
):
    """List license keys with pagination."""
    async with async_session() as db:
        # JOIN with User table to get usernames
        from sqlalchemy.orm import aliased
        UsedByUser = aliased(User)
        query = select(LicenseKey, UsedByUser.username).outerjoin(
            UsedByUser, LicenseKey.used_by == UsedByUser.id
        )
        if search:
            query = query.where(LicenseKey.key.contains(search.upper()))
        if status:
            query = query.where(LicenseKey.status == status)
        query = query.order_by(desc(LicenseKey.created_at))

        count_q = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_q)).scalar() or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        rows = result.all()

        return {
            "success": True,
            "data": {
                "items": [
                    {
                        "id": k.id,
                        "code": k.key,
                        "valid_days": k.valid_days,
                        "status": k.status,
                        "is_used": k.status == "used",
                        "used_by": k.used_by,
                        "used_by_username": username or "",
                        "used_at": k.used_at.isoformat() if k.used_at else None,
                        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                        "created_at": k.created_at.isoformat() if k.created_at else None,
                    }
                    for k, username in rows
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        }


@router.delete("/license-keys/{key_id}")
async def delete_key(
    key_id: int,
    admin=Depends(require_admin),
):
    """Delete a license key."""
    async with async_session() as db:
        result = await db.execute(select(LicenseKey).where(LicenseKey.id == key_id))
        lk = result.scalar_one_or_none()
        if not lk:
            raise HTTPException(status_code=404, detail="卡密不存在")
        await db.delete(lk)
        await db.commit()
        return {"success": True, "message": "卡密已删除"}


# ── Announcement Management ──────────────────────────────────────────────────

class AnnouncementBody(BaseModel):
    title: str
    content: str
    active: bool = True


@router.get("/announcements")
async def list_announcements(user=Depends(require_admin)):
    """List all announcements."""
    async with async_session() as db:
        result = await db.execute(
            select(Announcement).order_by(desc(Announcement.created_at))
        )
        anns = result.scalars().all()
        return {
            "success": True,
            "data": [
                {
                    "id": a.id,
                    "title": a.title,
                    "content": a.content,
                    "active": a.active,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in anns
            ]
        }


@router.post("/announcements")
async def create_announcement(
    body: AnnouncementBody,
    admin=Depends(require_admin),
):
    """Create an announcement."""
    async with async_session() as db:
        ann = Announcement(
            title=body.title,
            content=body.content,
            active=body.active,
            created_by=int(admin["sub"]),
        )
        db.add(ann)
        await db.flush()
        await db.commit()
        return {"success": True, "message": "公告已创建", "data": {"id": ann.id}}


@router.put("/announcements/{ann_id}")
async def update_announcement(
    ann_id: int,
    body: AnnouncementBody,
    admin=Depends(require_admin),
):
    """Update an announcement."""
    async with async_session() as db:
        result = await db.execute(select(Announcement).where(Announcement.id == ann_id))
        ann = result.scalar_one_or_none()
        if not ann:
            raise HTTPException(status_code=404, detail="公告不存在")
        ann.title = body.title
        ann.content = body.content
        ann.active = body.active
        await db.commit()
        return {"success": True, "message": "公告已更新"}


@router.delete("/announcements/{ann_id}")
async def delete_announcement(
    ann_id: int,
    admin=Depends(require_admin),
):
    """Delete an announcement."""
    async with async_session() as db:
        result = await db.execute(select(Announcement).where(Announcement.id == ann_id))
        ann = result.scalar_one_or_none()
        if not ann:
            raise HTTPException(status_code=404, detail="公告不存在")
        await db.delete(ann)
        await db.commit()
        return {"success": True, "message": "公告已删除"}


# ── Model Config ─────────────────────────────────────────────────────────────

class ModelConfigBody(BaseModel):
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None


@router.get("/model-config")
async def get_model_config(user=Depends(require_admin)):
    """Get global model config."""
    from core.config import settings
    return {
        "success": True,
        "data": {
            "llm_provider": settings.LLM_PROVIDER,
            "llm_api_key": settings.LLM_API_KEY,
            "llm_model": settings.LLM_MODEL,
            "llm_base_url": settings.LLM_BASE_URL,
            "llm_configured": bool(settings.LLM_API_KEY),
        }
    }


@router.put("/model-config")
async def update_model_config(
    body: ModelConfigBody,
    admin=Depends(require_admin),
):
    """Update global model config."""
    from core.config import settings
    update_kwargs = {}
    if body.llm_provider is not None:
        update_kwargs["LLM_PROVIDER"] = body.llm_provider
    if body.llm_api_key is not None:
        update_kwargs["LLM_API_KEY"] = body.llm_api_key
    if body.llm_model is not None:
        update_kwargs["LLM_MODEL"] = body.llm_model
    if body.llm_base_url is not None:
        update_kwargs["LLM_BASE_URL"] = body.llm_base_url
    settings.update(**update_kwargs)
    return {"success": True, "message": "模型配置已更新"}


@router.post("/model-config/test")
async def test_model_config(user=Depends(require_admin)):
    """Test model connection."""
    from core.config import settings
    if not settings.LLM_API_KEY:
        return {"success": False, "message": "未配置 API Key"}
    try:
        from core.llm import create_backend
        backend = create_backend(
            provider=settings.LLM_PROVIDER,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL,
        )
        response = await backend.chat("你好", "请回复OK两个字母")
        return {"success": True, "message": f"连接成功: {response[:50]}"}
    except Exception as e:
        return {"success": False, "message": f"连接失败: {str(e)[:100]}"}


# ── Stats ──────────────────────────────────────────────────────
@router.get("/stats")
async def get_stats(user=Depends(require_admin)):
    """Get system statistics overview."""
    async with async_session() as db:
        # Total users
        total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
        
        # Active cards
        active_cards = (await db.execute(
            select(func.count()).select_from(LicenseKey).where(LicenseKey.status == "unused")
        )).scalar() or 0
        
        return {
            "success": True,
            "data": {
                "totalUsers": total_users,
                "activeCards": active_cards,
                "todayApiCalls": 0,  # Placeholder
                "todayTokenUsage": 0,  # Placeholder
            }
        }


@router.get("/stats/usage")
async def get_usage_stats(
    group_by: str = "user",
    start_date: str = None,
    end_date: str = None,
    user=Depends(require_admin),
):
    """Get usage statistics."""
    async with async_session() as db:
        query = select(User)
        result = await db.execute(query)
        users = result.scalars().all()
        
        stats = []
        for u in users:
            stats.append({
                "username": u.username,
                "role": u.role,
                "api_calls": 0,  # Placeholder
                "token_usage": 0,  # Placeholder
                "last_active": u.last_login.isoformat() if u.last_login else None,
            })
        
        return {"success": True, "data": stats}