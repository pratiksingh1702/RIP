"""Base block definitions."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class BlockKind(Enum):
    TRIGGER = "trigger"
    RETRIEVAL = "retrieval"
    PROMPT = "prompt"
    MODEL = "model"
    TOOL = "tool"
    APPROVAL = "approval"
    VERIFICATION = "verification"
    DEPLOYMENT = "deployment"
    NOTIFICATION = "notification"
    MEMORY = "memory"
    CUSTOM = "custom"


@dataclass
class ExecutionContext:
    session_id: str | None = None
    workflow_run_id: str | None = None
    project_id: str | None = None
    user_id: str | None = None


@dataclass
class BlockResult:
    ok: bool
    output: dict[str, Any] | None = None
    error: str | None = None
    events: list[dict[str, Any]] | None = None


class Block(Protocol):
    id: str
    kind: BlockKind
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    config_schema: dict[str, Any]
    requires_capabilities: list[str]

    @abstractmethod
    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        ...

    @abstractmethod
    def describe(self) -> dict[str, Any]:
        ...
