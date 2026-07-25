"""Router data models — path types, decisions, cache keys."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
import hashlib

class PathType(StrEnum):
    FAST = "fast"
    MEDIUM = "medium"
    DEEP = "deep"

@dataclass
class RouteDecision:
    path: PathType
    confidence: float
    reasoning: str = ""
    suggested_sources: list[str] = field(default_factory=list)
    needs_llm: bool = False
    urgency: str = "normal"
    needs_clarification: bool = False
    suggested_interpretations: list[str] = field(default_factory=list)
    escalated: bool = False
    escalated_from: str | None = None

@dataclass
class RouteCacheKey:
    normalized_query: str
    project_id: str
    workspace_id: str
    user_role: str
    def to_hash(self) -> str:
        raw = f"{self.normalized_query}:{self.project_id}:{self.workspace_id}:{self.user_role}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

@dataclass
class RouteCacheEntry:
    key: RouteCacheKey
    decision: RouteDecision
    cached_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ttl_seconds: int = 300
    @property
    def is_valid(self) -> bool:
        return (datetime.now(UTC) - self.cached_at).total_seconds() < self.ttl_seconds

CONFIDENCE_THRESHOLDS = {
    PathType.FAST:    {"accept": 0.80, "escalate_to": PathType.MEDIUM, "below_accept": PathType.MEDIUM, "below_escalate": PathType.DEEP},
    PathType.MEDIUM:  {"accept": 0.50, "escalate_to": PathType.DEEP,   "below_accept": PathType.DEEP,   "below_escalate": PathType.DEEP},
    PathType.DEEP:    {"accept": 0.40, "escalate_to": None,            "below_accept": PathType.DEEP,   "below_escalate": None},
}
