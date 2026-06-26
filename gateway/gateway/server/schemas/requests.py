"""HTTP request schemas."""

from pydantic import BaseModel
from typing import Optional, List


class GetContextRequest(BaseModel):
    """Request to get context for a task."""
    task: str
    max_tokens: int = 12000
    role: str = "developer"


class ValidateChangeRequest(BaseModel):
    """Request to validate a code change."""
    diff: str
    files: Optional[List[str]] = None
