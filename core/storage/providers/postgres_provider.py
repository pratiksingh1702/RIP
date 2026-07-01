"""PostgreSQL metadata provider wrapper."""

from __future__ import annotations

from pathlib import Path

from core.projects import (
    ProjectRef,
    ensure_project,
    get_project,
    list_projects,
)
from core.runtime.capabilities import Capability
from core.storage.database import async_session_factory, ensure_storage_schema
from core.storage.interfaces.metadata_store import MetadataStore


class PostgresProvider(MetadataStore):
    name = "PostgresProvider"
    capabilities = {
        Capability.METADATA_STORAGE,
        Capability.PERSISTENT_STORAGE,
        Capability.MULTI_PROJECT,
        Capability.INCREMENTAL_INDEX,
        Capability.CONCURRENT_USERS,
    }

    async def setup(self) -> None:
        await ensure_storage_schema()

    async def save_project(
        self,
        root: Path,
        project_id: str | None = None,
        project_name: str | None = None,
        files_count: int = 0,
        entities_count: int = 0,
        languages: list[str] | None = None,
    ) -> ProjectRef:
        _ = (project_id, project_name, files_count, entities_count, languages)
        async with async_session_factory() as session:
            return await ensure_project(session, root)

    async def get_project(self, project_id: str) -> ProjectRef | None:
        async with async_session_factory() as session:
            return await get_project(session, project_id)

    async def list_projects(self) -> list[ProjectRef]:
        async with async_session_factory() as session:
            return await list_projects(session)

    async def save_file_hash(self, project_id: str, file_path: str, sha256_hash: str) -> None:
        _ = (project_id, file_path, sha256_hash)

    async def get_file_hash(self, project_id: str, file_path: str) -> str | None:
        _ = (project_id, file_path)
        return None

    async def delete_project(self, project_id: str) -> bool:
        from core.projects import delete_project

        async with async_session_factory() as session:
            return await delete_project(session, project_id)

    async def close(self) -> None:
        return None


async def can_connect_postgres() -> bool:
    provider = PostgresProvider()
    try:
        await provider.setup()
        return True
    except Exception:
        return False
