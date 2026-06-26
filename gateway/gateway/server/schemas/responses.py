"""HTTP response schemas."""

from pydantic import BaseModel
from typing import List, Optional, Any

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
    context: List[ContextItem]
    tokens_used: int
    conflicts: List[dict]
    warnings: List[str]


class ValidateChangeResponse(BaseModel):
    """Response to validate change request."""
    risk_level: str
    affected_files: List[str]
    impact_summary: str
    warnings: List[str]
    error: Optional[str] = None


class SourceListResponse(BaseModel):
    """Response with list of sources."""
    sources: List[dict[str, Any]]


class MetricsResponse(BaseModel):
    """Response with gateway metrics."""
    sessions: int
    active_sessions: int
    tokens_retrieved: int
    tokens_delivered: int
