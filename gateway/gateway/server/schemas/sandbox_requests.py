"""Sandbox request/response schemas."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field

class CreateSandboxRequest(BaseModel):
    project_id: str
    environment: str = "python"
    custom_config: dict[str, Any] | None = None

class TerminalInputRequest(BaseModel):
    command: str

class TerminalApproveRequest(BaseModel):
    command: str

class FileWriteRequest(BaseModel):
    path: str
    content: str

class SnapshotRequest(BaseModel):
    label: str = ""

class RemoteConnectRequest(BaseModel):
    machine_url: str
    api_key: str

class SandboxResponse(BaseModel):
    sandbox_id: str
    project_id: str
    user_id: str = ""
    environment: str
    status: str
    image: str = ""
    created_at: str = ""

class SandboxStatusResponse(BaseModel):
    sandbox_id: str
    status: str
    cpu_percent: float = 0.0
    memory_used_bytes: int = 0
    memory_limit_bytes: int = 0
    memory_percent: float = 0.0

class TerminalEvent(BaseModel):
    type: str
    terminal_id: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = ""
