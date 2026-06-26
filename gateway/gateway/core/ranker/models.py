"""Ranker data models."""

from pydantic import BaseModel


class ScoredItem(BaseModel):
    """Item with a relevance score."""
    source: str
    query_type: str
    content: str
    metadata: dict
    score: float


class CompressedContext(BaseModel):
    """Compressed context that fits within token budget."""
    included: list[ScoredItem]
    excluded: list[ScoredItem]
    tokens_used: int
    token_budget: int
    compression_ratio: float
