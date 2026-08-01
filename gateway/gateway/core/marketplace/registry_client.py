"""Official MCP Registry API Client with pagination, exponential backoff, and SQLite caching."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog

logger = structlog.get_logger(__name__)

OFFICIAL_REGISTRY_BASE_URL = "https://registry.modelcontextprotocol.io/v0.1"
DB_PATH = Path(__file__).parent.parent.parent / "storage" / "marketplace_cache.db"


class OfficialRegistryClient:
    """Wraps calls to the Official MCP Registry API with retry backoff and SQLite cache."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_sqlite()

    def _init_sqlite(self):
        """Initializes the SQLite marketplace_cache table."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marketplace_cache (
                    id TEXT PRIMARY KEY,
                    raw_json TEXT NOT NULL,
                    is_latest BOOLEAN NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'active',
                    updated_at TEXT NOT NULL,
                    synced_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS registry_sync_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def get_last_sync_time(self) -> Optional[str]:
        """Returns the last successful sync timestamp ISO string."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute("SELECT value FROM registry_sync_meta WHERE key = 'last_synced_at'")
            row = cur.fetchone()
            return row[0] if row else None

    def _set_last_sync_time(self, timestamp_iso: str):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO registry_sync_meta (key, value) VALUES ('last_synced_at', ?)",
                (timestamp_iso,),
            )
            conn.commit()

    async def _fetch_with_backoff(
        self, client: httpx.AsyncClient, url: str, params: Dict[str, Any], max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """Executes HTTP GET request with exponential backoff on retriable errors."""
        wait_sec = 1.0
        for attempt in range(1, max_retries + 1):
            try:
                resp = await client.get(url, params=params, timeout=12.0)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        "Registry API rate-limited or error response",
                        status_code=resp.status_code,
                        attempt=attempt,
                        wait_sec=wait_sec,
                    )
                    await asyncio.sleep(wait_sec)
                    wait_sec *= 2.0
                else:
                    logger.error("Registry API non-retriable error", status_code=resp.status_code, body=resp.text[:200])
                    return None
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                logger.warning("Registry API network exception", error=str(exc), attempt=attempt, wait_sec=wait_sec)
                await asyncio.sleep(wait_sec)
                wait_sec *= 2.0

        logger.error("Registry API max retries exceeded", url=url)
        return None

    async def fetch_all_servers(self, updated_since: Optional[str] = None, max_pages: int = 10) -> List[Dict[str, Any]]:
        """Paginates through Official MCP Registry GET /v0.1/servers filtering for active servers."""
        cursor: Optional[str] = None
        fetched_records: List[Dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat()
        page_count = 0

        async with httpx.AsyncClient(follow_redirects=True) as client:
            while page_count < max_pages:
                page_count += 1
                params: Dict[str, Any] = {
                    "limit": 100,
                    "version": "latest",
                }
                if cursor:
                    params["cursor"] = cursor
                if updated_since:
                    params["updated_since"] = updated_since

                url = f"{OFFICIAL_REGISTRY_BASE_URL}/servers"
                data = await self._fetch_with_backoff(client, url, params)
                if not data or "servers" not in data:
                    break

                servers = data.get("servers", [])
                if not servers:
                    break

                with sqlite3.connect(str(self.db_path)) as conn:
                    for item in servers:
                        if not isinstance(item, dict):
                            continue
                        srv = item.get("server", {})
                        meta = item.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {})

                        # Enforce Ingestion Filters
                        status = meta.get("status", "active")
                        if status and status != "active":
                            continue

                        sid = srv.get("name")
                        if not sid:
                            continue

                        is_latest = meta.get("isLatest", True)
                        updated_at = meta.get("updatedAt", now_iso)
                        raw_json_str = json.dumps(item)

                        conn.execute(
                            """
                            INSERT OR REPLACE INTO marketplace_cache
                            (id, raw_json, is_latest, status, updated_at, synced_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (sid, raw_json_str, 1 if is_latest else 0, status, updated_at, now_iso),
                        )
                        fetched_records.append(item)

                    conn.commit()

                metadata = data.get("metadata", {})
                next_cursor = metadata.get("nextCursor")
                if not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor

        self._set_last_sync_time(now_iso)
        logger.info("Official MCP Registry fetch completed", count=len(fetched_records))
        return fetched_records


    def get_cached_servers(self) -> List[Dict[str, Any]]:
        """Returns all active, latest cached registry server JSON entries from SQLite."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                "SELECT raw_json FROM marketplace_cache WHERE is_latest = 1 AND status = 'active'"
            )
            rows = cur.fetchall()
            results = []
            for row in rows:
                try:
                    results.append(json.loads(row[0]))
                except Exception:
                    pass
            return results

    def get_cached_server(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Returns a single cached server entry by ID."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                "SELECT raw_json FROM marketplace_cache WHERE id = ?", (server_id,)
            )
            row = cur.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except Exception:
                    pass
            return None

    async def fetch_server_versions(self, server_id: str) -> Dict[str, Any]:
        """Calls Official MCP Registry GET /v0.1/servers/{serverName}/versions to fetch available version history."""
        import urllib.parse
        encoded_name = urllib.parse.quote(server_id, safe="")
        url = f"{OFFICIAL_REGISTRY_BASE_URL}/servers/{encoded_name}/versions"
        async with httpx.AsyncClient(follow_redirects=True) as client:
            data = await self._fetch_with_backoff(client, url, {})
            return data or {"servers": []}

    async def fetch_server_version_detail(self, server_id: str, version: str) -> Optional[Dict[str, Any]]:
        """Calls Official MCP Registry GET /v0.1/servers/{serverName}/versions/{version}."""
        import urllib.parse
        encoded_name = urllib.parse.quote(server_id, safe="")
        encoded_ver = urllib.parse.quote(version, safe="")
        url = f"{OFFICIAL_REGISTRY_BASE_URL}/servers/{encoded_name}/versions/{encoded_ver}"
        async with httpx.AsyncClient(follow_redirects=True) as client:
            return await self._fetch_with_backoff(client, url, {})

    async def validate_server_json(self, server_json: Dict[str, Any]) -> Dict[str, Any]:
        """Calls Official MCP Registry POST /v0.1/validate to validate a server.json definition."""
        url = f"{OFFICIAL_REGISTRY_BASE_URL}/validate"
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                resp = await client.post(url, json=server_json, timeout=10.0)
                if resp.status_code == 200:
                    return resp.json()
                return {"valid": False, "issues": [{"type": "error", "path": "root", "message": f"Validation status {resp.status_code}: {resp.text}", "severity": "error", "reference": "validate"}]}
            except Exception as exc:
                return {"valid": False, "issues": [{"type": "network_error", "path": "root", "message": str(exc), "severity": "error", "reference": "validate"}]}

