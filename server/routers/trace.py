"""Trace API router."""

from __future__ import annotations

import time

from fastapi import APIRouter

from core.graph.client import Neo4jClient
from core.graph.queries.trace import trace_symbol
from server.config import get_settings
from server.schemas.responses import ApiEnvelope

router = APIRouter(tags=["trace"])


@router.get("/trace/{symbol}", response_model=ApiEnvelope)
async def trace_symbol_endpoint(symbol: str, explain: bool = False) -> ApiEnvelope:
    start = time.perf_counter()
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        result = await trace_symbol(client, symbol, explain=explain)
    finally:
        await client.close()
    return ApiEnvelope(
        success=True,
        data=result.model_dump(),
        error=None,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )
