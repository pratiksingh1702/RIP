"""Sources API router."""

from fastapi import APIRouter, HTTPException

from gateway.core.sources.registry import get_source_registry
from gateway.server.schemas.responses import SourceListResponse

router = APIRouter()
registry = get_source_registry()


@router.get("", response_model=SourceListResponse)
@router.get("/", response_model=SourceListResponse)
async def list_sources():
    """List all available sources."""
    try:
        sources_list = []
        for name, source in registry.sources.items():
            sources_list.append({
                "name": name,
                "available": source.is_available(),
                "healthy": registry.is_healthy(name),
            })
        return SourceListResponse(sources=sources_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{source_name}/enable")
async def enable_source(source_name: str):
    """Enable a source."""
    try:
        if not registry.set_enabled(source_name, True):
            raise HTTPException(status_code=404, detail=f"Unknown or fixed source: {source_name}")
        return {"status": "ok", "source": source_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{source_name}/disable")
async def disable_source(source_name: str):
    """Disable a source."""
    try:
        if not registry.set_enabled(source_name, False):
            raise HTTPException(status_code=404, detail=f"Unknown or fixed source: {source_name}")
        return {"status": "ok", "source": source_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
