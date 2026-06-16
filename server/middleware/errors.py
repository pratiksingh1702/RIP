"""Error handling middleware."""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request
from fastapi.responses import JSONResponse


async def envelope_errors(request: Request, call_next: Callable):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001 - API must return envelope errors
        duration_ms = int((time.perf_counter() - start) * 1000)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "data": None,
                "error": str(exc),
                "duration_ms": duration_ms,
            },
        )
    return response
