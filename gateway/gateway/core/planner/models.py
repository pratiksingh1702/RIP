"""Planner data models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from gateway.core.classifier.models import ClassificationResult


class SourceQuery(BaseModel):
    """Query to send to a source."""
    source: str  # "rip", "github", "jira", "slack"
    query_type: str  # "trace", "search", "architecture", "impact"
    query_params: dict[str, Any]
    priority: int  # 1=critical, 2=important, 3=nice-to-have
    estimated_tokens: int
    timeout_seconds: float = 5.0


class RetrievalStep(BaseModel):
    """Step in the retrieval plan."""
    queries: list[SourceQuery]
    parallel: bool = True
    condition: str = "always"


class Plan(BaseModel):
    """Complete retrieval plan."""
    classification: ClassificationResult
    steps: list[RetrievalStep]
    token_budget: int
    token_allocation: dict[str, int]  # source -> token budget
    estimated_tokens_raw: int
    created_at: datetime
