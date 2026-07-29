"""User, OAuth accounts, and User Session ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.storage.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def gen_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    """User profile record."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    oauth_accounts: Mapped[list[UserOAuthAccount]] = relationship("UserOAuthAccount", back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[list[UserSession]] = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")


class UserOAuthAccount(Base):
    """Linked OAuth provider account for a user."""

    __tablename__ = "user_oauth_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # 'github' or 'google'
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True, doc="Encrypted OAuth access token with full repo scope")
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True, doc="Granted OAuth scopes")
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    user: Mapped[User] = relationship("User", back_populates="oauth_accounts")


class UserSession(Base):
    """Authenticated user session token (API key tied to user)."""

    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    token_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    device_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="sessions")
