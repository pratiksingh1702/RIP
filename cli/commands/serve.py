"""Serve the RIP FastAPI application."""

from __future__ import annotations

import uvicorn

from server.config import get_settings


def serve(host: str | None = None, port: int | None = None, reload: bool = False) -> None:
    settings = get_settings()
    uvicorn.run(
        "server.app:app",
        host=host or settings.rip_server_host,
        port=port or settings.rip_server_port,
        reload=reload,
        factory=False,
    )
