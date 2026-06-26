"""Memory data models."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel

from gateway.core.classifier.models import ClassificationResult


class Session(BaseModel):
    """Session model."""
    id: UUID
    agent_type: str
    task_description: str
    classification: ClassificationResult
    files_accessed: List[str] = []
    nodes_accessed: List[str] = []
    sources_used: List[str] = []
    tokens_retrieved: int = 0
    tokens_delivered: int = 0
    tokens_saved: int = 0
    status: str = "in_progress"
    outcome: Optional[str] = None
    files_modified: List[str] = []
    started_at: datetime
    ended_at: Optional[datetime] = None
    git_branch: Optional[str] = None
    project_id: Optional[UUID] = None
    user_id: Optional[str] = None


class Conflict(BaseModel):
    """Conflict between sessions."""
    session_id: UUID
    agent_type: str
    task_description: str
    overlapping_files: List[str]
    started_at: datetime
    risk_level: str


class BridgedContext(BaseModel):
    """Context bridged from a previous session."""
    from_session_id: UUID
    files_previously_accessed: List[str]
    task_summary: str
    completed_at: datetime
    suggestion: str
