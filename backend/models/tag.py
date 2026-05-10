"""Tag model — content library tags."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from core.database import Base


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, index=True)
    color = Column(String(20), default="#1890ff")
    created_at = Column(DateTime, default=datetime.utcnow)


class NoteTag(Base):
    __tablename__ = "note_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    note_id = Column(Integer, ForeignKey("notes.id"), index=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), index=True)
