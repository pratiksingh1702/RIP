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
    await registry.refresh()
    sources_status = {}
    for source_name, source in registry.sources.items():
        record = registry.get_record(source_name)
        sources_status[source_name] = {
            "available": source.is_available(),
            "healthy": registry.is_healthy(source_name),
            "always_on": bool(record.protected) if record else source_name == "rip",
            "toggleable": not record.protected if record else source_name != "rip",
            "kind": record.kind if record else "builtin",
        }
    return HealthCheckResponse(
        status="healthy",
        version=settings.version,
        sources={
            **sources_status,
            "_capabilities": {
                "single_connection": True,
                "sessions": True,
                "sources": True,
                "metrics": True,
                "audit": True,
                "feedback": True,
                "pipeline_stream": True,
            },
        },
    )
