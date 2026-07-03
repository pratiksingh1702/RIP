"""Generic runtime-configured MCP source."""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from gateway.config import settings
from gateway.core.sources.base import BaseSource
from gateway.core.sources.mcp_transport import (
    MCPConfigError,
    MCPProtocolError,
    UniversalMCPClient,
)
from gateway.core.sources.models import SourceResponse
from gateway.storage import source_registry as source_store
from gateway.storage.source_registry import SourceRecord

logger = structlog.get_logger(__name__)


class DynamicMCPSource(BaseSource):
    """MCP-compatible source built from registry row data."""

    def __init__(self, record: SourceRecord):
        self.record = record
        self.name = record.name
        self.available = record.enabled
        self.enabled = record.enabled
        self.transport = self._normalize_transport(record.transport)
        self.endpoint_url = (record.endpoint_url or "").rstrip("/")
        self.auth_type = record.auth_type
        self.credential = record.credential
        self.domain_hints = record.domain_hints
        self.priority_hint = record.priority_hint
        self.mcp_config = dict(record.mcp_config or {})
        self.tool_name = str(self.mcp_config.get("tool_name") or "search").strip() or "search"

    async def query(self, query_type: str, query_params: dict[str, Any]) -> SourceResponse:
        """Query an MCP server through Gateway-owned transports."""
        start = time.time()
        logger.info(
            "Starting dynamic MCP source query",
            source=self.name,
            source_id=self.record.id,
            transport=self.transport,
            endpoint_url=self.endpoint_url,
            tool_name=self.tool_name,
            query_type=query_type,
        )
        if not self.enabled:
            return self._error(query_type, "Source is disabled", start)

        try:
            client = self._client()
            arguments = self._tool_arguments(query_type, query_params)
            result = await client.call_tool(self.tool_name, arguments)
            self.available = True
            content = result.content
            return SourceResponse(
                source=self.name,
                query_type=query_type,
                content=content,
                metadata={
                    "source_id": self.record.id,
                    "transport": self.transport,
                    "tool_name": self.tool_name,
                    "domain_hints": self.domain_hints,
                    "raw_result": result.raw_result,
                },
                token_count=len(content.split()),
                latency_ms=self._latency(start),
                success=True,
            )
        except PermissionError as exc:
            self.available = False
            return self._error(query_type, str(exc), start)
        except (MCPConfigError, MCPProtocolError) as exc:
            self.available = False
            return self._error(query_type, str(exc), start)
        except httpx.TimeoutException as exc:
            self.available = False
            return self._error(query_type, f"MCP server timed out: {exc}", start)
        except Exception as exc:
            logger.warning(
                "Dynamic MCP source query failed",
                source=self.name,
                error=str(exc),
                traceback=True,
            )
            self.available = False
            return self._error(query_type, str(exc), start)

    async def health_check(self) -> bool:
        """Attempt an MCP initialize/tools-list handshake."""
        status = await self.test_connection()
        self.available = status == "ok"
        return self.available

    async def test_connection(self) -> str:
        """Return the mobile-facing connection result."""
        logger.info(
            "Testing dynamic MCP source connection",
            source=self.name,
            source_id=self.record.id,
            transport=self.transport,
            endpoint_url=self.endpoint_url,
        )
        try:
            handshake = await self._client().handshake()
            tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
                for tool in handshake.tools
            ]
            tool_names = {tool["name"] for tool in tools}
            if self.tool_name not in tool_names:
                await self._persist_status(
                    "no_usable_tool",
                    {
                        "capabilities": {"tools": tools, "server_info": handshake.server_info},
                        "last_test_status": "no_usable_tool",
                    },
                )
                return "no_usable_tool"
            await self._persist_status(
                "ok",
                {
                    "capabilities": {"tools": tools, "server_info": handshake.server_info},
                    "last_test_status": "ok",
                },
            )
            return "ok"
        except PermissionError:
            await self._persist_status("auth_failed", {"last_test_status": "auth_failed"})
            return "auth_failed"
        except httpx.TimeoutException:
            await self._persist_status("timeout", {"last_test_status": "timeout"})
            return "timeout"
        except MCPConfigError as exc:
            logger.warning("MCP source config invalid", source=self.name, error=str(exc))
            await self._persist_status("unreachable", {"last_test_status": "unreachable"})
            return "unreachable"
        except MCPProtocolError as exc:
            logger.warning("MCP protocol error", source=self.name, error=str(exc))
            await self._persist_status("protocol_error", {"last_test_status": "protocol_error"})
            return "protocol_error"
        except Exception as exc:
            logger.warning("MCP source test failed", source=self.name, error=str(exc), traceback=True)
            await self._persist_status("unreachable", {"last_test_status": "unreachable"})
            return "unreachable"

    def _client(self) -> UniversalMCPClient:
        return UniversalMCPClient(
            transport=self.transport,
            endpoint_url=self.endpoint_url,
            headers=self._headers(),
            mcp_config=self.mcp_config,
            timeout_seconds=settings.source_timeout_seconds,
        )

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.credential and self.auth_type in {"bearer", "token", "oauth", "oauth2"}:
            headers["Authorization"] = f"Bearer {self.credential}"
        elif self.credential and self.auth_type == "api_key":
            headers["X-API-Key"] = self.credential
        return headers

    def _tool_arguments(self, query_type: str, query_params: dict[str, Any]) -> dict[str, Any]:
        template = self.mcp_config.get("tool_arguments_template")
        if isinstance(template, dict) and template:
            return {
                key: self._render_template_value(value, query_type, query_params)
                for key, value in template.items()
            }
        return {
            "task": query_params.get("task") or query_params.get("query") or "",
            "query": query_params.get("query") or query_params.get("task") or "",
            "limit": query_params.get("limit", 10),
            "source_id": self.record.id,
            "domain_hints": self.domain_hints,
        }

    def _render_template_value(self, value: Any, query_type: str, query_params: dict[str, Any]) -> Any:
        if isinstance(value, str):
            replacements = {
                "{task}": str(query_params.get("task") or ""),
                "{query}": str(query_params.get("query") or query_params.get("task") or ""),
                "{query_type}": query_type,
                "{source_id}": self.record.id,
            }
            for placeholder, replacement in replacements.items():
                value = value.replace(placeholder, replacement)
        return value

    async def _persist_status(self, status: str, mcp_updates: dict[str, Any]) -> None:
        try:
            merged = dict(self.mcp_config)
            merged.update(mcp_updates)
            await source_store.update_source(
                self.record.id,
                {"health_status": status, "mcp_config": merged},
            )
        except Exception:
            logger.debug("Could not persist MCP source status", source=self.name, exc_info=True)

    def _error(self, query_type: str, message: str, start: float) -> SourceResponse:
        return SourceResponse(
            source=self.name,
            query_type=query_type,
            content="",
            metadata={
                "source_id": self.record.id,
                "transport": self.transport,
                "tool_name": self.tool_name,
            },
            token_count=0,
            latency_ms=self._latency(start),
            success=False,
            error=message,
        )

    def _latency(self, start: float) -> int:
        return int((time.time() - start) * 1000)

    def _normalize_transport(self, transport: str) -> str:
        value = (transport or "streamable_http").lower()
        if value == "http":
            return "streamable_http"
        return value
