"""Architecture API router."""

from __future__ import annotations

import time

from fastapi import APIRouter, Query

from core.analysis.architecture_generator import ArchitectureGenerator
from core.graph.client import Neo4jClient
from server.config import get_settings
from server.schemas.responses import ApiEnvelope

router = APIRouter(tags=["architecture"])


@router.get("/architecture", response_model=ApiEnvelope)
async def architecture_endpoint(
    format: str = Query("json", description="json|mermaid")
) -> ApiEnvelope:
    start = time.perf_counter()
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        generator = ArchitectureGenerator(client)
        arch_data = await generator.generate()
    finally:
        await client.close()

    # If they want format='mermaid', we can return just the mermaid string or the whole payload.
    # The API spec returns services, dependencies, and mermaid.
    return ApiEnvelope(
        success=True,
        data=arch_data,
        error=None,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )
