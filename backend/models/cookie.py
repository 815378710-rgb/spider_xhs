"""Cookie model — encrypted storage."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from core.database import Base


class Cookie(Base):
    __tablename__ = "cookies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    cookies_encrypted = Column(Text, default="")  # Fernet-encrypted
    username = Column(String(100), default="")
    a1 = Column(String(60), default="")
    is_valid = Column(Boolean, default=True)
    is_active = Column(Boolean, default=False)
    last_validated = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
