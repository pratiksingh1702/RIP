from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.storage.database import Base

try:
    UTC = datetime.UTC
except AttributeError:
    UTC = timezone.utc


class EmbeddingCache(Base):
    __tablename__ = "embedding_cache"
    
    content_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    fqn: Mapped[str] = mapped_column(String(1024), index=True)
    embedding_json: Mapped[str] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
