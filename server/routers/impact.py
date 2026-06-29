"""Impact API router."""

from __future__ import annotations

import time

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.graph.client import Neo4jClient
from core.graph.queries.impact import impact_symbol
from core.projects import verify_project_access
from core.storage.database import get_db_session
from server.config import get_settings
from server.middleware.auth import verify_api_key
from server.schemas.responses import ApiEnvelope

router = APIRouter(tags=["impact"])


@router.get("/impact/{symbol}", response_model=ApiEnvelope)
async def impact_symbol_endpoint(
    symbol: str,
    request: Request,
    project_id: str = Query(None, description="Project id to check impact within"),
    auth: Annotated[None, Depends(verify_api_key)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> ApiEnvelope:
    start = time.perf_counter()
    
    # Isolation check
    if project_id:
        api_key = getattr(request.state, "api_key", None)
        if not await verify_project_access(db, api_key, project_id):
            raise HTTPException(status_code=403, detail=f"Access to project {project_id} denied")

    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        result = await impact_symbol(client, symbol, project_id=project_id)
    finally:
        await client.close()
    return ApiEnvelope(
        success=True,
        data=result.model_dump(),
        error=None,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )
