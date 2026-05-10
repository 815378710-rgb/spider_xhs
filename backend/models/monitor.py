"""Monitor model — competitor monitoring."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from core.database import Base


class MonitorItem(Base):
    __tablename__ = "monitor_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), default="")
    monitor_type = Column(String(20), default="keyword")  # keyword, account, brand, url
    target = Column(String(500), default="")  # keyword, user_id, brand name, or URL
    interval_minutes = Column(Integer, default=60)  # check interval
    is_active = Column(Boolean, default=True)
    last_check = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MonitorSnapshot(Base):
    __tablename__ = "monitor_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, nullable=False, index=True)
    data_json = Column(Text, default="{}")  # snapshot data
    created_at = Column(DateTime, default=datetime.utcnow)
