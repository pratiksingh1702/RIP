"""Workflow policy checks for write-mode blocks."""

from __future__ import annotations

from sqlalchemy import select

from gateway.storage.database import async_session_factory
from gateway.storage.models import WorkflowPolicy


async def workflow_action_allowed(action: str, repo: str | None = None) -> tuple[bool, str | None]:
    """Return whether a write action is allowed by the single-user policy table."""
    async with async_session_factory() as session:
        policy = (
            await session.execute(
                select(WorkflowPolicy).where(WorkflowPolicy.action == action)
            )
        ).scalar_one_or_none()
        if policy is None:
            return True, None
        if policy.allowed_repos and repo and repo not in policy.allowed_repos:
            return False, f"Workflow policy blocks {action} for repo {repo}"
        if policy.allowed_repos and not repo:
            return False, f"Workflow policy for {action} requires a target repo"
        if policy.requires_approval:
            return False, f"Workflow policy requires approval before {action}"
        return True, None
