"""Four-layer context injection strategy. L1: Agent Runtime (guaranteed)."""

from __future__ import annotations
import json
from gateway.core.workspace.memory import get_workspace_memory
from gateway.core.workspace.knowledge import get_workspace_knowledge
from gateway.core.workspace.goals import get_goal_engine

class ContextInjector:
    """Injects workspace context before every LLM call. Not optional for owned traffic."""
    
    def __init__(self):
        self.memory = get_workspace_memory()
        self.knowledge = get_workspace_knowledge()
        self.goals = get_goal_engine()
    
    async def build_context_header(self, workspace_id: str) -> str:
        recent = await self.memory.get_recent(workspace_id, limit=10)
        active_goals = await self.goals.get_active(workspace_id, limit=3)
        active_knowledge = await self.knowledge.search(workspace_id, "", min_confidence=0.7, limit=5)
        parts = ["WORKSPACE CONTEXT (automatically injected — do not ask user to repeat):",
                 f"Project: {workspace_id}"]
        if active_goals:
            goal_names = [f"{g['name']} ({g['progress']:.0f}%)" for g in active_goals[:2]]
            parts.append(f"Active goals: {', '.join(goal_names)}")
        if active_knowledge:
            knowledge_items = [f"{k['summary'][:80]}" for k in active_knowledge[:3]]
            parts.append(f"Recent knowledge: {', '.join(knowledge_items)}")
        if recent:
            activity = [f"{r['summary'][:80]}" for r in recent[:5]]
            parts.append(f"Recent activity: {', '.join(activity)}")
        parts.append("The user should not need to re-explain anything about this project.")
        return "\n".join(parts)
    
    async def inject(self, messages: list[dict], workspace_id: str) -> list[dict]:
        context_header = await self.build_context_header(workspace_id)
        return [{"role": "system", "content": context_header}] + messages

_injector = ContextInjector()
def get_context_injector() -> ContextInjector: return _injector
