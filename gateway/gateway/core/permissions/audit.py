"""Audit logging utilities."""

import structlog
from typing import List

from .models import AuditLogEntry

logger = structlog.get_logger(__name__)


class AuditLogger:
    """Audit logger for tracking access decisions."""

    def __init__(self):
        self._logs: List[AuditLogEntry] = []

    def log(self, entry: AuditLogEntry):
        """Log an audit entry."""
        self._logs.append(entry)
        logger.info(
            "Audit log entry",
            timestamp=entry.timestamp,
            session_id=entry.session_id,
            action=entry.action,
            allowed=entry.allowed
        )

    def get_logs(self, session_id: str | None = None) -> List[AuditLogEntry]:
        """Get audit logs, optionally filtered by session ID."""
        if session_id:
            return [log for log in self._logs if log.session_id == session_id]
        return list(self._logs)

    def clear(self):
        """Clear all audit logs."""
        self._logs = []
