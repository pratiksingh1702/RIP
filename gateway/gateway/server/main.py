"""FastAPI server for Context Gateway."""

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway.config import settings
from gateway.core.blocks import register_all_blocks
from gateway.core.llm_pool import seed_llm_configs
from gateway.core.prompts import seed_prompt_templates
from gateway.core.sources.registry import get_source_registry
from gateway.core.workflow import seed_workflows
from gateway.server.middleware.rate_limit import RateLimitMiddleware
from gateway.server.routers import (
    audit,
    context,
    feedback,
    health,
    metrics,
    oauth,
    sessions,
    sources,
    validate,
    workflows,
)
from gateway.server.routers import (
    settings as gateway_settings,
)
from gateway.storage.database import ensure_storage_schema

logger = structlog.get_logger(__name__)


async def _background_health_check():
    """Periodically check source health in the background."""
    registry = get_source_registry()
    while True:
        try:
            logger.debug("Running background health checks")
            await registry.check_all_health()
        except Exception as e:
            logger.error("Background health check failed", error=str(e))
        await asyncio.sleep(settings.cache_ttl_seconds)


async def _background_oauth_refresh():
    """Refresh expiring OAuth tokens in the background."""
    while True:
        try:
            await oauth.oauth_manager.refresh_due_tokens()
            await get_source_registry().refresh()
        except Exception as e:
            logger.error("Background OAuth refresh failed", error=str(e))
        await asyncio.sleep(300)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan for setup/teardown."""
    logger.info("Starting Context Gateway server", version=settings.version)
    seed_llm_configs()
    await ensure_storage_schema()
    await seed_prompt_templates()
    await seed_workflows()
    await oauth.oauth_manager.ensure_oauth_providers()
    await get_source_registry().refresh()
    register_all_blocks()
    
    # Start background health checks
    health_task = asyncio.create_task(_background_health_check())
    oauth_task = asyncio.create_task(_background_oauth_refresh())
    
    yield
    
    # Cancel background health checks
    health_task.cancel()
    oauth_task.cancel()
    try:
        await health_task
    except asyncio.CancelledError:
        pass
    try:
        await oauth_task
    except asyncio.CancelledError:
        pass
    
    logger.info("Shutting down Context Gateway server")


def create_app() -> FastAPI:
    """Create and configure FastAPI app."""
    app = FastAPI(
        title="Context Gateway",
        description="Intelligent context orchestration for coding agents",
        version=settings.version,
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add Rate Limit middleware
    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

    # Include routers
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(context.router, prefix="/api/context", tags=["context"])
    app.include_router(validate.router, prefix="/api/validate", tags=["validate"])
    app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
    app.include_router(sources.router, prefix="/api/sources", tags=["sources"])
    app.include_router(sources.router, prefix="/api/integrations", tags=["integrations"])
    app.include_router(oauth.router, prefix="/api/oauth", tags=["oauth"])
    app.include_router(gateway_settings.router, prefix="/api/settings", tags=["settings"])
    app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
    app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
    app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])
    app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "gateway.server.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
