"""Project ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.storage.database import Base


class Project(Base):
    """Repository/project metadata used for isolation."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    root: Mapped[str] = mapped_column(String, nullable=True)  # Root is optional for git-cloned repos
    language: Mapped[str] = mapped_column(String, default="mixed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # New fields for Git integration
    git_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    files_count: Mapped[int] = mapped_column(Integer, default=0)
    entities_count: Mapped[int] = mapped_column(Integer, default=0)
    languages: Mapped[list[str]] = mapped_column(JSON, default=list)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reindexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
