"""Graph store interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.graph.models import FlowTrace, GraphEdge, GraphNode, ImpactResult
from core.parser.base import ParsedFile
from core.runtime.capabilities import Capability


class GraphStore(ABC):
    name: str
    capabilities: set[Capability]

    @abstractmethod
    async def setup(self) -> None: ...

    @abstractmethod
    async def batch_upsert_files(
        self, files: list[ParsedFile], project_id: str
    ) -> dict[str, int]: ...

    @abstractmethod
    async def trace(self, symbol: str, project_id: str, depth: int = 8) -> FlowTrace: ...

    @abstractmethod
    async def dependencies(self, target: str, project_id: str) -> list[GraphEdge]: ...

    @abstractmethod
    async def architecture(self, project_id: str) -> dict[str, object]: ...

    @abstractmethod
    async def impact(self, symbol: str, project_id: str) -> ImpactResult: ...

    @abstractmethod
    async def find_unused(self, project_id: str, entity_type: str = "all") -> list[GraphNode]: ...

    @abstractmethod
    async def delete_project(self, project_id: str) -> int: ...

    @abstractmethod
    async def close(self) -> None: ...
