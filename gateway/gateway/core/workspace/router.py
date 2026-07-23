"""Workspace Router — classifies intent and routes to the cheapest, fastest handler."""

from __future__ import annotations
import asyncio
import logging
from typing import Any

from gateway.core.classifier.engine import ClassifierEngine
from gateway.core.classifier.models import IntentType
from gateway.core.workspace.memory import get_workspace_memory
from gateway.core.workspace.capabilities import get_capability_registry

logger = logging.getLogger(__name__)


class WorkspaceRouter:
    """Routes every user query to the optimal handler based on classified intent."""

    def __init__(self):
        self.classifier = ClassifierEngine()
        self.memory = get_workspace_memory()
        self.registry = get_capability_registry()

    async def route(self, query: str, workspace_id: str, user_id: str,
                    project_id: str | None = None) -> dict[str, Any]:
        try:
            intent = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.classifier.classify(query))
        except Exception:
            intent = None
        intent_type = intent.type if intent else IntentType.INVESTIGATION
        handler_info = self.registry.get(intent_type.value)
        if handler_info is None:
            handler_info = self.registry.get("INVESTIGATION")
        handler = handler_info["handler"] if handler_info else self._handle_fallback
        cost = handler_info["cost"] if handler_info else "full"
        logger.info("ROUTER: %s → %s (cost: %s)", query[:80], intent_type.value, cost)
        result = await handler(query, workspace_id, user_id, project_id)
        await self.memory.record(
            workspace_id=workspace_id, project_id=project_id,
            category="conversation", intent=intent_type.value if intent else None,
            query=query, summary=result.get("summary", ""), result_data=result,
            tokens_used=result.get("tokens_used", 0),
            duration_seconds=result.get("duration_seconds", 0),
            status=result.get("status", "completed"), created_by=user_id,
        )
        return result

    async def _handle_fallback(self, query, workspace_id, user_id, project_id):
        return {"type": "fallback", "summary": "No handler found", "tokens_used": 0, "status": "failed"}


_router = WorkspaceRouter()

def get_workspace_router() -> WorkspaceRouter:
    return _router
