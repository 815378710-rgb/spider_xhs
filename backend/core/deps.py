"""
FastAPI dependency injection — auth-free mode (v2 simplified)
"""
from fastapi import Depends


async def get_current_user():
    """No auth required — return default user."""
    return {"sub": "1", "username": "admin"}


async def get_optional_user():
    """No auth required — return default user."""
    return {"sub": "1", "username": "admin"}
