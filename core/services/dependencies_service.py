"""Dependencies domain service."""

from __future__ import annotations


class DependenciesService:
    def __init__(self, graph_store) -> None:
        self.graph_store = graph_store

    async def dependencies(self, target: str, project_id: str):
        return await self.graph_store.dependencies(target, project_id)
