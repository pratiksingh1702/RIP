"""Health check router."""

from fastapi import APIRouter

from gateway.config import settings
from gateway.core.sources.registry import get_source_registry
from gateway.server.schemas.responses import HealthCheckResponse

router = APIRouter()


@router.get("", response_model=HealthCheckResponse)
@router.get("/", response_model=HealthCheckResponse)
async def get_health():
    """Get gateway health status."""
    registry = get_source_registry()
    sources_status = {}
    for source_name, source in registry.sources.items():
        sources_status[source_name] = {
            "available": source.is_available(),
            "healthy": registry.is_healthy(source_name),
        }
    return HealthCheckResponse(
        status="healthy",
        version=settings.version,
        sources=sources_status,
    )
