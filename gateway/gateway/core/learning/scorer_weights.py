"""Scorer weight adjustment from feedback."""

import structlog
from typing import Dict, Optional
from gateway.config import settings

logger = structlog.get_logger(__name__)


class ScorerWeights:
    """Manage and adjust scorer weights based on feedback."""

    DEFAULT_WEIGHTS = {
        "semantic": 0.3,
        "recency": 0.2,
        "pattern": 0.15,
        "authority": 0.15,
        "centrality": 0.2,
    }

    def __init__(self):
        self._weights = self.DEFAULT_WEIGHTS.copy()

    async def adjust_weights_from_feedback(self, feedback: dict):
        """Adjust weights based on feedback."""
        rating = feedback.get("rating")
        missing_context = bool(feedback.get("missing_context"))
        irrelevant_context = bool(feedback.get("irrelevant_context"))

        if rating is not None and int(rating) >= 4 and not missing_context:
            logger.info("Feedback positive; scorer weights unchanged", feedback=feedback)
            return

        if missing_context:
            self._weights["semantic"] += 0.04
            self._weights["centrality"] += 0.02
            self._weights["recency"] -= 0.03
        if irrelevant_context:
            self._weights["pattern"] += 0.03
            self._weights["authority"] += 0.02
            self._weights["semantic"] -= 0.02
        if rating is not None and int(rating) <= 2:
            self._weights["semantic"] += 0.02
            self._weights["pattern"] += 0.02

        self._normalize()
        logger.info("Adjusted scorer weights from feedback", weights=self._weights)

    def get_weights(self) -> Dict[str, float]:
        """Get current scorer weights."""
        return self._weights.copy()

    def _normalize(self) -> None:
        for key, value in self._weights.items():
            self._weights[key] = max(0.05, min(0.7, value))
        total = sum(self._weights.values()) or 1.0
        self._weights = {key: value / total for key, value in self._weights.items()}


_scorer_weights: Optional[ScorerWeights] = None


def get_scorer_weights() -> ScorerWeights:
    """Get the global scorer weights manager."""
    global _scorer_weights
    if _scorer_weights is None:
        _scorer_weights = ScorerWeights()
    return _scorer_weights
