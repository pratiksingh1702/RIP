"""Workspace State — single source of truth for current workspace context."""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class WorkspaceState:
    """Every component reads current state from here instead of reconstructing it."""
    workspace_id: str
    organization_id: str | None = None
    active_project_id: str | None = None
    active_repository_id: str | None = None
    active_branch: str | None = None
    current_user_id: str | None = None
    active_agents: list[str] = field(default_factory=list)
    active_workflows: list[str] = field(default_factory=list)
    pending_approvals: list[dict] = field(default_factory=list)
    repository_health: dict | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_state_instances: dict[str, WorkspaceState] = {}


def get_workspace_state(workspace_id: str) -> WorkspaceState:
    if workspace_id not in _state_instances:
        _state_instances[workspace_id] = WorkspaceState(workspace_id=workspace_id)
    return _state_instances[workspace_id]
