"""Tokenizer data models."""

from pydantic import BaseModel


class TokenCountResult(BaseModel):
    """Result of counting tokens."""
    text: str
    token_count: int
