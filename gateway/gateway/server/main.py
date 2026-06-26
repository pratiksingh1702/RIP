"""FastAPI server for Context Gateway."""

import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway.config import settings
from gateway.core.sources.registry import get_source_registry
from gateway.server.middleware.rate_limit import RateLimitMiddleware
from gateway.server.routers import health, context, validate, sessions, sources, metrics

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan for setup/teardown."""
    logger.info("Starting Context Gateway server", version=settings.version)
    
    # Start background health checks
    health_task = asyncio.create_task(_background_health_check())
    
    yield
    
    # Cancel background health checks
    health_task.cancel()
    try:
        await health_task
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
    app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])

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
