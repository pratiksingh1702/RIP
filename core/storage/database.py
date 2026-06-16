"""Database setup."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from server.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.postgres_url, echo=False)
async_session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection or utility provider for db sessions."""
    async with async_session_factory() as session:
        yield session
