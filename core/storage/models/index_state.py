"""Index state ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from core.storage.database import Base


class IndexState(Base):
    """ORM model storing index runs and metadata."""

    __tablename__ = "index_states"

    repo_path: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, default="idle")
    last_run: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
