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
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    account_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AutomationLog(Base):
    """每次流水线执行的日志记录"""
    __tablename__ = "automation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    automation_id = Column(Integer, nullable=False, index=True)
    keyword = Column(String(200), default="")
    step = Column(String(50), default="")  # search/rewrite/image/publish
    status = Column(String(20), default="running")  # running/success/failed
    message = Column(Text, default="")
    duration_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
