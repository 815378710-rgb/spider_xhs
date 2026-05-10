"""
JWT + Fernet security utilities
"""
import os
import time
import secrets
from typing import Optional
from jose import JWTError, jwt
from cryptography.fernet import Fernet
from core.config import settings


# ── Fernet encryption (for cookies) ──────────────────────────────────────────

def _get_or_create_fernet_key() -> str:
    """Get or auto-generate Fernet key."""
    key_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", ".fernet_key")
    if settings.FERNET_KEY:
        return settings.FERNET_KEY
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            return f.read().strip()
    key = Fernet.generate_key().decode()
    os.makedirs(os.path.dirname(key_file), exist_ok=True)
    with open(key_file, "w") as f:
        f.write(key)
    return key


_fernet_key = None


def _get_fernet() -> Fernet:
    global _fernet_key
    if _fernet_key is None:
        _fernet_key = _get_or_create_fernet_key()
    return Fernet(_fernet_key.encode() if isinstance(_fernet_key, str) else _fernet_key)


def encrypt_value(value: str) -> str:
    """Encrypt a string value."""
    if not value:
        return ""
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt an encrypted string value."""
    if not token:
        return ""
    f = _get_fernet()
    return f.decrypt(token.encode()).decode()


# ── JWT token ─────────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_minutes: int = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = time.time() + (expires_minutes or settings.JWT_EXPIRE_MINUTES) * 60
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_access_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token. Returns payload or None."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
