"""
认证路由 — JWT 登录/登出
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.security import create_access_token
from core.deps import get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Login and get JWT token.
    For now, simple hardcoded admin login. Can be extended to full user system.
    """
    # TODO: implement proper user table + password hashing
    if req.username == "admin" and req.password == "admin":
        token = create_access_token({"sub": "1", "username": "admin"})
        return TokenResponse(access_token=token)
    raise HTTPException(status_code=401, detail="用户名或密码错误")


@router.get("/me")
async def get_me(user=Depends(get_current_user)):
    """Get current user info."""
    return {
        "user_id": user.get("sub"),
        "username": user.get("username"),
    }
