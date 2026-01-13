"""
Database initialization and session management.
"""
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base

logger = logging.getLogger("benchmark.database")

# Global engine and session maker
engine = None
async_session_maker = None


def init_database(db_url: str, echo: bool = False) -> None:
    """
    Initialize database engine and session maker.
    
    Args:
        db_url: Database URL (e.g., 'sqlite+aiosqlite:///data/metrics.db')
        echo: Whether to echo SQL statements
    """
    global engine, async_session_maker
    
    # Convert sqlite:/// to sqlite+aiosqlite:///
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    
    logger.info(f"Initializing database: {db_url}")
    
    engine = create_async_engine(
        db_url,
        echo=echo,
        future=True
    )
    
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    logger.info("Database engine initialized")


async def init_db() -> None:
    """Create all tables in the database."""
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    logger.info("Creating database tables...")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created successfully")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session.
    
    Yields:
        AsyncSession instance
    """
    if async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def close_db() -> None:
    """Close database connections."""
    global engine
    
    if engine:
        logger.info("Closing database connections...")
        await engine.dispose()
        logger.info("Database connections closed")
