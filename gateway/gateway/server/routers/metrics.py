"""Metrics API router."""

from fastapi import APIRouter, HTTPException

from gateway.server.schemas.responses import MetricsResponse

router = APIRouter()


@router.get("", response_model=MetricsResponse)
@router.get("/", response_model=MetricsResponse)
async def get_metrics():
    """Get gateway metrics."""
    try:
        # Placeholder metrics
        return MetricsResponse(
            sessions=0,
            active_sessions=0,
            tokens_retrieved=0,
            tokens_delivered=0,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
