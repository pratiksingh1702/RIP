"""Routing Context Gatherer — builds live context snapshot for the Router LLM."""
from __future__ import annotations
import logging
from typing import Any
from gateway.core.workspace.memory import get_workspace_memory
from gateway.core.workspace.knowledge import get_workspace_knowledge
from gateway.core.workspace.goals import get_goal_engine
from gateway.core.sources.registry import get_source_registry

logger = logging.getLogger(__name__)

class RoutingContextGatherer:
    """Gathers live workspace context to help the Router LLM make informed decisions."""

    def __init__(self):
        self._memory = get_workspace_memory()
        self._knowledge = get_workspace_knowledge()
        self._goals = get_goal_engine()
        self._registry = get_source_registry()

    async def gather(self, project_id: str | None, user_id: str | None, role: str) -> dict[str, Any]:
        """Build a context snapshot for the Router LLM."""
        ctx: dict[str, Any] = {
            "project_id": project_id or "none",
            "user_role": role,
            "available_sources": [],
            "active_goals": [],
            "recent_activity_summary": "",
            "knowledge_highlights": [],
            "domain_hints": [],
        }
        ws = project_id or "default"
        try:
            recent = await self._memory.get_recent(ws, limit=5)
            if recent:
                summaries = [r.get("summary", "")[:100] for r in recent if r.get("summary")]
                ctx["recent_activity_summary"] = "; ".join(summaries[:3])
                for r in recent:
                    cat = r.get("category", "")
                    if cat and cat not in ctx["domain_hints"]:
                        ctx["domain_hints"].append(cat)
        except Exception as e:
            logger.debug("Router context: memory failed: %s", e)
        try:
            goals = await self._goals.get_active(ws, limit=3)
            ctx["active_goals"] = [
                {"name": g["name"], "progress": g.get("progress", 0), "priority": g.get("priority", "medium")}
                for g in goals
            ]
        except Exception as e:
            logger.debug("Router context: goals failed: %s", e)
        try:
            knowledge = await self._knowledge.search(ws, "", min_confidence=0.7, limit=3)
            ctx["knowledge_highlights"] = [k.get("summary", "")[:120] for k in knowledge if k.get("summary")]
        except Exception as e:
            logger.debug("Router context: knowledge failed: %s", e)
        try:
            sources = self._registry.enabled_source_names(project_id=project_id)
            ctx["available_sources"] = sources
        except Exception as e:
            logger.debug("Router context: sources failed: %s", e)
        return ctx

_routing_context: RoutingContextGatherer | None = None
def get_routing_context() -> RoutingContextGatherer:
    global _routing_context
    if _routing_context is None:
        _routing_context = RoutingContextGatherer()
    return _routing_context
