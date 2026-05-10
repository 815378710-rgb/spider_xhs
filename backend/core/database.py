"""
SQLAlchemy async database setup
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from core.config import settings, DATA_DIR


class Base(DeclarativeBase):
    pass


# Create engine
DATABASE_URL = settings.DATABASE_URL
if DATABASE_URL.startswith("sqlite"):
    # Ensure data directory exists for SQLite
    db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else DATA_DIR, exist_ok=True)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI dependency — yields an async DB session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
