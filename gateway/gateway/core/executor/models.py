"""Executor data models."""

from pydantic import BaseModel


class ExecutorResult(BaseModel):
    """Result of executing a retrieval plan."""
    source_responses: list
    total_latency_ms: int
    success_count: int
    failure_count: int
