"""Metadata store interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from core.projects import ProjectRef
from core.runtime.capabilities import Capability


class MetadataStore(ABC):
    name: str
    capabilities: set[Capability]

    @abstractmethod
    async def setup(self) -> None: ...

    @abstractmethod
    async def save_project(
        self,
        root: Path,
        project_id: str | None = None,
        project_name: str | None = None,
        files_count: int = 0,
        entities_count: int = 0,
        languages: list[str] | None = None,
    ) -> ProjectRef: ...

    @abstractmethod
    async def get_project(self, project_id: str) -> ProjectRef | None: ...

    @abstractmethod
    async def list_projects(self) -> list[ProjectRef]: ...

    @abstractmethod
    async def save_file_hash(self, project_id: str, file_path: str, sha256_hash: str) -> None: ...

    @abstractmethod
    async def get_file_hash(self, project_id: str, file_path: str) -> str | None: ...

    @abstractmethod
    async def delete_project(self, project_id: str) -> bool: ...

    @abstractmethod
    async def close(self) -> None: ...
