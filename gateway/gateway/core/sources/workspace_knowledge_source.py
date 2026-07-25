"""Workspace Knowledge as a context source for the planner."""
from gateway.core.sources.base import BaseSource
from gateway.core.sources.models import SourceResponse
from gateway.core.workspace.knowledge import get_workspace_knowledge

class WorkspaceKnowledgeSource(BaseSource):
    name = "workspace_knowledge"
    display_name = "Workspace Knowledge"

    async def health_check(self) -> bool:
        return True

    async def query(self, query_type: str, query_params: dict) -> SourceResponse:
        knowledge = get_workspace_knowledge()
        workspace_id = query_params.get("workspace_id") or query_params.get("project_id", "default")
        query = query_params.get("query", "")
        limit = query_params.get("limit", 5)
        results = await knowledge.search(workspace_id=workspace_id, query=query, min_confidence=0.5, limit=limit)
        content_parts = []
        for r in results:
            content_parts.append(f"[{r['knowledge_type']}] {r['summary']} (confidence: {r['confidence']:.0%})")
        content = "\n".join(content_parts) if content_parts else "No relevant knowledge found"
        return SourceResponse(success=True, content=content, metadata={"source": "workspace_knowledge", "count": len(results), "types": list(set(r["knowledge_type"] for r in results)) if results else []}, token_count=len(content.split()) // 3 if content else 0, latency_ms=0)
