"""FastAPI app factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from server.config import get_settings
from server.middleware.errors import envelope_errors
from server.middleware.logging import log_requests
from server.routers import (
    analysis,
    architecture,
    explain,
    impact,
    index,
    onboard,
    runtime,
    search,
    trace,
)
from server.runtime import ServerRuntime


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    runtime = ServerRuntime(get_settings())
    app.state.runtime = runtime
    await runtime.startup()
    try:
        yield
    finally:
        await runtime.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Repository Intelligence Platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.middleware("http")(envelope_errors)
    app.middleware("http")(log_requests)
    app.include_router(index.router)
    app.include_router(trace.router)
    app.include_router(impact.router)
    app.include_router(search.router)
    app.include_router(analysis.router)
    app.include_router(architecture.router)
    app.include_router(onboard.router)
    app.include_router(explain.router)
    app.include_router(runtime.router)
    return app



app = create_app()
