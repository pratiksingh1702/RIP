"""Small intent helper shared by runtime services."""

from __future__ import annotations

from enum import StrEnum


class RuntimeIntent(StrEnum):
    SEARCH = "search"
    EXPLAIN = "explain"
    TRACE = "trace"
    IMPACT = "impact"
    ARCHITECTURE = "architecture"
    METRICS = "metrics"
    DEPENDENCIES = "dependencies"
    DEAD_CODE = "dead_code"
    ONBOARD = "onboard"


def classify_runtime_intent(text: str) -> RuntimeIntent:
    lowered = text.lower()
    if any(word in lowered for word in ("impact", "risk", "affected")):
        return RuntimeIntent.IMPACT
    if any(word in lowered for word in ("trace", "flow", "workflow", "call chain")):
        return RuntimeIntent.TRACE
    if any(word in lowered for word in ("dependency", "depends", "imports")):
        return RuntimeIntent.DEPENDENCIES
    if any(word in lowered for word in ("architecture", "modules", "diagram")):
        return RuntimeIntent.ARCHITECTURE
    return RuntimeIntent.EXPLAIN
