"""API request schemas."""

from __future__ import annotations

from pydantic import BaseModel


class IndexRequest(BaseModel):
    repo_path: str
    languages: list[str] | None = None
    incremental: bool = False


class ExplainRequest(BaseModel):
    query: str
    model: str | None = None
