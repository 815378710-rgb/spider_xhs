"""Notification model — system notifications."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from core.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), default="")
    message = Column(Text, default="")
    noti_type = Column(String(30), default="info")  # info, warning, error, success
    is_read = Column(Boolean, default=False)
    link = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
