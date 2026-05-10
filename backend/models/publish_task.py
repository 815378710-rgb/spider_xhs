"""PublishTask model — scheduled publishing."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from core.database import Base


class PublishTask(Base):
    __tablename__ = "publish_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    draft_id = Column(Integer, nullable=True)
    account_id = Column(Integer, nullable=True)
    status = Column(String(20), default="pending")  # pending, running, success, failed, cancelled
    note_type = Column(String(20), default="image")  # image, video
    title = Column(String(500), default="")
    content = Column(Text, default="")
    images_json = Column(Text, default="[]")
    tags_json = Column(Text, default="[]")
    topics_json = Column(Text, default="[]")
    location = Column(String(200), default="")
    privacy = Column(String(20), default="public")  # public, private
    scheduled_at = Column(DateTime, nullable=True)  # for timed publishing
    published_at = Column(DateTime, nullable=True)
    xhs_note_id = Column(String(50), default="")
    error_msg = Column(Text, default="")
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
