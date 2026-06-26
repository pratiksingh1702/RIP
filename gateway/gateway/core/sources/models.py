"""Source response models."""

from pydantic import BaseModel


class SourceResponse(BaseModel):
    """Response from a source query."""
    source: str
    query_type: str
    content: str
    metadata: dict
    token_count: int
    latency_ms: int
    success: bool
    error: str | None = None
