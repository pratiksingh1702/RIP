"""Dead-code domain service."""

from __future__ import annotations


class DeadCodeService:
    def __init__(self, graph_store) -> None:
        self.graph_store = graph_store

    async def find_unused(self, project_id: str, entity_type: str = "all"):
        return await self.graph_store.find_unused(project_id, entity_type)
