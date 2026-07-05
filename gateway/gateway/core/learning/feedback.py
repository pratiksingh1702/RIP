"""Feedback handling and learning loop."""


import structlog

logger = structlog.get_logger(__name__)


class FeedbackStore:
    """Store for feedback on context quality."""

    def __init__(self):
        self._feedback: dict[str, list] = {}

    async def add_feedback(self, session_id: str, feedback: dict):
        """Add feedback for a session."""
        if session_id not in self._feedback:
            self._feedback[session_id] = []
        self._feedback[session_id].append(feedback)
        logger.info("Received feedback", session_id=session_id, feedback=feedback)


_feedback_store: FeedbackStore | None = None


def get_feedback_store() -> FeedbackStore:
    """Get the global feedback store."""
    global _feedback_store
    if _feedback_store is None:
        _feedback_store = FeedbackStore()
    return _feedback_store
