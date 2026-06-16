"""Search API router."""

from __future__ import annotations

import time

from fastapi import APIRouter, Query, Request

from core.search.searcher import Searcher
from server.schemas.responses import ApiEnvelope, SearchResultResponse

router = APIRouter(tags=["search"])


@router.get("/search", response_model=ApiEnvelope)
async def search(
    request: Request,
    q: str = Query(..., description="Query string"),
    top: int = Query(20, description="Top K results"),
    language: str | None = Query(None, description="Filter by language"),
    service: str | None = Query(None, description="Filter by service"),
    entity_type: str | None = Query(None, description="Filter by entity type"),
) -> ApiEnvelope:
    start = time.perf_counter()
    runtime = request.app.state.runtime
    searcher = Searcher(
        qdrant_client=runtime.qdrant,
        embedder=runtime.embedder,
        reranker=runtime.reranker,
        graph_client=runtime.neo4j,
    )
    filters = {
        "language": language,
        "service": service,
        "entity_type": entity_type,
    }
    results = await searcher.hybrid_search(query=q, filters=filters, top_k=top)
    response_data = [SearchResultResponse(**r.model_dump()) for r in results]

    duration_ms = int((time.perf_counter() - start) * 1000)
    return ApiEnvelope(
        success=True,
        data=response_data,
        error=None,
        duration_ms=duration_ms,
    )
