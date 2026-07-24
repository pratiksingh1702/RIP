"""Sandbox Session — per-user per-project session management."""
from __future__ import annotations
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

class SandboxSession:
    def __init__(self, sandbox_id: str, project_id: str, user_id: str):
        self.session_id = str(uuid4())
        self.sandbox_id = sandbox_id
        self.project_id = project_id
        self.user_id = user_id
        self.created_at = datetime.now(UTC)
        self.last_activity = datetime.now(UTC)
        self.commands_run: list[dict[str, Any]] = []
        self.is_shared = False
        self.shared_with: list[str] = []

    def record_command(self, command: str, exit_code: int, output: str) -> None:
        self.commands_run.append({"command": command, "exit_code": exit_code, "output": output[:500], "timestamp": datetime.now(UTC).isoformat()})
        self.last_activity = datetime.now(UTC)

    def is_idle(self, timeout_seconds: int = 7200) -> bool: return (datetime.now(UTC) - self.last_activity).total_seconds() > timeout_seconds

    def to_dict(self) -> dict[str, Any]:
        return {"session_id": self.session_id, "sandbox_id": self.sandbox_id, "project_id": self.project_id, "user_id": self.user_id, "created_at": self.created_at.isoformat(), "last_activity": self.last_activity.isoformat(), "commands_count": len(self.commands_run), "is_shared": self.is_shared}

class SessionManager:
    def __init__(self): self._sessions: dict[str, SandboxSession] = {}
    def create_session(self, sandbox_id: str, project_id: str, user_id: str) -> SandboxSession:
        s = SandboxSession(sandbox_id, project_id, user_id); self._sessions[s.session_id] = s
        logger.info("Session created: %s", s.session_id); return s
    def get_session(self, session_id: str) -> SandboxSession | None: return self._sessions.get(session_id)
    def close_session(self, session_id: str) -> bool:
        if session_id in self._sessions: del self._sessions[session_id]; return True
        return False
    def get_user_sessions(self, user_id: str) -> list[SandboxSession]: return [s for s in self._sessions.values() if s.user_id == user_id]
    def get_project_sessions(self, project_id: str) -> list[SandboxSession]: return [s for s in self._sessions.values() if s.project_id == project_id]
    def get_active_session_count(self) -> int: return len(self._sessions)

_session_manager: SessionManager | None = None
def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None: _session_manager = SessionManager()
    return _session_manager
