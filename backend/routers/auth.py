"""
认证路由 — 注册/登录/公告
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from core.security import hash_password, verify_password, create_access_token, generate_license_key
from core.deps import get_current_user
from core.database import async_session
from models.user import User, LicenseKey, Announcement

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str
    password: str
    license_key: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest):
    """Register with license key."""
    if not req.username or len(req.username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少2个字符")
    if not req.password or len(req.password) < 4:
        raise HTTPException(status_code=400, detail="密码至少4个字符")

    async with async_session() as db:
        # Check username exists
        existing = await db.execute(select(User).where(User.username == req.username))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="用户名已存在")

        # Validate license key
        lk = await db.execute(
            select(LicenseKey).where(LicenseKey.key == req.license_key.upper())
        )
        license_obj = lk.scalar_one_or_none()
        if not license_obj:
            raise HTTPException(status_code=400, detail="卡密无效")
        if license_obj.status != "unused":
            raise HTTPException(status_code=400, detail="卡密已被使用或已禁用")

        # Create user — set expires_at based on license key valid_days
        now = datetime.utcnow()
        user_expires = now + timedelta(days=license_obj.valid_days) if license_obj.valid_days else None
        user = User(
            username=req.username,
            password_hash=hash_password(req.password),
            role="user",
            status="active",
            expires_at=user_expires,
        )
        db.add(user)
        await db.flush()

        # Mark license key as used
        license_obj.status = "used"
        license_obj.used_by = user.id
        license_obj.used_at = now
        license_obj.expires_at = user_expires
        await db.commit()

        # Generate token
        token = create_access_token({"sub": str(user.id), "username": user.username})
        return TokenResponse(access_token=token, username=user.username, role=user.role)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Login with username and password."""
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == req.username))
        user = result.scalar_one_or_none()

        if not user or not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        if user.status == "disabled":
            raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")
        # Check expiry (admin users never expire)
        if user.expires_at and user.role != "admin" and datetime.utcnow() > user.expires_at:
            raise HTTPException(status_code=403, detail="账号已过期，请联系管理员续期")

        token = create_access_token({"sub": str(user.id), "username": user.username})
        return TokenResponse(access_token=token, username=user.username, role=user.role)


@router.get("/me")
async def get_me(user=Depends(get_current_user)):
    """Get current user info."""
    return {
        "user_id": user.get("sub"),
        "username": user.get("username"),
        "role": user.get("role"),
    }


@router.get("/announcement")
async def get_announcement():
    """Get latest active announcement."""
    async with async_session() as db:
        result = await db.execute(
            select(Announcement)
            .where(Announcement.active == True)
            .order_by(Announcement.created_at.desc())
            .limit(1)
        )
        ann = result.scalar_one_or_none()
        if not ann:
            return {"success": True, "data": None}
        return {
            "success": True,
            "data": {
                "id": ann.id,
                "title": ann.title,
                "content": ann.content,
                "created_at": ann.created_at.isoformat() if ann.created_at else None,
            }
        }
