"""File hash ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from core.storage.database import Base


class FileHash(Base):
    """ORM model storing file path hashes for incremental indexing."""

    __tablename__ = "file_hashes"

    path: Mapped[str] = mapped_column(String, primary_key=True)
    hash_value: Mapped[str] = mapped_column(String, nullable=False)
    last_indexed: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
