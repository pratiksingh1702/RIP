"""Runtime status API router."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

from server.schemas.responses import ApiEnvelope

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
