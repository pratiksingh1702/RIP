"""Trace domain service."""

from __future__ import annotations


class TraceService:
    def __init__(self, graph_store) -> None:
        self.graph_store = graph_store

    async def trace(self, symbol: str, project_id: str, depth: int = 8):
        return await self.graph_store.trace(symbol, project_id, depth)
