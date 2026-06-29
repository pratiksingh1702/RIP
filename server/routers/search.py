"""Search API router."""

from __future__ import annotations

import time

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.projects import verify_project_access
from core.search.searcher import Searcher
from core.storage.database import get_db_session
from server.middleware.auth import verify_api_key
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
    project_id: str = Query(..., description="Project id to search within"),
    auth: Annotated[None, Depends(verify_api_key)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> ApiEnvelope:
    start = time.perf_counter()
    
    # Isolation check
    api_key = getattr(request.state, "api_key", None)
    if not await verify_project_access(db, api_key, project_id):
        raise HTTPException(status_code=403, detail=f"Access to project {project_id} denied")

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
        "project_id": project_id,
    }
    results = await searcher.hybrid_search(
        query=q,
        filters=filters,
        top_k=top,
        project_id=project_id,
    )
    response_data = [SearchResultResponse(**r.model_dump()) for r in results]

    duration_ms = int((time.perf_counter() - start) * 1000)
    return ApiEnvelope(
        success=True,
        data=response_data,
        error=None,
        duration_ms=duration_ms,
    )
