"""Workflow run state management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StepState:
    step_id: str
    block_id: str
    status: str = "pending"
    inputs: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


@dataclass
class RunState:
    step_states: dict[str, StepState] = field(default_factory=dict)
    trigger_query: str | None = None
    missing_inputs: dict[str, str] = field(default_factory=dict)
    provided_inputs: dict[str, Any] = field(default_factory=dict)
    final_output: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_states": {
                step_id: {
                    "step_id": step.step_id,
                    "block_id": step.block_id,
                    "status": step.status,
                    "inputs": step.inputs,
                    "output": step.output,
                    "error": step.error,
                    "started_at": step.started_at,
                    "completed_at": step.completed_at,
                }
                for step_id, step in self.step_states.items()
            },
            "trigger_query": self.trigger_query,
            "missing_inputs": self.missing_inputs,
            "provided_inputs": self.provided_inputs,
            "final_output": self.final_output,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunState:
        step_states = {}
        for step_id, step_data in data.get("step_states", {}).items():
            step_states[step_id] = StepState(
                step_id=step_data["step_id"],
                block_id=step_data["block_id"],
                status=step_data["status"],
                inputs=step_data.get("inputs", {}),
                output=step_data.get("output"),
                error=step_data.get("error"),
                started_at=step_data.get("started_at"),
                completed_at=step_data.get("completed_at"),
            )
        return cls(
            step_states=step_states,
            trigger_query=data.get("trigger_query"),
            missing_inputs=data.get("missing_inputs", {}),
            provided_inputs=data.get("provided_inputs", {}),
            final_output=data.get("final_output"),
        )
