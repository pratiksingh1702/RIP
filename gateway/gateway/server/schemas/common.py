"""Common schemas shared across routers."""


from pydantic import BaseModel


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
    context: list[ContextItem]
    tokens_used: int
    tokens_retrieved: int = 0
    token_allocation: dict[str, int] = {}
    score_summary: list[dict] = []
    conflicts: list[dict]
    warnings: list[str]
