"""Index API router."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Request

from core.indexer.pipeline import index_repository_with_resources
from server.schemas.requests import IndexRequest
from server.schemas.responses import ApiEnvelope, IndexStartedResponse, IndexStatusResponse

router = APIRouter(tags=["index"])
LAST_STATUS = IndexStatusResponse(status="not_started", progress=0.0, entity_count=0)


@router.post("/index", response_model=ApiEnvelope)
async def index_repo(request: Request, index_request: IndexRequest) -> ApiEnvelope:
    start = time.perf_counter()
    runtime = request.app.state.runtime
    repo_path = Path(index_request.repo_path).resolve()  # noqa: ASYNC240
    summary = await index_repository_with_resources(
        repo_path,
        runtime.neo4j,
        qdrant_client=runtime.qdrant,
        embedder=runtime.embedder,
    )
    global LAST_STATUS
    LAST_STATUS = IndexStatusResponse(
        status="ready",
        progress=1.0,
        entity_count=summary.total_entities,
    )
    return ApiEnvelope(
        success=True,
        data={
            **IndexStartedResponse(job_id=str(uuid.uuid4()), status="completed").model_dump(),
            "repo_path": summary.repo_path,
            "indexed_files": summary.indexed_files,
            "total_entities": summary.total_entities,
            "progress": asdict(summary.progress),
        },
        error=None,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )


@router.get("/index/status", response_model=ApiEnvelope)
async def index_status() -> ApiEnvelope:
    return ApiEnvelope(success=True, data=LAST_STATUS.model_dump(), duration_ms=0)
