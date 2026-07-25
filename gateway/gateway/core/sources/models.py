"""Source response models."""

from typing import Any
from pydantic import BaseModel, Field, model_validator


class SourceResponse(BaseModel):
    """Response from a source query."""

    source: str = ""
    query_type: str = ""
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    token_count: int = 0
    latency_ms: int = 0
    success: bool = True
    error: str | None = None

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "tokens_used" in values and "token_count" not in values:
                values["token_count"] = values.get("tokens_used", 0)
            if "duration_ms" in values and "latency_ms" not in values:
                values["latency_ms"] = int(values.get("duration_ms", 0))
        return values
