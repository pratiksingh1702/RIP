"""FastAPI app factory."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI

GATEWAY_ROOT = Path(__file__).resolve().parents[1] / "gateway"
if str(GATEWAY_ROOT) not in sys.path:
    sys.path.insert(0, str(GATEWAY_ROOT))

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

from gateway.server.routers import (
    agent as gateway_agent,
    active_project as gateway_active_project,
    audit as gateway_audit,
    context as gateway_context,
    feedback as gateway_feedback,
    health as gateway_health,
    metrics as gateway_metrics,
    oauth as gateway_oauth,
    settings as gateway_settings,
    sessions as gateway_sessions,
    sources as gateway_sources,
    validate as gateway_validate,
    workflows as gateway_workflows,
)
from gateway.core.blocks import register_all_blocks
from gateway.core.llm_pool import seed_llm_configs
from gateway.core.prompts import seed_prompt_templates
from gateway.core.sources.registry import get_source_registry as get_gateway_source_registry
from gateway.core.workflow import seed_workflows
from gateway.storage.database import ensure_storage_schema as ensure_gateway_storage_schema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    runtime = ServerRuntime(get_settings())
    app.state.runtime = runtime
    await runtime.startup()
    await seed_llm_configs()
    await ensure_gateway_storage_schema()
    await seed_prompt_templates()
    await seed_workflows()
    await get_gateway_source_registry().refresh()
    register_all_blocks()
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
    app.include_router(health_router)
    app.include_router(runtime.router, dependencies=[Depends(verify_api_key)])
    app.include_router(git_router, dependencies=[Depends(verify_api_key)])
    app.include_router(projects_router, dependencies=[Depends(verify_api_key)])
    app.include_router(api_keys_router, dependencies=[Depends(verify_api_key)])
    app.include_router(gateway_health.router, prefix="/gateway/health", tags=["gateway-health"])
    app.include_router(
        gateway_context.router,
        prefix="/gateway/api/context",
        tags=["gateway-context"],
        dependencies=[Depends(verify_api_key)],
    )
    app.include_router(
        gateway_validate.router,
        prefix="/gateway/api/validate",
        tags=["gateway-validate"],
        dependencies=[Depends(verify_api_key)],
    )
    app.include_router(
        gateway_sessions.router,
        prefix="/gateway/api/sessions",
        tags=["gateway-sessions"],
        dependencies=[Depends(verify_api_key)],
    )
    app.include_router(
        gateway_sources.router,
        prefix="/gateway/api/sources",
        tags=["gateway-sources"],
        dependencies=[Depends(verify_api_key)],
    )
    app.include_router(
        gateway_sources.router,
        prefix="/gateway/sources",
        tags=["gateway-sources"],
        dependencies=[Depends(verify_api_key)],
    )
    app.include_router(
        gateway_oauth.router,
        prefix="/gateway/api/oauth",
        tags=["gateway-oauth"],
        dependencies=[Depends(verify_api_key)],
    )
    app.include_router(
        gateway_settings.router,
        prefix="/gateway/settings",
        tags=["gateway-settings"],
        dependencies=[Depends(verify_api_key)],
    )
    app.include_router(
        gateway_metrics.router,
        prefix="/gateway/api/metrics",
        tags=["gateway-metrics"],
        dependencies=[Depends(verify_api_key)],
    )
    app.include_router(
        gateway_audit.router,
        prefix="/gateway/api/audit",
        tags=["gateway-audit"],
        dependencies=[Depends(verify_api_key)],
    )
    app.include_router(
        gateway_feedback.router,
        prefix="/gateway/api/feedback",
        tags=["gateway-feedback"],
        dependencies=[Depends(verify_api_key)],
    )
    app.include_router(
        gateway_workflows.router,
        prefix="/gateway/api/workflows",
        tags=["gateway-workflows"],
        dependencies=[Depends(verify_api_key)],
    )
    app.include_router(
        gateway_active_project.router,
        prefix="/gateway/api/projects",
        tags=["gateway-projects"],
        dependencies=[Depends(verify_api_key)],
    )
    app.include_router(
        gateway_agent.router,
        prefix="/gateway/api/agent",
        tags=["gateway-agent"],
        dependencies=[Depends(verify_api_key)],
    )
    app.include_router(ws_router)
    return app


app = create_app()
