"""Data models for intent classification."""

from enum import StrEnum

from pydantic import BaseModel


class IntentType(StrEnum):
    """Supported intent types."""
    BUG_FIX = "bug_fix"
    FEATURE_ADDITION = "feature_addition"
    REFACTOR = "refactor"
    ARCHITECTURAL_QUESTION = "architectural_question"
    INVESTIGATION = "investigation"
    DOCUMENTATION = "documentation"


class RiskLevel(StrEnum):
    """Risk level for an intent."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ClassificationResult(BaseModel):
    """Result of intent classification."""
    intent: IntentType
    confidence: float
    domain: str
    risk_level: RiskLevel
    strategy: str  # "rules" or "llm_fallback"
    domain_keywords_found: list[str]
    raw_task: str
