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
        # Placeholder for weight adjustment logic
        logger.info("Adjusting scorer weights from feedback", feedback=feedback)

    def get_weights(self) -> Dict[str, float]:
        """Get current scorer weights."""
        return self._weights.copy()


_scorer_weights: Optional[ScorerWeights] = None


def get_scorer_weights() -> ScorerWeights:
    """Get the global scorer weights manager."""
    global _scorer_weights
    if _scorer_weights is None:
        _scorer_weights = ScorerWeights()
    return _scorer_weights
