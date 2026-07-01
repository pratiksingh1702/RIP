"""Runtime storage resolver."""

from __future__ import annotations

from pathlib import Path

from core.runtime.environment import RuntimeEnvironment, RuntimeMode


class StorageResolver:
    def __init__(
        self,
        repo_root: Path | None = None,
        mode: str | RuntimeMode = RuntimeMode.AUTO,
    ) -> None:
        self.repo_root = (repo_root or Path.cwd()).resolve()
        self.mode = RuntimeMode(mode)

    async def resolve(self) -> RuntimeEnvironment:
        if self.mode == RuntimeMode.LOCAL:
            return await self._resolve_local(["Explicit local mode selected."])
        if self.mode == RuntimeMode.SERVER:
            return await self._resolve_server(required=True)

        diagnostics = []
        from core.storage.providers.neo4j_provider import can_connect_neo4j
        from core.storage.providers.postgres_provider import can_connect_postgres
        from core.storage.providers.qdrant_provider import can_connect_qdrant

        server_ready = (
            await can_connect_neo4j()
            and await can_connect_qdrant()
            and await can_connect_postgres()
        )
        if server_ready:
            diagnostics.append("Auto mode selected server providers.")
            return await self._resolve_server(required=False, diagnostics=diagnostics)
        diagnostics.append(
            "Auto mode fell back to local providers because server services are unavailable."
        )
        return await self._resolve_local(diagnostics)

    async def _resolve_server(
        self, *, required: bool, diagnostics: list[str] | None = None
    ) -> RuntimeEnvironment:
        from core.storage.providers.neo4j_provider import Neo4jProvider
        from core.storage.providers.postgres_provider import PostgresProvider
        from core.storage.providers.qdrant_provider import QdrantProvider

        diagnostics = diagnostics or ["Explicit server mode selected."]
        graph = Neo4jProvider()
        vector = QdrantProvider()
        metadata = PostgresProvider()
        try:
            await graph.setup()
            await vector.setup()
            await metadata.setup()
        except Exception as exc:
            await graph.close()
            await vector.close()
            if required:
                raise RuntimeError(
                    "Server mode requires Neo4j, Qdrant, and PostgreSQL. "
                    "Start the root stack with: docker compose up -d"
                ) from exc
            return await self._resolve_local(
                diagnostics + [f"Server provider setup failed: {exc!s}"]
            )
        return RuntimeEnvironment(
            mode=RuntimeMode.SERVER,
            graph=graph,
            vector=vector,
            metadata=metadata,
            root=self.repo_root,
            diagnostics=diagnostics,
        )

    async def _resolve_local(self, diagnostics: list[str]) -> RuntimeEnvironment:
        from core.storage.providers.local_vector_provider import LocalVectorProvider
        from core.storage.providers.networkx_provider import NetworkXProvider
        from core.storage.providers.sqlite_provider import SQLiteProvider

        graph = NetworkXProvider(self.repo_root)
        vector = LocalVectorProvider(self.repo_root)
        metadata = SQLiteProvider(self.repo_root)
        await graph.setup()
        await vector.setup()
        await metadata.setup()
        return RuntimeEnvironment(
            mode=RuntimeMode.LOCAL,
            graph=graph,
            vector=vector,
            metadata=metadata,
            root=self.repo_root,
            diagnostics=diagnostics,
        )
