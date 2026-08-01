"""Optional Glama MCP Metadata Enrichment Client with non-blocking graceful fallback."""

from __future__ import annotations

from typing import Any, Dict, Optional
import httpx
import structlog

logger = structlog.get_logger(__name__)

GLAMA_BASE_URL = "https://glama.ai/api/mcp/v1"


class GlamaEnrichmentClient:
    """Optional enrichment client for fetching supplementary tool count and summary metadata from Glama."""

    async def fetch_enrichment(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Attempts to fetch metadata from Glama with 3s timeout and non-blocking fallback."""
        if not owner or not repo:
            return None

        url = f"{GLAMA_BASE_URL}/servers/{owner}/{repo}"
        try:
            async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "tool_count": data.get("toolCount") or data.get("tools_count"),
                        "readme_summary": data.get("summary") or data.get("description"),
                        "install_snippet": data.get("installSnippet"),
                    }
                else:
                    logger.debug("Glama enrichment HTTP non-200", status_code=resp.status_code, owner=owner, repo=repo)
                    return None
        except Exception as exc:
            logger.debug("Glama enrichment non-blocking exception", error=str(exc), owner=owner, repo=repo)
            return None
