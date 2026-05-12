"""TaskLog model — audit trail for all operations."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from core.database import Base


class TaskLog(Base):
    __tablename__ = "task_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(String(50), default="")       # collect, rewrite, publish, automation, etc.
    status = Column(String(20), default="running")    # running, success, failed
    detail = Column(Text, default="")                 # human-readable description
    input_summary = Column(Text, default="")          # JSON summary of inputs
    output_summary = Column(Text, default="")         # JSON summary of outputs
    error_detail = Column(Text, default="")           # error message if failed
    triggered_by = Column(String(50), default="system")  # system, manual, cron
    duration_seconds = Column(Integer, default=0)
    account_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
