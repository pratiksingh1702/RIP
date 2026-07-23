"""Two-tier confidence scoring for workspace knowledge."""

from enum import Enum

class ConfidenceTier(Enum):
    ACTIVE = "active"
    SUGGESTION = "suggestion"
    PENDING = "pending"
    NOISE = "noise"
    APPROVED = "approved"
    REJECTED = "rejected"

SOURCE_SCORES = {
    "human_decision": 1.0,
    "pattern_detection": 0.6,
    "llm_suggestion": 0.4,
    "cross_validation": 0.7,
    "agent_execution": 0.75,
    "workflow_result": 0.65,
}

def compute_confidence(source_type: str, frequency: int = 0,
                       cross_val_count: int = 0,
                       human_override: str | None = None) -> tuple[float, ConfidenceTier]:
    if human_override == "approved": return (0.98, ConfidenceTier.APPROVED)
    if human_override == "rejected": return (0.0, ConfidenceTier.REJECTED)
    source_score = SOURCE_SCORES.get(source_type, 0.3)
    frequency_score = min(frequency / 20, 1.0) if frequency > 0 else 0.0
    cross_val_score = min(cross_val_count * 0.3, 1.0) if cross_val_count > 0 else 0.0
    confidence = round(source_score * 0.5 + frequency_score * 0.3 + cross_val_score * 0.2, 2)
    if confidence >= 0.70: tier = ConfidenceTier.ACTIVE
    elif confidence >= 0.50: tier = ConfidenceTier.SUGGESTION
    elif confidence >= 0.30: tier = ConfidenceTier.PENDING
    else: tier = ConfidenceTier.NOISE
    return (confidence, tier)

def get_surfacing_rule(confidence: float, tier: ConfidenceTier) -> str:
    if tier == ConfidenceTier.APPROVED or confidence >= 0.95: return "active_inject"
    elif tier == ConfidenceTier.ACTIVE or confidence >= 0.70: return "inject_with_context"
    elif tier == ConfidenceTier.SUGGESTION: return "surface_with_caveat"
    elif tier == ConfidenceTier.PENDING: return "store_hide"
    else: return "store_silent"
