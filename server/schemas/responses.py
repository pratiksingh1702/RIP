

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ApiEnvelope(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None
    duration_ms: int


class IndexStatusResponse(BaseModel):
    status: str
    progress: float
    entity_count: int


class IndexStartedResponse(BaseModel):
    job_id: str
    status: str


class SearchResultResponse(BaseModel):
    entity_id: str
    entity_type: str
    name: str
    file_path: str
    language: str
    score: float
    raw_code: str
    callers: list[str] = []
    callees: list[str] = []

