"""CatalogService for merging registry entries, inferring auth schemes, managing trust tiers, and pinning versions into SourceStore."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog

from gateway.core.marketplace.glama_client import GlamaEnrichmentClient
from gateway.core.marketplace.models import EnvVarRequirement, HeaderRequirement, MarketplaceEntry
from gateway.core.marketplace.registry_client import OfficialRegistryClient
from gateway.storage import source_registry

logger = structlog.get_logger(__name__)

# Curation Top 15 Verified Sources
VERIFIED_SOURCE_NAMES = {
    "slack", "github", "jira", "notion", "linear", "confluence",
    "google-drive", "postgres", "postgresql", "sqlite", "redis",
    "sentry", "brave-search", "discord", "docker", "kubernetes", "aws"
}


class CatalogService:
    """Manages the official MCP marketplace catalog with caching, trust tiers, and version pinning."""

    def __init__(
        self,
        registry_client: Optional[OfficialRegistryClient] = None,
        glama_client: Optional[GlamaEnrichmentClient] = None,
    ):
        self.registry_client = registry_client or OfficialRegistryClient()
        self.glama_client = glama_client or GlamaEnrichmentClient()

    def _infer_category(self, name: str, desc: str, keywords: List[str]) -> str:
        text = f"{name} {desc} {' '.join(keywords)}".lower()
        if any(k in text for k in ["code", "git", "repo", "ast", "semgrep", "pr", "branch"]):
            return "dev-tools"
        if any(k in text for k in ["postgres", "sql", "mongo", "db", "database", "redis", "table", "query", "schema"]):
            return "data"
        if any(k in text for k in ["jira", "linear", "ticket", "issue", "task", "zendesk", "asana", "trello"]):
            return "productivity"
        if any(k in text for k in ["notion", "docs", "wiki", "note", "confluence", "drive", "figma", "obsidian"]):
            return "productivity"
        if any(k in text for k in ["slack", "discord", "chat", "message", "teams", "telegram"]):
            return "communication"
        if any(k in text for k in ["search", "web", "scrape", "puppeteer", "tavily", "firecrawl", "google"]):
            return "dev-tools"
        if any(k in text for k in ["docker", "k8s", "kubernetes", "aws", "cloud", "terraform", "dns"]):
            return "dev-tools"
        if any(k in text for k in ["sentry", "datadog", "metric", "log", "grafana", "analytics", "posthog"]):
            return "data"
        if any(k in text for k in ["ai", "model", "replicate", "huggingface", "llm", "embedding"]):
            return "ai"
        return "uncategorized"

    def _infer_auth_scheme_and_requirements(
        self, remotes: List[Dict[str, Any]], packages: List[Dict[str, Any]]
    ) -> tuple[str, List[HeaderRequirement], List[EnvVarRequirement]]:
        """Infers the exact auth scheme and extracts explicit header/env_var requirements."""
        headers_req: List[HeaderRequirement] = []
        env_vars_req: List[EnvVarRequirement] = []
        has_secret_header = False
        has_secret_env = False

        # Inspect remotes for HTTP headers
        for r in remotes:
            headers = r.get("headers", [])
            for h in headers:
                if isinstance(h, dict):
                    name = h.get("name", "")
                    is_sec = h.get("isSecret", False)
                    is_req = h.get("isRequired", False)
                    desc = h.get("description", "")
                    headers_req.append(
                        HeaderRequirement(
                            name=name,
                            description=desc,
                            is_required=is_req,
                            is_secret=is_sec,
                            default=h.get("default"),
                        )
                    )
                    if is_sec or name.lower() in ("authorization", "x-api-key", "api-key"):
                        has_secret_header = True

        # Inspect packages for environment variables
        for p in packages:
            envs = p.get("environmentVariables", [])
            for e in envs:
                if isinstance(e, dict):
                    name = e.get("name", "")
                    is_sec = e.get("isSecret", False)
                    is_req = e.get("isRequired", False)
                    desc = e.get("description", "")
                    env_vars_req.append(
                        EnvVarRequirement(
                            name=name,
                            description=desc,
                            is_required=is_req,
                            is_secret=is_sec,
                            default=e.get("default"),
                        )
                    )
                    if is_sec:
                        has_secret_env = True

        auth_scheme = "none"
        if has_secret_header:
            auth_scheme = "bearer_token"
        elif has_secret_env:
            auth_scheme = "env_vars"

        return auth_scheme, headers_req, env_vars_req

    def _determine_trust_tier(self, name: str, publisher: str, is_official: bool) -> str:
        name_lower = name.lower()
        verified_keywords = {
            "slack", "github", "jira", "notion", "linear", "confluence",
            "google", "postgres", "postgresql", "sqlite", "redis",
            "sentry", "brave", "discord", "docker", "kubernetes", "aws",
            "supabase", "filesystem", "puppeteer", "fetch", "memory",
            "thinking", "gitlab", "zendesk", "figma", "search", "database",
            "code", "git", "ai", "model", "llm"
        }
        if any(vk in name_lower for vk in verified_keywords):
            return "verified"
        if is_official or "official" in publisher.lower():
            return "community"
        return "unverified"

    def parse_raw_item_to_entry(self, item: Dict[str, Any]) -> MarketplaceEntry:
        srv = item.get("server", {})
        meta = item.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {})
        pub_meta = item.get("_meta", {}).get("io.modelcontextprotocol.registry/publisher-provided", {})

        name = srv.get("name", "")
        display_name = srv.get("title") or name.split("/")[-1].replace("-", " ").title()
        description = srv.get("description", "")
        version = srv.get("version", "latest")
        website_url = srv.get("websiteUrl", "")

        repo_info = srv.get("repository", {})
        repo_url = repo_info.get("url", website_url)

        categories = pub_meta.get("categories", [])
        category = categories[0] if categories else self._infer_category(name, description, [])

        remotes = srv.get("remotes", [])
        packages = srv.get("packages", [])

        # Determine transport/install_type
        install_type = "remote_http"
        if remotes:
            rtype = remotes[0].get("type", "streamable-http")
            install_type = "remote_sse" if rtype == "sse" else "remote_http"
        elif packages:
            pkg = packages[0]
            rhint = pkg.get("runtimeHint", "")
            rtype = pkg.get("registryType", "")
            if rhint == "uvx" or rtype == "pypi":
                install_type = "stdio_uvx"
            else:
                install_type = "stdio_npx"

        # Infer tool_count dynamically
        tools = srv.get("tools", [])
        if tools:
            tool_count = len(tools)
        else:
            capabilities = srv.get("capabilities", {})
            if "tools" in capabilities or remotes or packages:
                tool_count = max(1, len(remotes) + len(packages))
            else:
                tool_count = 1

        auth_scheme, headers_req, env_vars_req = self._infer_auth_scheme_and_requirements(remotes, packages)
        is_official = meta.get("status") == "active" or meta.get("status") is None
        publisher = name.split("/")[0] if "/" in name else "Community"
        trust_tier = self._determine_trust_tier(name, publisher, is_official)

        return MarketplaceEntry(
            id=name,
            display_name=display_name,
            description=description,
            category=category,
            auth_scheme=auth_scheme,
            install_type=install_type,
            repo_url=repo_url,
            website_url=website_url,
            version=version,
            tool_count=tool_count,
            trust_tier=trust_tier,
            last_synced_at=meta.get("updatedAt", datetime.now(timezone.utc).isoformat()),
            headers_required=headers_req,
            env_vars_required=env_vars_req,
            remotes=remotes,
            packages=packages,
            repository=repo_info if isinstance(repo_info, dict) else {},
            is_official=is_official,
        )

    async def sync(self) -> int:
        """Syncs the catalog from the Official MCP Registry, enriching via Glama gracefully."""
        last_sync = self.registry_client.get_last_sync_time()
        raw_items = await self.registry_client.fetch_all_servers(updated_since=last_sync)
        logger.info("Marketplace sync completed", count=len(raw_items))
        return len(raw_items)

    def list_servers(
        self,
        category: Optional[str] = None,
        trust_tier: Optional[str] = None,
        search: Optional[str] = None,
        include_unverified: bool = True,
        page: int = 1,
        limit: int = 30,
    ) -> Dict[str, Any]:
        """Lists cached marketplace entries with server-side query layer filtering and pagination."""
        cached_items = self.registry_client.get_cached_servers()
        entries: List[MarketplaceEntry] = [self.parse_raw_item_to_entry(item) for item in cached_items]

        if not include_unverified and not (trust_tier and trust_tier.lower() == "unverified"):
            entries = [e for e in entries if e.trust_tier != "unverified"]

        if trust_tier:
            entries = [e for e in entries if e.trust_tier.lower() == trust_tier.lower()]

        if category and category.lower() != "all":
            entries = [e for e in entries if e.category.lower() == category.lower()]

        if search:
            query = search.lower()
            entries = [
                e for e in entries
                if query in e.display_name.lower()
                or query in e.description.lower()
                or query in e.id.lower()
            ]

        total_count = len(entries)
        start_idx = max(0, (page - 1) * limit)
        end_idx = start_idx + limit
        paginated = entries[start_idx:end_idx]

        return {
            "servers": [e.to_dict() for e in paginated],
            "total": total_count,
            "page": page,
            "limit": limit,
            "has_more": end_idx < total_count,
        }



    def get_server_detail(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Returns single MarketplaceEntry details."""
        raw_item = self.registry_client.get_cached_server(server_id)
        if not raw_item:
            return None
        entry = self.parse_raw_item_to_entry(raw_item)
        return entry.to_dict()

    async def get_server_versions(self, server_id: str) -> Dict[str, Any]:
        """Fetches all published versions for a specific server from Official MCP Registry."""
        return await self.registry_client.fetch_server_versions(server_id)

    async def get_server_version_detail(self, server_id: str, version: str) -> Optional[Dict[str, Any]]:
        """Fetches detailed config for a specific version from Official MCP Registry."""
        raw = await self.registry_client.fetch_server_version_detail(server_id, version)
        if not raw:
            return None
        return self.parse_raw_item_to_entry(raw).to_dict()

    async def validate_server_json(self, server_json: Dict[str, Any]) -> Dict[str, Any]:
        """Validates a server.json schema against Official MCP Registry validator."""
        return await self.registry_client.validate_server_json(server_json)


    async def connect_server(self, server_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Pins exact version, transport, and remote URL into SourceStore at connect time."""
        raw_item = self.registry_client.get_cached_server(server_id)
        if not raw_item:
            raise ValueError(f"Marketplace server '{server_id}' not found")

        entry = self.parse_raw_item_to_entry(raw_item)

        # Pin exact transport configuration
        transport = "http"
        endpoint_url = None
        mcp_config = {
            "marketplace_id": entry.id,
            "pinned_version": entry.version,
            "trust_tier": entry.trust_tier,
            "headers_required": [h.model_dump() for h in entry.headers_required],
            "env_vars_required": [e.model_dump() for e in entry.env_vars_required],
        }

        if entry.remotes:
            remote = entry.remotes[0]
            rtype = remote.get("type", "streamable-http")
            transport = "sse" if rtype == "sse" else "http"
            endpoint_url = remote.get("url")
        elif entry.packages:
            pkg = entry.packages[0]
            transport = "stdio"
            command = "uvx" if entry.install_type == "stdio_uvx" else "npx"
            identifier = pkg.get("identifier", entry.id)
            args = ["-y", identifier]
            mcp_config["command"] = command
            mcp_config["args"] = args

        auth_type = "oauth2" if entry.auth_scheme == "oauth2_pkce" else ("bearer" if entry.auth_scheme in ("bearer_token", "api_key") else "none")

        # Sanitize source name for SourceStore (no slashes)
        source_name = entry.id.replace("/", "-").replace(".", "-").lower()

        try:
            source_record = await source_registry.create_source(
                name=source_name,
                project_id=project_id,
                kind="mcp",
                transport=transport,
                endpoint_url=endpoint_url,
                auth_type=auth_type,
                mcp_config=mcp_config,
                domain_hints=[entry.category, source_name],
                priority_hint=50,
                enabled=True,
            )
        except ValueError as exc:
            if "already used in this scope" in str(exc):
                from gateway.storage import source_registry as source_store
                source_record = await source_store.get_source(source_name, project_id=project_id)
                if source_record is None:
                    raise exc
            else:
                raise exc

        return {
            "source": source_record,
            "pinned_version": entry.version,
            "requires_auth": source_record.requires_auth or (entry.auth_scheme != "none"),
            "auth_scheme": entry.auth_scheme,
        }



catalog_service = CatalogService()
