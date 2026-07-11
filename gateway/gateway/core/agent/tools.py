"""Tool definitions and registry for the Agent Runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict
    handler: Callable[..., Awaitable[ToolResult]]
    requires_approval: bool = False
    risk_level: str = "low"


@dataclass
class ToolResult:
    ok: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_all(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get_for_llm(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
            }
            for t in self._tools.values()
        ]
