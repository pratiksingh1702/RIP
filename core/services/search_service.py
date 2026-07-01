"""Search domain service."""

from __future__ import annotations


class SearchService:
    def __init__(self, vector_store) -> None:
        self.vector_store = vector_store

    async def search(self, query: str, project_id: str, limit: int = 20, filters=None):
        return await self.vector_store.search_similar(query, project_id, limit, filters)
