"""Workspace Memory as a context source for the planner."""

from gateway.core.sources.base import BaseSource
from gateway.core.sources.models import SourceResponse
from gateway.core.workspace.memory import get_workspace_memory


class WorkspaceMemorySource(BaseSource):
    name = "workspace_memory"
    display_name = "Workspace Memory"

    async def health_check(self) -> bool:
        return True

    async def query(self, query_type: str, query_params: dict) -> SourceResponse:
        memory = get_workspace_memory()
        workspace_id = query_params.get("workspace_id") or query_params.get("project_id", "default")
        query = query_params.get("query", "")
        limit = query_params.get("limit", 5)
        
        results = await memory.search(
            workspace_id=workspace_id,
            query=query,
            categories=["execution", "decision", "pattern"],
            limit=limit,
        )
        
        content_parts = []
        for r in results:
            content_parts.append(f"[{r['category']}] {r['query']}: {r['summary']}")
        
        content = "\n".join(content_parts) if content_parts else "No past knowledge found"
        
        return SourceResponse(
            success=True,
            content=content,
            metadata={
                "source": "workspace_memory",
                "count": len(results),
                "categories": list(set(r["category"] for r in results)) if results else [],
            },
            tokens_used=len(content.split()) // 3 if content else 0,
            duration_ms=0,
        )