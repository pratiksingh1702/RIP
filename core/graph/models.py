"""Graph data models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    label: str
    name: str
    fqn: str | None = None
    file_path: str | None = None
    language: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship_type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class FlowHop(BaseModel):
    from_symbol: str
    to_symbol: str
    relationship_type: str
    file_path: str | None = None
    line: int | None = None


class FlowTrace(BaseModel):
    entry_point: str
    hops: list[FlowHop]
    mermaid: str = ""
    explanation: str | None = None


class ImpactResult(BaseModel):
    symbol: str
    affected_files: list[str]
    affected_apis: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    affected_nodes: list[GraphNode] = Field(default_factory=list)


class SearchResult(BaseModel):
    entity_id: str
    entity_type: str
    name: str
    file_path: str
    language: str
    score: float
    raw_code: str
    callers: list[str] = Field(default_factory=list)
    callees: list[str] = Field(default_factory=list)

