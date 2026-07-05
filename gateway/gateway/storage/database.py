"""Database setup for Context Gateway."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from gateway.config import settings

engine = create_async_engine(settings.postgres_url, echo=False)
async_session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection or utility provider for db sessions."""
    async with async_session_factory() as session:
        yield session


async def get_session() -> AsyncSession:
    """Get a new async session (for use in async with blocks)."""
    return async_session_factory()


__all__ = ["Base", "async_session_factory", "get_async_session", "get_session", "engine"]


async def ensure_storage_schema() -> None:
    """Create local metadata tables when migrations have not been run yet."""
    import gateway.storage.models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
