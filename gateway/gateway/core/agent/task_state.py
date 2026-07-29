"""Task state data models for Supervisor & Main Agent shared tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class LogEventType(str, Enum):
    PLAN_CREATED = "plan_created"
    STEP_STARTED = "step_started"
    DIFF_PROPOSED = "diff_proposed"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    FILE_TOUCHED = "file_touched"
    SIGNAL_EMITTED = "signal_emitted"
    CHECKPOINT_CREATED = "checkpoint_created"
    SUPERVISOR_REASONING = "supervisor_reasoning"


class FilePlan(BaseModel):
    file_path: str
    target_lines: str = ""
    rationale: str = ""
    proposed_diff: str = ""
    ast_impact: str = ""
    has_high_fan_in: bool = False
    dependent_count: int = 0


class StepStatus(BaseModel):
    step_id: str
    title: str
    description: str = ""
    target_files: list[str] = Field(default_factory=list)
    status: str = "pending"  # pending | running | completed | failed | skipped | paused
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    file_plans: list[FilePlan] = Field(default_factory=list)
    commit_hash: str | None = None


class TaskProgress(BaseModel):
    task_id: str
    original_query: str
    total_steps: int = 0
    current_step_index: int = 0
    current_step_id: str | None = None
    steps: list[StepStatus] = Field(default_factory=list)
    git_branch: str | None = None
    status: str = "running"  # running | paused | completed | failed | retasked
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    estimated_remaining_seconds: int = 0
    files_changed: list[str] = Field(default_factory=list)
    risk_level: str = "low"  # low | medium | high | critical


class StatusLogEvent(BaseModel):
    seq: int
    task_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: LogEventType
    step_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
