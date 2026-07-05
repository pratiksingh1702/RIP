"""Workflow DAG topological sorting."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


class WorkflowDAG:
    def __init__(self, blocks: list[dict[str, Any]], wires: list[dict[str, Any]] | None = None):
        self.blocks = blocks
        self.wires = wires or []

    def topological_order(self) -> list[str]:
        """Get the topological order of step IDs."""
        step_ids = [block["step_id"] for block in self.blocks]
        if not self.wires:
            return step_ids

        known_steps = set(step_ids)
        in_degree = {step_id: 0 for step_id in step_ids}
        downstream: dict[str, list[str]] = defaultdict(list)

        for wire in self.wires:
            source = wire.get("source_step_id")
            target = wire.get("target_step_id")
            if source not in known_steps or target not in known_steps:
                continue
            downstream[source].append(target)
            in_degree[target] += 1

        queue = deque(step_id for step_id in step_ids if in_degree[step_id] == 0)
        ordered: list[str] = []
        while queue:
            step_id = queue.popleft()
            ordered.append(step_id)
            for target in downstream[step_id]:
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    queue.append(target)

        if len(ordered) != len(step_ids):
            raise ValueError("Workflow canvas contains a circular dependency")
        return ordered

    def would_create_cycle(self, source_step_id: str, target_step_id: str) -> bool:
        """Return true when adding a source->target wire would create a cycle."""
        candidate_wires = [
            *self.wires,
            {"source_step_id": source_step_id, "target_step_id": target_step_id},
        ]
        try:
            WorkflowDAG(self.blocks, candidate_wires).topological_order()
        except ValueError:
            return True
        return False
