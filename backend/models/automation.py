"""Automation model — auto-operation pipelines."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from core.database import Base


class Automation(Base):
    __tablename__ = "automations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), default="")
    keywords = Column(Text, default="")  # comma-separated
    is_active = Column(Boolean, default=True)
    schedule_cron = Column(String(100), default="")  # e.g. "0 9 * * *"
    pipeline_config = Column(Text, default="{}")  # JSON: steps config
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    run_count = Column(Integer, default=0)
    account_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
