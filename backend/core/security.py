"""
JWT + Fernet security utilities + password hashing
"""
import os
import time
import secrets
import string
from typing import Optional
from jose import JWTError, jwt
from cryptography.fernet import Fernet
from core.config import settings

# P1-4 修复：使用bcrypt代替SHA-256，提供更强的密码哈希保护
try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except ImportError:
    # Fallback: 如果passlib未安装，使用bcrypt直接实现
    import bcrypt
    pwd_context = None


def hash_password(password: str) -> str:
    """Hash a plain-text password with bcrypt."""
    if pwd_context:
        return pwd_context.hash(password)
    else:
        # Fallback implementation
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a hash."""
    if pwd_context:
        return pwd_context.verify(plain_password, hashed_password)
    else:
        # Fallback implementation
        try:
            return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
        except Exception:
            return False


# ── License key generation ───────────────────────────────────────────────────

def generate_license_key() -> str:
    """Generate a license key in format XXXX-XXXX-XXXX-XXXX."""
    chars = string.ascii_uppercase + string.digits
    parts = []
    for _ in range(4):
        part = ''.join(secrets.choice(chars) for _ in range(4))
        parts.append(part)
    return '-'.join(parts)


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
