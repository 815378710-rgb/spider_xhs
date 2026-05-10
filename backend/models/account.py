"""Account model — multi-account matrix."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from core.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(20), default="xhs")  # xhs, creator
    nickname = Column(String(100), default="")
    avatar_url = Column(Text, default="")
    user_id = Column(String(100), default="")
    status = Column(String(20), default="active")  # active, expired, banned
    last_check = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
