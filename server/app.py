"""FastAPI app factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from server.config import get_settings
from server.middleware.auth import verify_api_key
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
from server.routers.api_keys import router as api_keys_router
from server.routers.git import router as git_router
from server.routers.projects import router as projects_router
from server.routers.runtime import health_router
from server.routers.ws import router as ws_router
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
    app.include_router(index.router, dependencies=[Depends(verify_api_key)])
    app.include_router(trace.router, dependencies=[Depends(verify_api_key)])
    app.include_router(impact.router, dependencies=[Depends(verify_api_key)])
    app.include_router(search.router, dependencies=[Depends(verify_api_key)])
    app.include_router(analysis.router, dependencies=[Depends(verify_api_key)])
    app.include_router(architecture.router, dependencies=[Depends(verify_api_key)])
    app.include_router(onboard.router, dependencies=[Depends(verify_api_key)])
    app.include_router(explain.router, dependencies=[Depends(verify_api_key)])
    app.include_router(health_router)  # No auth for health
    app.include_router(runtime.router, dependencies=[Depends(verify_api_key)])
    app.include_router(git_router, dependencies=[Depends(verify_api_key)])
    app.include_router(projects_router, dependencies=[Depends(verify_api_key)])
    app.include_router(api_keys_router, dependencies=[Depends(verify_api_key)])
    app.include_router(ws_router)
    return app



app = create_app()
