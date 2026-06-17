"""Project ORM model."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from core.storage.database import Base


class Project(Base):
    """Repository/project metadata used for isolation."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    root: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    language: Mapped[str] = mapped_column(String, default="mixed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
