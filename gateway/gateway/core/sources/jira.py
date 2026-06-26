"""Jira source client."""

from __future__ import annotations

import re
import time
from typing import Any

import httpx
import structlog

from gateway.config import settings
from gateway.core.sources.base import BaseSource
from gateway.core.sources.models import SourceResponse

logger = structlog.get_logger(__name__)


class JiraSource(BaseSource):
    """Source for Jira ticket details and acceptance criteria."""

    name = "jira"

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.available = enabled
        self.base_url = settings.jira_url.rstrip("/")
        self.token = settings.jira_token.strip()
        self.email = settings.jira_email.strip()
        self.project_key = settings.jira_project_key.strip()

    async def query(self, query_type: str, params: dict[str, Any]) -> SourceResponse:
        """Fetch Jira issue context."""
        start = time.time()
        if not self.enabled:
            return self._error(query_type, "Jira source is disabled", start)
        if not self.base_url or not self.token:
            return self._error(query_type, "GATEWAY_JIRA_URL and GATEWAY_JIRA_TOKEN are required", start)

        try:
            issue_key = self._extract_issue_key(params)
            async with httpx.AsyncClient(
                timeout=10.0,
                auth=self._auth(),
                headers=self._headers(),
            ) as client:
                if issue_key:
                    content, metadata = await self._fetch_issue(client, issue_key)
                else:
                    content, metadata = await self._search_issues(client, params)
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
            logger.warning("Jira query failed", query_type=query_type, error=str(exc))
            self.available = False
            return self._error(query_type, str(exc), start)

    async def health_check(self) -> bool:
        """Check Jira API reachability."""
        if not self.enabled or not self.base_url or not self.token:
            self.available = False
            return False
        try:
            async with httpx.AsyncClient(
                timeout=5.0,
                auth=self._auth(),
                headers=self._headers(),
            ) as client:
                response = await client.get(f"{self.base_url}/rest/api/3/myself")
            self.available = response.status_code < 500
            return self.available
        except Exception as exc:
            logger.warning("Jira health check failed", error=str(exc))
            self.available = False
            return False

    async def _fetch_issue(self, client: httpx.AsyncClient, issue_key: str) -> tuple[str, dict[str, Any]]:
        response = await client.get(f"{self.base_url}/rest/api/3/issue/{issue_key}")
        response.raise_for_status()
        issue = response.json()
        fields = issue.get("fields", {})
        summary = fields.get("summary", "")
        status = ((fields.get("status") or {}).get("name")) or "unknown"
        description = self._plain_text(fields.get("description"))
        content = (
            f"Jira issue {issue_key}\n"
            f"Summary: {summary}\n"
            f"Status: {status}\n\n"
            f"{description}"
        ).strip()
        return content, {"issue_key": issue_key, "status": status}

    async def _search_issues(
        self,
        client: httpx.AsyncClient,
        params: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        query = params.get("query") or params.get("task") or ""
        jql = f'text ~ "{query}"'
        if self.project_key:
            jql = f'project = "{self.project_key}" AND {jql}'
        response = await client.get(
            f"{self.base_url}/rest/api/3/search",
            params={"jql": jql, "maxResults": 5, "fields": "summary,status"},
        )
        response.raise_for_status()
        issues = response.json().get("issues", [])
        lines = ["Relevant Jira issues:"]
        for issue in issues:
            fields = issue.get("fields", {})
            status = ((fields.get("status") or {}).get("name")) or "unknown"
            lines.append(f"- {issue.get('key')}: {fields.get('summary', '')} ({status})")
        return "\n".join(lines), {"query": query, "issue_keys": [i.get("key") for i in issues]}

    def _extract_issue_key(self, params: dict[str, Any]) -> str | None:
        text = " ".join(str(value) for value in params.values() if value)
        match = re.search(r"\b[A-Z][A-Z0-9]+-\d+\b", text)
        return match.group(0) if match else None

    def _plain_text(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            parts: list[str] = []
            for child in value.get("content", []):
                parts.append(self._plain_text(child))
            if value.get("text"):
                parts.append(str(value["text"]))
            return "\n".join(part for part in parts if part)
        if isinstance(value, list):
            return "\n".join(self._plain_text(item) for item in value)
        return ""

    def _auth(self) -> httpx.Auth | None:
        if self.email:
            return (self.email, self.token)
        return None

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token and not self.email:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

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
