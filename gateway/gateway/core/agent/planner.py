"""DAG Execution Planner - decomposes complex tasks into parallel/sequential subtasks."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from enum import Enum

from gateway.core.llm_pool.router import LLMConfig, get_llm_router

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are a software engineering task planner. Given a complex engineering task, break it into subtasks.

Output ONLY valid JSON in this exact format:
{
    "subtasks": [
        {
            "id": "1",
            "title": "Read and analyze auth module",
            "description": "Read all files in auth module and trace dependencies",
            "depends_on": [],
            "estimated_turns": 5
        },
        {
            "id": "2", 
            "title": "Add OAuth2 provider",
            "description": "Create OAuth2 provider class with token refresh",
            "depends_on": ["1"],
            "estimated_turns": 8
        }
    ]
}

Rules:
1. First subtask should ALWAYS be reading/understanding the affected code
2. List dependencies between subtasks (which must complete before others start)
3. Group independent subtasks so they can run in parallel
4. Keep each subtask focused on 1-5 files
5. Last subtask should be verification/testing
"""


class SubtaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Subtask:
    id: str
    title: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    estimated_turns: int = 5
    status: SubtaskStatus = SubtaskStatus.PENDING
    result_summary: str = ""
    error: str | None = None
    changes_made: list[dict] = field(default_factory=list)


@dataclass
class ExecutionPlan:
    query: str
    subtasks: list[Subtask]
    total_estimated_turns: int = 0

    @property
    def ready_subtasks(self) -> list[Subtask]:
        """Return subtasks whose dependencies are all completed."""
        completed_ids = {s.id for s in self.subtasks if s.status == SubtaskStatus.COMPLETED}
        return [
            s for s in self.subtasks 
            if s.status == SubtaskStatus.PENDING 
            and all(dep in completed_ids for dep in s.depends_on)
        ]

    @property
    def is_complete(self) -> bool:
        return all(s.status in (SubtaskStatus.COMPLETED, SubtaskStatus.SKIPPED, SubtaskStatus.FAILED) for s in self.subtasks)

    @property
    def has_failures(self) -> bool:
        return any(s.status == SubtaskStatus.FAILED for s in self.subtasks)


class ExecutionPlanner:
    """Decomposes complex engineering tasks into DAG-based execution plans."""

    MAX_PLAN_TOKENS = 2000

    async def plan(self, query: str, rip_context: dict, llm_config: LLMConfig) -> ExecutionPlan:
        """Generate an execution plan from a complex task."""
        # For simple tasks, create a single-subtask plan
        if self._is_simple_task(query):
            return ExecutionPlan(
                query=query,
                subtasks=[Subtask(id="1", title=query, description=query, estimated_turns=10)],
                total_estimated_turns=10,
            )

        try:
            router = get_llm_router()
            context_summary = json.dumps({
                "files": rip_context.get("files", [])[:10],
                "architecture": str(rip_context.get("architecture", ""))[:500],
            })

            prompt = f"Task: {query}\n\nRepository Context:\n{context_summary}\n\nBreak this into subtasks."
            
            response = await router.query_llm(
                prompt=prompt,
                config=llm_config,
                system_prompt=PLANNER_SYSTEM_PROMPT,
                max_tokens=self.MAX_PLAN_TOKENS,
            )

            plan_data = self._parse_plan(response)
            subtasks = []
            for item in plan_data.get("subtasks", []):
                subtasks.append(Subtask(
                    id=str(item.get("id", len(subtasks) + 1)),
                    title=str(item.get("title", item.get("description", ""))),
                    description=str(item.get("description", "")),
                    depends_on=[str(d) for d in item.get("depends_on", [])],
                    estimated_turns=int(item.get("estimated_turns", 5)),
                ))

            if not subtasks:
                subtasks = [Subtask(id="1", title=query, description=query, estimated_turns=10)]

            total_turns = sum(s.estimated_turns for s in subtasks)
            logger.info("PLANNER: Created plan with %d subtasks, ~%d total turns", len(subtasks), total_turns)

            return ExecutionPlan(query=query, subtasks=subtasks, total_estimated_turns=total_turns)

        except Exception as e:
            logger.warning("PLANNER: Planning failed, using single-task fallback: %s", e)
            return ExecutionPlan(
                query=query,
                subtasks=[Subtask(id="1", title=query, description=query, estimated_turns=10)],
                total_estimated_turns=10,
            )

    def _is_simple_task(self, query: str) -> bool:
        """Detect if a task is simple enough to skip detailed planning."""
        query_lower = query.lower()
        simple_patterns = [
            "list file", "read file", "show file", "what is", "explain",
            "find ", "search ", "grep ", "locate ",
        ]
        return any(pattern in query_lower for pattern in simple_patterns)

    def _parse_plan(self, response: str) -> dict:
        """Extract JSON plan from LLM response."""
        import re
        # Try to find JSON block
        json_match = re.search(r'\{[^{}]*"subtasks"\s*:\s*\[.*?\][^{}]*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # Try full response as JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        return {"subtasks": []}


_planner = ExecutionPlanner()


def get_execution_planner() -> ExecutionPlanner:
    return _planner
