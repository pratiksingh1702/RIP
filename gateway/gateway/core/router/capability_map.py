"""Tool Capability Map for the Gateway Router."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

class ToolCategory(StrEnum):
    CORE_GATEWAY = "core_gateway"
    KNOWLEDGE = "knowledge"
    ORGANISATION = "organisation"
    WORKSPACE = "workspace"
    RIP_NATIVE = "rip_native"
    DEVELOPER = "developer"
    CUSTOM = "custom"

class EffortTier(StrEnum):
    FAST = "fast"
    MEDIUM = "medium"
    DEEP = "deep"
    AUTO = "auto"

@dataclass
class BehaviorDef:
    actions: list[str]
    summary: str

@dataclass
class ToolCapability:
    id: str
    category: ToolCategory
    min_effort: str
    behavior_by_effort: dict[str, BehaviorDef]
    parallel_safe: bool = True
    discovered_at: str = ""
    manifest_hash: str = ""
    api_version: str = ""
    enabled: bool = True

    def validate_monotonic(self) -> None:
        """Ensure actions at higher tiers are supersets of lower tiers."""
        tiers = ["fast", "medium", "deep"]
        present = [t for t in tiers if t in self.behavior_by_effort]
        for lower, higher in zip(present, present[1:]):
            lower_actions = set(self.behavior_by_effort[lower].actions)
            higher_actions = set(self.behavior_by_effort[higher].actions)
            if not lower_actions.issubset(higher_actions):
                raise ValueError(
                    f"{self.id}: {higher} actions must be a superset of {lower} actions"
                )

# Central registry of tool capabilities
_REGISTRY: dict[str, ToolCapability] = {}

def register_tool(tool: ToolCapability) -> None:
    tool.validate_monotonic()
    _REGISTRY[tool.id] = tool

def get_capability_map() -> dict[str, ToolCapability]:
    return _REGISTRY

# Default tools from the architecture document
register_tool(ToolCapability(
    id="git_history",
    category=ToolCategory.DEVELOPER,
    min_effort="fast",
    behavior_by_effort={
        "fast": BehaviorDef(["commit_history"], "Recent commits, diffs, blame for active branch"),
        "medium": BehaviorDef(["commit_history", "code_diffs", "file_changes"], "Adds line-level diffs and changed-file listings"),
        "deep": BehaviorDef(["commit_history", "code_diffs", "file_changes", "pr_history"], "Full PR and issue history cross-reference"),
    }
))

register_tool(ToolCapability(
    id="workspace_memory",
    category=ToolCategory.CORE_GATEWAY,
    min_effort="fast",
    behavior_by_effort={
        "fast": BehaviorDef(["read_memory"], "Session/workspace memory buffer"),
        "medium": BehaviorDef(["read_memory", "search_memory"], "Full session history search"),
        "deep": BehaviorDef(["read_memory", "search_memory", "cross_session_graph"], "Cross-session memory graphs"),
    }
))

register_tool(ToolCapability(
    id="code_ast",
    category=ToolCategory.DEVELOPER,
    min_effort="medium",
    behavior_by_effort={
        "medium": BehaviorDef(["symbol_lookup", "call_graph"], "AST-based symbol/reference lookup"),
        "deep": BehaviorDef(["symbol_lookup", "call_graph", "full_traversal"], "Full codebase AST traversal"),
    }
))

register_tool(ToolCapability(
    id="docker_terminal",
    category=ToolCategory.CORE_GATEWAY,
    min_effort="deep",
    parallel_safe=False,
    behavior_by_effort={
        "deep": BehaviorDef(["execute_command"], "Docker sandbox exec, conflict locks"),
    }
))

register_tool(ToolCapability(
    id="agent_runs",
    category=ToolCategory.CORE_GATEWAY,
    min_effort="fast",
    behavior_by_effort={
        "fast": BehaviorDef(["list_runs"], "Recent agent executions"),
        "medium": BehaviorDef(["list_runs", "run_logs"], "Agent execution logs"),
        "deep": BehaviorDef(["list_runs", "run_logs", "agent_traces"], "Full agent execution traces"),
    }
))
