"""Jira source client (placeholder)."""

import structlog
from typing import Any
from gateway.core.sources.base import BaseSource
from gateway.core.sources.models import SourceResponse

logger = structlog.get_logger(__name__)


class JiraSource(BaseSource):
    """Source for Jira ticket data."""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.name = "jira"

    async def query(self, query_type: str, params: dict[str, Any]) -> SourceResponse:
        """Query Jira for data."""
        if not self.enabled:
            return SourceResponse(
                source="jira",
                query_type=query_type,
                content="",
                metadata={},
                token_count=0,
                latency_ms=0,
                success=False,
                error="Jira source is disabled",
            )
        # Placeholder for actual Jira API calls
        return SourceResponse(
            source="jira",
            query_type=query_type,
            content="Jira source is not implemented yet",
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
