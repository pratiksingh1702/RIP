"""ORM models for Context Gateway."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    ARRAY,
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gateway.storage.database import Base


class Session(Base):
    """Session tracking."""

    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    task_description: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String(50), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(100))
    risk_level: Mapped[str | None] = mapped_column(String(20))
    files_accessed: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    nodes_accessed: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    sources_used: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    tokens_retrieved: Mapped[int] = mapped_column(Integer, default=0)
    tokens_delivered: Mapped[int] = mapped_column(Integer, default=0)
    tokens_saved: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    outcome: Mapped[str | None] = mapped_column(Text)
    files_modified: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    git_branch: Mapped[str | None] = mapped_column(String(255))
    project_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[str | None] = mapped_column(String(255))

    events: Mapped[list[SessionEvent]] = relationship("SessionEvent", back_populates="session", cascade="all, delete-orphan")
    feedback: Mapped[Feedback | None] = relationship("Feedback", back_populates="session", cascade="all, delete-orphan", uselist=False)


class SessionEvent(Base):
    """Session event analytics."""

    __tablename__ = "session_events"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[dict | None] = mapped_column(JSON)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    session: Mapped[Session] = relationship("Session", back_populates="events")


class Feedback(Base):
    """Feedback for learning loop."""

    __tablename__ = "feedback"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    rating: Mapped[int | None] = mapped_column(Integer, CheckConstraint("rating BETWEEN 1 AND 5"))
    was_helpful: Mapped[bool | None] = mapped_column(Boolean)
    missing_context: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    irrelevant_context: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    session: Mapped[Session] = relationship("Session", back_populates="feedback")


class SourceHealth(Base):
    """Source health tracking."""

    __tablename__ = "source_health"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    avg_latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_rate: Mapped[float] = mapped_column(Float, default=0.0)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class RegisteredSource(Base):
    """Runtime-configurable Gateway source registry."""

    __tablename__ = "registered_sources"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="mcp")
    transport: Mapped[str] = mapped_column(String(20), nullable=False, default="http")
    endpoint_url: Mapped[str | None] = mapped_column(Text)
    auth_type: Mapped[str] = mapped_column(String(50), nullable=False, default="none")
    credential_ref: Mapped[str | None] = mapped_column(String(120))
    mcp_config: Mapped[dict] = mapped_column(JSON, default=dict)
    domain_hints: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    priority_hint: Mapped[int] = mapped_column(Integer, default=50)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    health_status: Mapped[str] = mapped_column(String(30), default="unknown")
    protected: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class SourceCredential(Base):
    """Encrypted credential material referenced by registered sources."""

    __tablename__ = "source_credentials"

    ref: Mapped[str] = mapped_column(String(120), primary_key=True)
    source_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True))
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    masked_value: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class OAuthProvider(Base):
    """Server-operator configured OAuth provider registration."""

    __tablename__ = "oauth_providers"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    authorize_url: Mapped[str] = mapped_column(Text, nullable=False)
    token_url: Mapped[str] = mapped_column(Text, nullable=False)
    revoke_url: Mapped[str | None] = mapped_column(Text)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    client_secret: Mapped[str] = mapped_column(Text, nullable=False)
    default_scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    supports_pkce: Mapped[bool] = mapped_column(Boolean, default=True)
    icon_key: Mapped[str] = mapped_column(String(80), nullable=False)
    allowed_redirect_uris: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class PendingOAuthRequest(Base):
    """Short-lived OAuth authorization request state."""

    __tablename__ = "pending_oauth_requests"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("registered_sources.id", ondelete="CASCADE"), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(80), ForeignKey("oauth_providers.id"), nullable=False)
    state: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    code_verifier: Mapped[str | None] = mapped_column(Text)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    client_type: Mapped[str] = mapped_column(String(20), nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OAuthToken(Base):
    """Encrypted tokens for an OAuth-connected source."""

    __tablename__ = "oauth_tokens"
    __table_args__ = (UniqueConstraint("provider_id", "account_label", name="uq_oauth_provider_account_label"),)

    source_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("registered_sources.id", ondelete="CASCADE"), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(80), ForeignKey("oauth_providers.id"), nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    scope: Mapped[str | None] = mapped_column(Text)
    token_type: Mapped[str] = mapped_column(String(40), default="Bearer")
    account_label: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class GatewaySetting(Base):
    """Editable Gateway defaults exposed to mobile Settings."""

    __tablename__ = "gateway_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class AuditLog(Base):
    """Access decision audit logs."""

    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str | None] = mapped_column(String(100))
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
