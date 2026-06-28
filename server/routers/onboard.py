"""Onboard API router."""

from __future__ import annotations

import time

from fastapi import APIRouter, Query

from core.analysis.onboard_engine import OnboardEngine
from core.graph.client import Neo4jClient
from server.config import get_settings
from server.schemas.responses import ApiEnvelope

router = APIRouter(tags=["onboard"])


@router.get("/onboard", response_model=ApiEnvelope)
async def onboard_endpoint(
    project_id: str = Query(None, description="Project id to get onboarding for"),
) -> ApiEnvelope:
    start = time.perf_counter()
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        engine = OnboardEngine(client)
        data = await engine.generate_onboarding_data(project_id=project_id)
    finally:
        await client.close()

    return ApiEnvelope(
        success=True,
        data=data,
        error=None,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )
