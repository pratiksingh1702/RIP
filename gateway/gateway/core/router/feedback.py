"""Route Feedback Logger — tracks routing accuracy for continuous improvement."""
from __future__ import annotations
import logging
from datetime import UTC, datetime
from typing import Any
from gateway.core.router.models import PathType, RouteDecision

logger = logging.getLogger(__name__)

class RouteFeedbackLogger:
    """Logs routing decisions and user feedback for tuning."""

    def __init__(self):
        self._log: list[dict[str, Any]] = []

    def log_route(self, query: str, decision: RouteDecision, project_id: str | None, user_id: str | None) -> None:
        """Record a routing decision."""
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "query": query[:200],
            "path": decision.path.value,
            "confidence": decision.confidence,
            "escalated": decision.escalated,
            "escalated_from": decision.escalated_from,
            "project_id": project_id,
            "user_id": user_id,
        }
        self._log.append(entry)
        if len(self._log) > 1000:
            self._log = self._log[-500:]

    def log_reask(self, query: str, original_path: PathType) -> None:
        """Log when a user re-asks — signal of potential misroute."""
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": "reask",
            "query": query[:200],
            "original_path": original_path.value,
        }
        self._log.append(entry)
        logger.info("Route feedback: re-ask detected for query=%s, path=%s", query[:80], original_path)

    def log_clarification_response(self, query: str, selected_interpretation: str) -> None:
        """Log which interpretation the user selected after clarification."""
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": "clarification_selected",
            "query": query[:200],
            "selected": selected_interpretation[:200],
        }
        self._log.append(entry)

    def get_stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        if not self._log:
            return {"total": 0}
        paths = {}
        escalations = 0
        reasks = 0
        for entry in self._log:
            p = entry.get("path", "unknown")
            paths[p] = paths.get(p, 0) + 1
            if entry.get("escalated"):
                escalations += 1
            if entry.get("event") == "reask":
                reasks += 1
        return {
            "total": len(self._log),
            "by_path": paths,
            "escalations": escalations,
            "reasks": reasks,
            "escalation_rate": escalations / max(1, len(self._log)),
            "reask_rate": reasks / max(1, len(self._log)),
        }

_feedback: RouteFeedbackLogger | None = None
def get_route_feedback() -> RouteFeedbackLogger:
    global _feedback
    if _feedback is None:
        _feedback = RouteFeedbackLogger()
    return _feedback
