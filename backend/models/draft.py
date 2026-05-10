"""Draft model — draft workshop."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from core.database import Base


class Draft(Base):
    __tablename__ = "drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), default="")
    content = Column(Text, default="")
    images_json = Column(Text, default="[]")  # JSON array of local image paths
    tags_json = Column(Text, default="[]")
    source_note_id = Column(String(50), default="")  # linked library note
    status = Column(String(20), default="draft")  # draft, ready, published
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
