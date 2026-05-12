"""
FastAPI dependency injection — real JWT auth
"""
from datetime import datetime
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from core.security import verify_access_token
from core.database import async_session

security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Parse JWT from Authorization header, return user dict with DB info."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录，请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = verify_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 token")

    # Fetch user from DB
    async with async_session() as db:
        from models.user import User
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
        if user.status == "disabled":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
        # Check expiry (admin never expires)
        if user.expires_at and user.role != "admin" and datetime.utcnow() > user.expires_at:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已过期，请联系管理员续期")
        return {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
        }


async def get_optional_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Like get_current_user but returns None instead of raising."""
    if not credentials:
        return None
    payload = verify_access_token(credentials.credentials)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    async with async_session() as db:
        from models.user import User
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()
        if not user or user.status == "disabled":
            return None
        return {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
        }


async def require_admin(user=Depends(get_current_user)):
    """Require admin role."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user
