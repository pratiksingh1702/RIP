"""Vector store interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.graph.models import SearchResult
from core.parser.base import ParsedEntity
from core.runtime.capabilities import Capability


class VectorStore(ABC):
    name: str
    capabilities: set[Capability]

    @abstractmethod
    async def setup(self) -> None: ...

    @abstractmethod
    async def upsert_entities(
        self, entities: list[ParsedEntity], project_id: str, project_name: str | None = None
    ) -> int: ...

    @abstractmethod
    async def search_similar(
        self,
        query: str,
        project_id: str,
        limit: int = 20,
        filters: dict[str, object] | None = None,
    ) -> list[SearchResult]: ...

    @abstractmethod
    async def delete_project(self, project_id: str) -> int: ...

    @abstractmethod
    async def close(self) -> None: ...
