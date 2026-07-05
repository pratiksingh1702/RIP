"""HTTP response schemas."""

from typing import Any

from pydantic import BaseModel

from gateway.server.schemas.common import ContextItem


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    sources: dict[str, dict[str, Any]]


class GetContextResponse(BaseModel):
    """Response to get context request."""
    session_id: str
    intent: str
    domain: str
    context: list[ContextItem]
    tokens_used: int
    tokens_retrieved: int = 0
    token_allocation: dict[str, int] = {}
    score_summary: list[dict[str, Any]] = []
    conflicts: list[dict]
    warnings: list[str]


class ValidateChangeResponse(BaseModel):
    """Response to validate change request."""
    risk_level: str
    affected_files: list[str]
    impact_summary: str
    warnings: list[str]
    error: str | None = None


class SourceListResponse(BaseModel):
    """Response with list of sources."""
    sources: list[dict[str, Any]]


class MetricsResponse(BaseModel):
    """Response with gateway metrics."""
    sessions: int
    active_sessions: int
    tokens_retrieved: int
    tokens_delivered: int
    active_conflicts: int = 0
    source_health: list[dict[str, Any]] = []


class FeedbackResponse(BaseModel):
    """Feedback submission response."""
    status: str
    session_id: str
