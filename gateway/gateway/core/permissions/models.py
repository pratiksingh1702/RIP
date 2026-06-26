"""Permission models."""

from enum import StrEnum
from pydantic import BaseModel
from typing import List


class UserRole(StrEnum):
    """Supported user roles."""
    JUNIOR_DEV = "junior_dev"
    DEVELOPER = "developer"
    SENIOR_DEV = "senior_dev"
    CI_AGENT = "ci_agent"


class AccessPolicy(BaseModel):
    """Access policy definition."""
    role: UserRole
    allowed_sources: List[str]
    max_token_budget: int
    can_access_sensitive_domains: bool


class AuditLogEntry(BaseModel):
    """Audit log entry."""
    timestamp: str
    session_id: str
    user_id: str | None
    role: UserRole
    action: str
    source: str | None
    allowed: bool
    reason: str | None
