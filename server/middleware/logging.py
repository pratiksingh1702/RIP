"""Request logging middleware."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from fastapi import Request

logger = logging.getLogger(__name__)


async def log_requests(request: Request, call_next: Callable):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - start) * 1000)
    logger.info("%s %s %sms", request.method, request.url.path, duration_ms)
    return response
