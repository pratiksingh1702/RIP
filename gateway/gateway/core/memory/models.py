"""Memory data models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from gateway.core.classifier.models import ClassificationResult


class Session(BaseModel):
    """Session model."""
    id: UUID
    agent_type: str
    task_description: str
    classification: ClassificationResult
    files_accessed: list[str] = Field(default_factory=list)
    nodes_accessed: list[str] = Field(default_factory=list)
    sources_used: list[str] = Field(default_factory=list)
    tokens_retrieved: int = 0
    tokens_delivered: int = 0
    tokens_saved: int = 0
    status: str = "in_progress"
    outcome: str | None = None
    files_modified: list[str] = Field(default_factory=list)
    started_at: datetime
    ended_at: datetime | None = None
    git_branch: str | None = None
    project_id: UUID | None = None
    user_id: str | None = None


class Conflict(BaseModel):
    """Conflict between sessions."""
    session_id: UUID
    agent_type: str
    task_description: str
    overlapping_files: list[str]
    started_at: datetime
    risk_level: str


class BridgedContext(BaseModel):
    """Context bridged from a previous session."""
    from_session_id: UUID
    files_previously_accessed: list[str]
    task_summary: str
    completed_at: datetime
    suggestion: str
