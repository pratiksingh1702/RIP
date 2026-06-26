"""Context bridge between related sessions."""

from typing import Optional

from .models import BridgedContext, Session
from .store import get_session_store


class ContextBridge:
    """Bridges context from recent related sessions."""

    def __init__(self):
        self.store = get_session_store()

    async def get_bridged_context(
        self,
        domain: str,
        current_task: str
    ) -> Optional[BridgedContext]:
        """Get context from a recent related session."""
        recent = await self.store.get_recent_sessions(domain, hours=24)

        if not recent:
            return None

        # Find most relevant (simple heuristic: first one)
        most_relevant = recent[0]

        return BridgedContext(
            from_session_id=most_relevant.id,
            files_previously_accessed=most_relevant.files_accessed,
            task_summary=most_relevant.task_description[:200],
            completed_at=most_relevant.ended_at,
            suggestion=f"Previous session worked on {domain}. Pre-loading context."
        )


# Global bridge instance
_bridge: ContextBridge | None = None


def get_context_bridge() -> ContextBridge:
    """Get the global context bridge."""
    global _bridge
    if _bridge is None:
        _bridge = ContextBridge()
    return _bridge
