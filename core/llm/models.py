"""LLM models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExplanationRequest(BaseModel):
    """Request for code symbol explanation."""

    symbol: str = Field(..., description="The symbol (function, class, etc.) to explain")
    context_level: str = Field("file", description="Context scope: 'file', 'class', or 'function'")
    provider: str | None = Field(
        None,
        description="Optional: LLM provider to use (e.g., google, openrouter)",
    )
    model: str | None = Field(
        None,
        description="Optional: LLM model to use (e.g., gemini-2.5-flash)",
    )


class ExplanationResponse(BaseModel):
    """Response containing symbol explanation and suggested improvements."""

    explanation: str = Field(..., description="Detailed explanation of the symbol")
    suggested_improvements: list[str] = Field(
        default_factory=list,
        description="List of proposed code quality or architectural improvements",
    )
