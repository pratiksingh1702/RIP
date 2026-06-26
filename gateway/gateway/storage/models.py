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
