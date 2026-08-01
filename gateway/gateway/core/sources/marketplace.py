"""Dynamic Open-Source MCP Marketplace Catalog Aggregator Engine.

Fetches live MCP tool catalogs directly from multiple open-source registries:
- Smithery Registry API (https://registry.smithery.ai/servers)
- Glama MCP Registry API (https://glama.ai/api/mcp/servers)
- ModelContextProtocol GitHub Registry (https://raw.githubusercontent.com/modelcontextprotocol/servers/main/src/registry.json)
- Community MCP Index & Disk Cache (marketplace_cache.json)
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)

# Open-Source MCP Registry API Endpoints
REGISTRY_ENDPOINTS = [
    {
        "name": "smithery",
        "url": "https://registry.smithery.ai/servers",
        "type": "smithery",
    },
    {
        "name": "glama",
        "url": "https://glama.ai/api/mcp/servers",
        "type": "glama",
    },
    {
        "name": "mcp_official",
        "url": "https://raw.githubusercontent.com/modelcontextprotocol/servers/main/src/registry.json",
        "type": "github_official",
    },
]

CACHE_FILE_PATH = Path(__file__).parent.parent.parent / "storage" / "marketplace_cache.json"


@dataclass
class MCPToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPSourceDetail:
    id: str
    name: str
    publisher: str
    author_url: str
    repository_url: str
    description: str
    category: str  # "code", "database", "tickets", "docs", "communication", "search", "infrastructure", "analytics", "payments", "ai"
    icon_key: str
    transport: str  # "stdio" or "http" (SSE)
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    endpoint_url: Optional[str] = None
    auth_type: str = "oauth2"  # "oauth2", "api_key", "bearer_token", "none"
    domain_hints: List[str] = field(default_factory=list)
    tools: List[MCPToolSpec] = field(default_factory=list)
    install_instructions: str = ""
    is_official: bool = True
    stars_count: int = 0
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["tools"] = [asdict(t) if isinstance(t, MCPToolSpec) else t for t in self.tools]
        return d


# Minimal seed fallback for offline cold boot
OFFLINE_SEED_CATALOG: List[MCPSourceDetail] = [
    MCPSourceDetail(
        id="github",
        name="GitHub MCP Server",
        publisher="ModelContextProtocol",
        author_url="https://github.com/modelcontextprotocol/servers/tree/main/src/github",
        repository_url="https://github.com/modelcontextprotocol/servers",
        description="Inspect repositories, manage pull requests, create issues, and search code.",
        category="code",
        icon_key="github",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        auth_type="oauth2",
        domain_hints=["code", "git", "pr", "issues", "github"],
        tools=[
            MCPToolSpec("search_repositories", "Search GitHub repositories.", {"query": {"type": "string"}}),
            MCPToolSpec("create_issue", "Create GitHub issue.", {"owner": {"type": "string"}, "repo": {"type": "string"}, "title": {"type": "string"}}),
        ],
        install_instructions="Run via NPX or connect via GitHub OAuth 2.0 app credentials.",
        is_official=True,
        stars_count=12400,
        updated_at="2026-07-28T00:00:00Z",
    ),
    MCPSourceDetail(
        id="postgres",
        name="PostgreSQL Database MCP",
        publisher="ModelContextProtocol",
        author_url="https://github.com/modelcontextprotocol/servers/tree/main/src/postgres",
        repository_url="https://github.com/modelcontextprotocol/servers",
        description="Inspect database schemas, execute read-only queries, and trace table relations.",
        category="database",
        icon_key="postgres",
        transport="stdio",
        command="uvx",
        args=["mcp-server-postgres", "--connection-string"],
        auth_type="api_key",
        domain_hints=["database", "sql", "db", "postgres"],
        tools=[
            MCPToolSpec("query", "Execute a read-only SQL query.", {"sql": {"type": "string"}}),
        ],
        install_instructions="Requires a valid PostgreSQL connection URI string.",
        is_official=True,
        stars_count=6700,
        updated_at="2026-07-20T00:00:00Z",
    ),
]


class MarketplaceCatalogEngine:
    def __init__(self):
        self._catalog: Dict[str, MCPSourceDetail] = {}
        self._last_synced_at: Optional[datetime] = None
        self._is_syncing: bool = False

        # 1. Load offline seed
        for item in OFFLINE_SEED_CATALOG:
            self._catalog[item.id] = item

        # 2. Load disk cache if available
        self._load_disk_cache()

        # 3. Schedule background fetch
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.sync_online_catalog())
        except Exception:
            pass

    def _load_disk_cache(self):
        """Loads cached marketplace entries from disk."""
        if not CACHE_FILE_PATH.exists():
            return
        try:
            with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        sid = item.get("id")
                        if not sid:
                            continue
                        tools_raw = item.get("tools", [])
                        tools = [
                            MCPToolSpec(
                                name=t.get("name", ""),
                                description=t.get("description", ""),
                                input_schema=t.get("input_schema", {}),
                            )
                            for t in tools_raw
                        ]
                        detail = MCPSourceDetail(
                            id=sid,
                            name=item.get("name", sid.title()),
                            publisher=item.get("publisher", "Community"),
                            author_url=item.get("author_url", ""),
                            repository_url=item.get("repository_url", ""),
                            description=item.get("description", ""),
                            category=item.get("category", "code"),
                            icon_key=item.get("icon_key", "custom"),
                            transport=item.get("transport", "stdio"),
                            command=item.get("command"),
                            args=item.get("args", []),
                            endpoint_url=item.get("endpoint_url"),
                            auth_type=item.get("auth_type", "api_key"),
                            domain_hints=item.get("domain_hints", []),
                            tools=tools,
                            install_instructions=item.get("install_instructions", ""),
                            is_official=item.get("is_official", False),
                            stars_count=item.get("stars_count", 0),
                            updated_at=item.get("updated_at", ""),
                        )
                        self._catalog[sid] = detail
                    logger.info("Loaded cached MCP Marketplace catalog from disk", count=len(self._catalog))
        except Exception as exc:
            logger.warning("Failed loading disk cache for marketplace", error=str(exc))

    def _save_disk_cache(self):
        """Saves current catalog entries to disk cache."""
        try:
            CACHE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = [item.to_dict() for item in self._catalog.values()]
            with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info("Persisted MCP Marketplace catalog to disk cache", count=len(self._catalog))
        except Exception as exc:
            logger.warning("Failed saving disk cache for marketplace", error=str(exc))

    def list_catalog(self, category: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        items = list(self._catalog.values())
        if category and category.lower() != "all":
            items = [item for item in items if item.category.lower() == category.lower()]
        if search:
            query = search.lower()
            items = [
                item for item in items
                if query in item.name.lower()
                or query in item.description.lower()
                or any(query in hint for hint in item.domain_hints)
            ]
        return [item.to_dict() for item in items]

    def get_detail(self, source_id: str) -> Optional[Dict[str, Any]]:
        item = self._catalog.get(source_id)
        return item.to_dict() if item else None

    def _infer_category(self, name: str, desc: str, keywords: List[str]) -> str:
        text = f"{name} {desc} {' '.join(keywords)}".lower()
        if any(k in text for k in ["code", "git", "repo", "ast", "semgrep", "pr", "branch"]):
            return "code"
        if any(k in text for k in ["postgres", "sql", "mongo", "db", "database", "redis", "table", "query", "schema"]):
            return "database"
        if any(k in text for k in ["jira", "linear", "ticket", "issue", "task", "zendesk", "asana", "trello"]):
            return "tickets"
        if any(k in text for k in ["notion", "docs", "wiki", "note", "confluence", "drive", "figma", "obsidian"]):
            return "docs"
        if any(k in text for k in ["slack", "discord", "chat", "message", "teams", "telegram"]):
            return "communication"
        if any(k in text for k in ["search", "web", "scrape", "puppeteer", "tavily", "firecrawl", "google"]):
            return "search"
        if any(k in text for k in ["docker", "k8s", "kubernetes", "aws", "cloud", "terraform", "dns"]):
            return "infrastructure"
        if any(k in text for k in ["sentry", "datadog", "metric", "log", "grafana", "analytics", "posthog"]):
            return "analytics"
        if any(k in text for k in ["stripe", "payment", "billing", "crm", "hubspot"]):
            return "payments"
        if any(k in text for k in ["ai", "model", "replicate", "huggingface", "llm", "embedding"]):
            return "ai"
        return "code"

    async def sync_online_catalog(self) -> bool:
        """Fetches live open-source MCP catalog entries directly from public registry APIs."""
        if self._is_syncing:
            return False

        self._is_syncing = True
        synced_count = 0

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            for endpoint in REGISTRY_ENDPOINTS:
                try:
                    resp = await client.get(endpoint["url"])
                    if resp.status_code != 200:
                        continue

                    raw_data = resp.json()
                    servers = []
                    if isinstance(raw_data, list):
                        servers = raw_data
                    elif isinstance(raw_data, dict):
                        servers = raw_data.get("servers") or raw_data.get("data") or raw_data.get("items") or []

                    for s in servers:
                        if not isinstance(s, dict):
                            continue

                        sid = s.get("id") or s.get("name", "").lower().replace(" ", "-").replace("/", "-")
                        if not sid:
                            continue

                        name = s.get("name") or sid.title()
                        desc = s.get("description") or "Open-Source MCP Server"
                        publisher = s.get("publisher") or s.get("author") or s.get("organization") or "Open Source Community"
                        author_url = s.get("homepage") or s.get("url") or s.get("repository") or "https://github.com/modelcontextprotocol"
                        repo_url = s.get("repository") or s.get("repo") or author_url
                        
                        command = s.get("command") or "npx"
                        args = s.get("args") or []
                        if isinstance(args, str):
                            args = [args]

                        endpoint_url = s.get("endpoint_url") or s.get("url") if s.get("transport") == "http" else None
                        transport = "http" if endpoint_url or s.get("transport") == "http" else "stdio"

                        auth_type = s.get("auth_type") or ("oauth2" if "oauth" in str(s).lower() else "api_key" if "key" in str(s).lower() else "none")
                        category = s.get("category") or self._infer_category(name, desc, s.get("tags", []))

                        tools_raw = s.get("tools") or []
                        tools = []
                        if isinstance(tools_raw, list):
                            for t in tools_raw:
                                if isinstance(t, dict):
                                    tools.append(
                                        MCPToolSpec(
                                            name=t.get("name", "tool"),
                                            description=t.get("description", "MCP Tool Functionality"),
                                            input_schema=t.get("input_schema") or t.get("schema") or {},
                                        )
                                    )

                        detail = MCPSourceDetail(
                            id=sid,
                            name=name,
                            publisher=publisher,
                            author_url=author_url,
                            repository_url=repo_url,
                            description=desc,
                            category=category,
                            icon_key=category,
                            transport=transport,
                            command=command if transport == "stdio" else None,
                            args=args if transport == "stdio" else [],
                            endpoint_url=endpoint_url,
                            auth_type=auth_type,
                            domain_hints=[sid, category, name.lower()],
                            tools=tools,
                            install_instructions=f"1-Click Install from {endpoint['name'].title()} Marketplace Registry.",
                            is_official=s.get("is_official", "official" in str(publisher).lower()),
                            stars_count=s.get("stars") or s.get("stars_count") or 50,
                            updated_at=datetime.now(timezone.utc).isoformat(),
                        )

                        self._catalog[sid] = detail
                        synced_count += 1

                except Exception as exc:
                    logger.debug("Registry catalog fetch warning", endpoint=endpoint["name"], error=str(exc))

        self._is_syncing = False
        if synced_count > 0:
            self._last_synced_at = datetime.now(timezone.utc)
            self._save_disk_cache()
            logger.info("Live open-source MCP Marketplace catalog sync complete", total_catalog_sources=len(self._catalog))
            return True

        return False


# Global Singleton Marketplace Instance
marketplace_engine = MarketplaceCatalogEngine()
