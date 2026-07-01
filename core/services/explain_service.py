"""Explain domain service."""

from __future__ import annotations

from core.llm.models import ExplainContext


class ExplainService:
    def __init__(self, graph_store, vector_store) -> None:
        self.graph_store = graph_store
        self.vector_store = vector_store

    async def graph_context(self, query: str, project_id: str, max_hops: int = 8) -> ExplainContext:
        results = await self.vector_store.search_similar(query, project_id, 10, None)
        trace = await self.graph_store.trace(query, project_id, max_hops)
        dep_rows = await self.graph_store.dependencies(query, project_id)
        return ExplainContext(
            query=query,
            found=bool(results or trace.hops or dep_rows),
            context_str="Runtime graph/search analysis.",
            overview="Runtime graph/search analysis.",
            important_files=sorted({item.file_path for item in results if item.file_path}),
            important_entities=[
                {
                    "name": item.name,
                    "type": item.entity_type,
                    "file_path": item.file_path,
                    "raw_code": item.raw_code,
                }
                for item in results
            ],
            workflow_chain=[
                {
                    "from": hop.from_symbol,
                    "to": hop.to_symbol,
                    "relationship": hop.relationship_type,
                }
                for hop in trace.hops
            ],
            dependency_graph={
                query: [(edge.target, edge.relationship_type) for edge in dep_rows[:20]]
            },
        )
