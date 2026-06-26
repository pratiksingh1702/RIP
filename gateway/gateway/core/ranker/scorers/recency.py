"""Recency scorer."""

from datetime import datetime

from gateway.core.classifier.models import IntentType


class RecencyScorer:
    """Scores items based on recency."""

    def score(self, last_modified: datetime | None, intent: IntentType) -> float:
        """Calculate recency score based on intent."""
        if not last_modified:
            return 0.5

        days_old = (datetime.utcnow() - last_modified).days

        if intent == IntentType.BUG_FIX or intent == IntentType.INVESTIGATION:
            # Recent is better for bugs/investigation
            return max(0.1, 1.0 - (days_old / 30.0))
        else:
            # Stable (older) is better for architecture/docs
            return min(1.0, 0.5 + (days_old / 180.0))
