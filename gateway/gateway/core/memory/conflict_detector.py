"""Conflict detector for overlapping sessions."""

from uuid import UUID

from .models import Conflict, Session
from .store import get_session_store


class ConflictDetector:
    """Detects conflicts between active sessions."""

    def __init__(self):
        self.store = get_session_store()

    async def detect(
        self,
        current_session_id: UUID,
        current_files: list[str]
    ) -> list[Conflict]:
        """Detect conflicts with other active sessions."""
        active_sessions = await self.store.get_active_sessions(
            exclude_session_id=current_session_id
        )

        conflicts = []
        current_file_set = set(current_files)

        for session in active_sessions:
            session_file_set = set(session.files_accessed)
            overlap = current_file_set & session_file_set

            if overlap:
                conflicts.append(
                    Conflict(
                        session_id=session.id,
                        agent_type=session.agent_type,
                        task_description=session.task_description,
                        overlapping_files=list(overlap),
                        started_at=session.started_at,
                        risk_level=self._assess_conflict_risk(list(overlap), session)
                    )
                )

        return conflicts

    def _assess_conflict_risk(
        self,
        overlapping_files: list[str],
        other_session: Session
    ) -> str:
        """Assess the risk level of a conflict."""
        high_risk_patterns = ["payment", "auth", "security", "core"]
        for file_path in overlapping_files:
            if any(pattern in file_path.lower() for pattern in high_risk_patterns):
                return "high"
        return "medium"


# Global detector instance
_detector: ConflictDetector | None = None


def get_conflict_detector() -> ConflictDetector:
    """Get the global conflict detector."""
    global _detector
    if _detector is None:
        _detector = ConflictDetector()
    return _detector
