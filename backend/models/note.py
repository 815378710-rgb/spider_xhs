"""Note model — content library."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from core.database import Base


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(String(50), unique=True, index=True)
    title = Column(String(500), default="")
    desc = Column(Text, default="")
    note_type = Column(String(20), default="normal")  # normal, video
    url = Column(Text, default="")
    author_name = Column(String(100), default="")
    author_id = Column(String(100), default="")
    likes = Column(Integer, default=0)
    collects = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    images_json = Column(Text, default="[]")  # JSON array of image URLs
    tags_json = Column(Text, default="[]")
    source = Column(String(50), default="")  # search, collect, monitor
    # Content library fields
    in_library = Column(Boolean, default=False)
    library_tags = Column(Text, default="")  # comma-separated tag names
    # Rewritten content
    rewritten_title = Column(String(500), default="")
    rewritten_desc = Column(Text, default="")
    # Local images
    local_images_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
