"""Common schemas shared across routers."""

from pydantic import BaseModel
from typing import List


class ContextItem(BaseModel):
    """Single context item."""
    source: str
    query_type: str
    content: str
    metadata: dict
    score: float


class ContextPackage(BaseModel):
    """Final context package returned by get_context."""
    session_id: str
    intent: str
    domain: str
    context: List[ContextItem]
    tokens_used: int
    conflicts: List[dict]
    warnings: List[str]
