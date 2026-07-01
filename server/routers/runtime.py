"""Runtime status API router."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

from server.schemas.responses import ApiEnvelope

# Health router (public)
health_router = APIRouter(tags=["health"])

# Runtime router (protected)
router = APIRouter(tags=["runtime"])


@router.get("/runtime/status", response_model=ApiEnvelope)
async def runtime_status(request: Request) -> ApiEnvelope:
    start = time.perf_counter()
    runtime = request.app.state.runtime
    return ApiEnvelope(
        success=True,
        data=runtime.status(),
        error=None,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )


@health_router.get("/health")
async def health(request: Request) -> dict[str, object]:
    runtime = request.app.state.runtime
    status = runtime.status()
    return {
        "status": "ready",
        "neo4j": status["neo4j_available"],
        "qdrant": status["qdrant_available"],
        "mode": status.get("mode", "server"),
        "capabilities": status.get("capabilities", []),
    }
