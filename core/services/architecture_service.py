"""Architecture domain service."""

from __future__ import annotations


class ArchitectureService:
    def __init__(self, graph_store) -> None:
        self.graph_store = graph_store

    async def architecture(self, project_id: str):
        return await self.graph_store.architecture(project_id)
