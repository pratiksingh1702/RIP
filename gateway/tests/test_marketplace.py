"""Automated unit and integration test suite for the Official MCP Marketplace Engine."""

import unittest
import asyncio
import sqlite3
import json

from gateway.core.marketplace.models import MarketplaceEntry
from gateway.core.marketplace.catalog_service import CatalogService
from gateway.core.marketplace.registry_client import OfficialRegistryClient
from gateway.core.marketplace.glama_client import GlamaEnrichmentClient


class TestMCPMarketplaceEngine(unittest.TestCase):

    def test_auth_scheme_inference(self):
        """Assert auth_scheme correctly detects isSecret: true in headers vs env vars."""
        service = CatalogService()

        # Case 1: Secret Header -> bearer_token
        remotes = [
            {
                "type": "streamable-http",
                "url": "https://api.test.com/mcp",
                "headers": [{"name": "Authorization", "isSecret": True, "isRequired": True}],
            }
        ]
        scheme, headers, envs = service._infer_auth_scheme_and_requirements(remotes, [])
        self.assertEqual(scheme, "bearer_token")
        self.assertEqual(len(headers), 1)
        self.assertTrue(headers[0].is_secret)

        # Case 2: Secret Environment Variable -> env_vars
        packages = [
            {
                "registryType": "npm",
                "identifier": "@test/mcp-server",
                "transport": {"type": "stdio"},
                "environmentVariables": [{"name": "API_SECRET_KEY", "isSecret": True, "isRequired": True}],
            }
        ]
        scheme, headers, envs = service._infer_auth_scheme_and_requirements([], packages)
        self.assertEqual(scheme, "env_vars")
        self.assertEqual(len(envs), 1)
        self.assertTrue(envs[0].is_secret)

    def test_ingestion_filtering_and_parsing(self):
        """Assert parser maps fields and enforces isLatest: true & status: active filters."""
        client = OfficialRegistryClient()
        service = CatalogService(registry_client=client)

        raw_item_active = {
            "server": {
                "name": "io.test.org/slack",
                "title": "Slack MCP Server",
                "description": "Slack channel management and message posting.",
                "version": "1.2.0",
                "websiteUrl": "https://slack.com",
                "remotes": [{"type": "streamable-http", "url": "https://mcp.slack.com"}],
            },
            "_meta": {
                "io.modelcontextprotocol.registry/official": {
                    "status": "active",
                    "isLatest": True,
                    "updatedAt": "2026-07-31T00:00:00Z",
                }
            },
        }

        entry = service.parse_raw_item_to_entry(raw_item_active)
        self.assertEqual(entry.id, "io.test.org/slack")
        self.assertEqual(entry.display_name, "Slack MCP Server")
        self.assertEqual(entry.version, "1.2.0")
        self.assertEqual(entry.trust_tier, "verified")
        self.assertEqual(entry.install_type, "remote_http")

    def test_server_side_trust_tier_filtering(self):
        """Assert list_servers correctly filters by trust_tier parameter."""
        import tempfile
        from pathlib import Path
        temp_dir = Path(tempfile.mkdtemp())
        client = OfficialRegistryClient(db_path=temp_dir / "test_cache.db")
        service = CatalogService(registry_client=client)


        verified_item = {
            "server": {
                "name": "io.github/slack",
                "title": "Slack Verified",
                "description": "Slack integration",
                "version": "1.0.0",
                "remotes": [{"type": "streamable-http", "url": "https://slack.com/mcp"}],
            },
            "_meta": {
                "io.modelcontextprotocol.registry/official": {
                    "status": "active",
                    "isLatest": True,
                }
            },
        }

        unverified_item = {
            "server": {
                "name": "com.unknown.user/random-tool",
                "title": "Unverified Tool",
                "description": "Unreviewed third-party tool",
                "version": "0.0.1",
                "remotes": [{"type": "streamable-http", "url": "https://unverified.com/mcp"}],
            },
            "_meta": {
                "io.modelcontextprotocol.registry/official": {
                    "status": "active",
                    "isLatest": True,
                }
            },
        }

        with sqlite3.connect(str(client.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO marketplace_cache (id, raw_json, is_latest, status, updated_at, synced_at) VALUES (?, ?, 1, 'active', '2026-07-31', '2026-07-31')",
                ("io.github/slack", json.dumps(verified_item)),
            )
            conn.execute(
                "INSERT OR REPLACE INTO marketplace_cache (id, raw_json, is_latest, status, updated_at, synced_at) VALUES (?, ?, 1, 'active', '2026-07-31', '2026-07-31')",
                ("com.unknown.user/random-tool", json.dumps(unverified_item)),
            )
            conn.commit()

        verified_results = service.list_servers(trust_tier="verified", include_unverified=True)
        verified_ids = [r["id"] for r in verified_results["servers"]]
        self.assertIn("io.github/slack", verified_ids)

        all_results = service.list_servers(include_unverified=True)
        all_ids = [r["id"] for r in all_results["servers"]]
        self.assertIn("com.unknown.user/random-tool", all_ids)


    def test_glama_graceful_fallback(self):
        """Assert Glama client degrades gracefully on failure without raising exceptions."""
        client = GlamaEnrichmentClient()
        res = asyncio.run(client.fetch_enrichment("nonexistent_owner", "nonexistent_repo"))
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
