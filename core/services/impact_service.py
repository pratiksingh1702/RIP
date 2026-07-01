"""Impact domain service."""

from __future__ import annotations


class ImpactService:
    def __init__(self, graph_store) -> None:
        self.graph_store = graph_store

    async def analyze(self, symbol: str, project_id: str):
        return await self.graph_store.impact(symbol, project_id)
