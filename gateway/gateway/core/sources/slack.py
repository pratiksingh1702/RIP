"""Slack source client."""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from gateway.config import settings
from gateway.core.sources.base import BaseSource
from gateway.core.sources.models import SourceResponse

logger = structlog.get_logger(__name__)


class SlackSource(BaseSource):
    """Source for Slack discussion context."""

    name = "slack"

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.available = enabled
        self.token = settings.slack_token.strip()
        self.channel_id = settings.slack_channel_id.strip()

    async def query(self, query_type: str, params: dict[str, Any]) -> SourceResponse:
        """Fetch Slack search or channel context."""
        start = time.time()
        if not self.enabled:
            return self._error(query_type, "Slack source is disabled", start)
        if not self.token:
            return self._error(query_type, "GATEWAY_SLACK_TOKEN is required", start)

        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
                if query_type == "search":
                    content, metadata = await self._search(client, params)
                else:
                    content, metadata = await self._history(client)
            self.available = True
            return SourceResponse(
                source=self.name,
                query_type=query_type,
                content=content,
                metadata=metadata,
                token_count=len(content.split()),
                latency_ms=self._latency(start),
                success=True,
            )
        except Exception as exc:
            logger.warning("Slack query failed", query_type=query_type, error=str(exc))
            self.available = False
            return self._error(query_type, str(exc), start)

    async def health_check(self) -> bool:
        """Check Slack API reachability."""
        if not self.enabled or not self.token:
            self.available = False
            return False
        try:
            async with httpx.AsyncClient(
                timeout=5.0,
                headers={"Authorization": f"Bearer {self.token}"},
            ) as client:
                response = await client.get("https://slack.com/api/auth.test")
            data = response.json()
            self.available = bool(data.get("ok"))
            return self.available
        except Exception as exc:
            logger.warning("Slack health check failed", error=str(exc))
            self.available = False
            return False

    async def _search(
        self,
        client: httpx.AsyncClient,
        params: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        query = params.get("query") or params.get("task") or ""
        response = await client.get(
            "https://slack.com/api/search.messages",
            params={"query": query, "count": 10, "sort": "timestamp"},
        )
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("error", "Slack search failed"))
        matches = data.get("messages", {}).get("matches", [])
        lines = ["Relevant Slack messages:"]
        for match in matches:
            channel = (match.get("channel") or {}).get("name", "unknown")
            user = match.get("user", "unknown")
            text = self._clean(match.get("text", ""))
            lines.append(f"- #{channel} {user}: {text}")
        return "\n".join(lines), {"query": query, "message_count": len(matches)}

    async def _history(self, client: httpx.AsyncClient) -> tuple[str, dict[str, Any]]:
        if not self.channel_id:
            raise RuntimeError("GATEWAY_SLACK_CHANNEL_ID is required for history queries")
        response = await client.get(
            "https://slack.com/api/conversations.history",
            params={"channel": self.channel_id, "limit": 10},
        )
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("error", "Slack history failed"))
        messages = data.get("messages", [])
        lines = ["Recent Slack channel messages:"]
        for message in messages:
            user = message.get("user", "unknown")
            text = self._clean(message.get("text", ""))
            lines.append(f"- {user}: {text}")
        return "\n".join(lines), {"channel_id": self.channel_id, "message_count": len(messages)}

    def _clean(self, text: str) -> str:
        return " ".join(text.replace("\n", " ").split())

    def _error(self, query_type: str, message: str, start: float) -> SourceResponse:
        return SourceResponse(
            source=self.name,
            query_type=query_type,
            content="",
            metadata={},
            token_count=0,
            latency_ms=self._latency(start),
            success=False,
            error=message,
        )

    def _latency(self, start: float) -> int:
        return int((time.time() - start) * 1000)
