"""Serve the RIP FastAPI application."""

from __future__ import annotations

from pathlib import Path

import uvicorn
from rich.console import Console

from core.runtime.capabilities import Capability
from core.runtime.resolver import StorageResolver
from server.config import get_settings

console = Console()


RELOAD_DIRS = ("server", "core", "cli", "mcp")


def serve(
    host: str | None = None,
    port: int | None = None,
    reload: bool = False,
    mode: str = "server",
) -> None:
    settings = get_settings()
    if mode != "server":
        import asyncio

        env = asyncio.run(StorageResolver(Path.cwd(), mode=mode).resolve())
        try:
            if not env.has(Capability.REST_API):
                console.print(
                    "[yellow]REST API requires server mode with Neo4j, "
                    "Qdrant, and PostgreSQL.[/yellow]"
                )
                console.print("[yellow]Start server storage with: docker compose up -d[/yellow]")
                return
        finally:
            asyncio.run(env.graph.close())
            asyncio.run(env.vector.close())
            asyncio.run(env.metadata.close())

    reload_dirs = [str(Path.cwd() / path) for path in RELOAD_DIRS if (Path.cwd() / path).exists()]

    uvicorn.run(
        "server.app:app",
        host=host or settings.rip_server_host,
        port=port or settings.rip_server_port,
        reload=reload,
        reload_dirs=reload_dirs if reload else None,
        factory=False,
        log_level="debug",  # Enable verbose logging
        access_log=True,
    )
