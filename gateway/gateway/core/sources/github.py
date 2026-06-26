"""GitHub source client (placeholder)."""

import structlog
from typing import Any
from gateway.core.sources.base import BaseSource
from gateway.core.sources.models import SourceResponse

logger = structlog.get_logger(__name__)


class GitHubSource(BaseSource):
    """Source for GitHub data (PRs, commits, etc.)."""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.name = "github"

    async def query(self, query_type: str, params: dict[str, Any]) -> SourceResponse:
        """Query GitHub for data."""
        if not self.enabled:
            return SourceResponse(
                source="github",
                query_type=query_type,
                content="",
                metadata={},
                token_count=0,
                latency_ms=0,
                success=False,
                error="GitHub source is disabled",
            )
        # Placeholder for actual GitHub API calls
        return SourceResponse(
            source="github",
            query_type=query_type,
            content="GitHub source is not implemented yet",
            metadata=params,
            token_count=0,
            latency_ms=10,
            success=True,
        )

    def is_available(self) -> bool:
        """Check if source is available."""
        return self.enabled

    async def health_check(self) -> bool:
        """Check if source is healthy."""
        return self.enabled
