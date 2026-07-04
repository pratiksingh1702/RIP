"""GitHub source client."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from gateway.config import settings
from gateway.core.sources.base import BaseSource
from gateway.core.sources.models import SourceResponse
from gateway.storage.source_registry import SourceRecord

logger = structlog.get_logger(__name__)


class GitHubSource(BaseSource):
    """Source for GitHub pull requests and commits."""

    name = "github"

    def __init__(self, enabled: bool = False, record: SourceRecord | None = None):
        self._record = record
        self.enabled = record.enabled if record is not None else enabled
        self.available = self.enabled
        self.repo = settings.github_repo.strip()
        self.api_url = settings.github_api_url.rstrip("/")
        self.token = settings.github_token.strip()
        if record is not None:
            self._apply_record(record)

    async def _load_runtime_config(self) -> None:
        """Hydrate repo/token from the persistent source registry when present."""
        if self._record is not None:
            self._apply_record(self._record)
            return
        try:
            from gateway.storage import source_registry as source_store

            record = await source_store.get_source("github")
        except Exception as exc:
            logger.debug("GitHub source registry lookup failed", error=str(exc))
            return
        if record is None:
            return
        config = record.mcp_config or {}
        self.repo = str(config.get("repo") or self.repo or "").strip()
        self.api_url = (record.endpoint_url or self.api_url).rstrip("/")
        self.token = (record.credential or self.token or "").strip()
        self.enabled = bool(record.enabled)

    def _apply_record(self, record: SourceRecord) -> None:
        config = record.mcp_config or {}
        self.repo = str(config.get("repo") or self.repo or "").strip()
        self.api_url = (record.endpoint_url or self.api_url).rstrip("/")
        self.token = (record.credential or self.token or "").strip()
        self.enabled = bool(record.enabled)
        self.available = self.enabled

    async def query(self, query_type: str, params: dict[str, Any]) -> SourceResponse:
        """Query GitHub REST APIs for repository activity."""
        start = time.time()
        await self._load_runtime_config()
        if not self.enabled:
            return self._error(query_type, "GitHub source is disabled", start)
        if not self.repo:
            self.repo = await self._repo_from_project(params)
        if not self.repo:
            return self._error(
                query_type,
                "GitHub repository is required. Add or re-index this project from a GitHub URL, then allocate GitHub to it.",
                start,
            )

        try:
            headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
                if query_type in {"recent_commits", "commits"}:
                    content, metadata = await self._recent_commits(client)
                elif query_type in {"similar_prs", "pr_descriptions", "open_prs"}:
                    content, metadata = await self._pull_requests(client, params)
                else:
                    content, metadata = await self._repository_search(client, params)

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
            logger.warning("GitHub query failed", query_type=query_type, error=str(exc))
            self.available = False
            return self._error(query_type, str(exc), start)

    async def health_check(self) -> bool:
        """Check GitHub configuration and API reachability."""
        await self._load_runtime_config()
        if not self.enabled or not self.repo:
            self.available = False
            return False
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
                response = await client.get(f"{self.api_url}/repos/{self.repo}")
            self.available = response.status_code < 500
            return self.available
        except Exception as exc:
            logger.warning("GitHub health check failed", error=str(exc))
            self.available = False
            return False

    async def _repo_from_project(self, params: dict[str, Any]) -> str:
        """Resolve owner/repo from the active RIP project instead of requiring CLI setup."""
        project_id = str(params.get("project_id") or "").strip()
        if not project_id:
            return ""
        try:
            from core.projects import get_project
            from core.storage.database import async_session_factory

            async with async_session_factory() as session:
                project = await get_project(session, project_id)
        except Exception as exc:
            logger.debug("GitHub project lookup failed", project_id=project_id, error=str(exc))
            return ""
        if project is None:
            return ""
        repo = self._repo_from_git_url(project.git_url or "")
        if repo:
            return repo
        return self._repo_from_local_git(project.root or "")

    def _repo_from_local_git(self, root: str) -> str:
        if not root:
            return ""
        try:
            from pathlib import Path

            git_config = Path(root) / ".git" / "config"
            if not git_config.exists():
                return ""
            text = git_config.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            logger.debug("GitHub local git config lookup failed", root=root, error=str(exc))
            return ""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("url ="):
                repo = self._repo_from_git_url(stripped.split("=", 1)[1].strip())
                if repo:
                    return repo
        return ""

    def _repo_from_git_url(self, value: str) -> str:
        raw = value.strip()
        if not raw:
            return ""
        if raw.count("/") == 1 and ":" not in raw and "@" not in raw:
            return raw.removesuffix(".git")
        if raw.startswith("git@"):
            raw = raw.replace(":", "/", 1).replace("git@", "ssh://git@", 1)
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        if host and host not in {"github.com", "www.github.com"}:
            return ""
        path = parsed.path.strip("/")
        parts = [part for part in path.split("/") if part]
        if len(parts) < 2:
            return ""
        return f"{parts[-2]}/{parts[-1].removesuffix('.git')}"

    async def _recent_commits(self, client: httpx.AsyncClient) -> tuple[str, dict[str, Any]]:
        response = await client.get(f"{self.api_url}/repos/{self.repo}/commits", params={"per_page": 10})
        response.raise_for_status()
        commits = response.json()
        lines = ["Recent GitHub commits:"]
        files: set[str] = set()
        for commit in commits:
            sha = commit.get("sha", "")[:8]
            data = commit.get("commit", {})
            message = (data.get("message") or "").splitlines()[0]
            author = (data.get("author") or {}).get("name", "unknown")
            date = (data.get("author") or {}).get("date", "")
            lines.append(f"- {sha} {message} ({author}, {date})")
        return "\n".join(lines), {"files": sorted(files), "repo": self.repo}

    async def _pull_requests(
        self,
        client: httpx.AsyncClient,
        params: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        query = params.get("query") or params.get("task") or ""
        response = await client.get(
            f"{self.api_url}/repos/{self.repo}/pulls",
            params={"state": "open", "per_page": 10},
        )
        response.raise_for_status()
        pulls = response.json()
        terms = {term.lower() for term in query.split() if len(term) > 3}
        scored = []
        for pr in pulls:
            text = f"{pr.get('title', '')} {pr.get('body') or ''}".lower()
            score = sum(1 for term in terms if term in text)
            scored.append((score, pr))
        scored.sort(key=lambda item: item[0], reverse=True)

        lines = ["Open GitHub pull requests:"]
        for score, pr in scored[:10]:
            title = pr.get("title", "")
            number = pr.get("number")
            user = (pr.get("user") or {}).get("login", "unknown")
            url = pr.get("html_url", "")
            lines.append(f"- #{number} {title} by {user} (match={score}) {url}")
        return "\n".join(lines), {"repo": self.repo, "query": query}

    async def _repository_search(
        self,
        client: httpx.AsyncClient,
        params: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        query = params.get("query") or params.get("task") or ""
        response = await client.get(
            f"{self.api_url}/search/code",
            params={"q": f"{query} repo:{self.repo}", "per_page": 10},
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        files = [item.get("path", "") for item in items if item.get("path")]
        lines = ["GitHub code search:"]
        for item in items:
            lines.append(f"- {item.get('path')} {item.get('html_url', '')}")
        return "\n".join(lines), {"repo": self.repo, "files": files, "query": query}

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
