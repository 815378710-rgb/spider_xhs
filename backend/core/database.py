"""
SQLAlchemy async database setup
"""
import os
from contextlib import asynccontextmanager
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

_async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def async_session():
    """Auto-committing async session context manager.

    Usage:
        async with async_session() as db:
            db.add(...)
            # auto-committed on successful exit, auto-rolled-back on error
    """
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


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
    """Initialize database: create tables if needed, then run Alembic migrations."""
    import subprocess
    from loguru import logger

    # Step 1: Create tables if they don't exist (for fresh installs)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Base tables ensured via create_all")

    # Step 2: Run Alembic migrations to apply any schema changes
    alembic_dir = os.path.join(os.path.dirname(__file__), "..", "alembic")
    if os.path.isdir(alembic_dir):
        try:
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                cwd=os.path.dirname(__file__),  # backend dir
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                logger.info("✅ Alembic migrations applied")
            else:
                logger.warning(f"Alembic migration warning: {result.stderr[:200]}")
        except FileNotFoundError:
            logger.info("Alembic not installed, skipping migrations (create_all is sufficient)")
        except Exception as e:
            logger.warning(f"Alembic migration error (non-fatal): {e}")
    else:
        logger.info("No alembic directory found, using create_all only")
