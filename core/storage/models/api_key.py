"""API Key ORM model."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.storage.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ApiKey(Base):
    """API key for authentication."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, doc="Human-readable name for the key")
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, doc="Hashed API key")
    prefix: Mapped[str] = mapped_column(String(20), nullable=False, doc="Key prefix for identification (e.g., 'rip_')")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, doc="Whether the key is active")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, doc="Optional expiration date")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, doc="Last time the key was used")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, doc="Optional description of the key's purpose")
    project_id: Mapped[str | None] = mapped_column(String(255), nullable=True, doc="Optional project isolation ID")
