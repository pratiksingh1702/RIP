"""RIP source client (MCP)."""

import asyncio
import json
import time
from typing import Any

import structlog

from gateway.config import settings
from .base import BaseSource
from .models import SourceResponse

logger = structlog.get_logger(__name__)


class RIPSource(BaseSource):
    """RIP as a source using its MCP server."""

    name = "rip"

    def __init__(self):
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._request_id = 0

    async def connect(self) -> None:
        """Connect to RIP MCP server."""
        if self._process and self._process.returncode is None:
            return

        try:
            self._process = await asyncio.create_subprocess_exec(
                settings.rip_mcp_command,
                *settings.rip_mcp_args,
                cwd=settings.rip_mcp_cwd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self._reader = self._process.stdout
            self._writer = self._process.stdin
            logger.info("RIP MCP client connected")
        except Exception as e:
            logger.error("Failed to connect to RIP MCP", error=str(e))
            self.is_available = False

    async def disconnect(self) -> None:
        """Disconnect from RIP MCP server."""
        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except Exception as e:
                logger.warning("Error disconnecting RIP MCP", error=str(e))
            finally:
                self._process = None
                self._reader = None
                self._writer = None

    async def query(self, query_type: str, query_params: dict[str, Any]) -> SourceResponse:
        """Query RIP using its CLI or MCP interface."""
        start_time = time.time()

        try:
            # For now, use the CLI directly (simpler for initial implementation)
            result = await self._cli_query(query_type, query_params)
            latency_ms = int((time.time() - start_time) * 1000)

            return SourceResponse(
                source="rip",
                query_type=query_type,
                content=result,
                metadata={"query_params": query_params},
                token_count=len(result.split()),  # rough estimate
                latency_ms=latency_ms,
                success=True
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error("RIP query failed", query_type=query_type, error=str(e))
            return SourceResponse(
                source="rip",
                query_type=query_type,
                content="",
                metadata={},
                token_count=0,
                latency_ms=latency_ms,
                success=False,
                error=str(e)
            )

    async def _cli_query(self, query_type: str, query_params: dict[str, Any]) -> str:
        """Execute a RIP CLI command."""
        args = ["run", "repo"]

        if query_type == "search":
            args.extend(["search", query_params.get("query", "")])
            if "limit" in query_params:
                args.extend(["--limit", str(query_params["limit"])])
        elif query_type == "trace":
            args.extend(["trace", query_params.get("query", "")])
        elif query_type == "impact":
            args.extend(["impact", query_params.get("query", "")])
        elif query_type == "explain":
            args.extend(["explain", query_params.get("query", "")])
        elif query_type == "architecture":
            args.append("architecture")
        elif query_type == "metrics":
            args.append("metrics")
        elif query_type == "onboard":
            args.append("onboard")
        else:
            # Default to search
            args.extend(["search", query_params.get("query", "")])

        proc = await asyncio.create_subprocess_exec(
            "uv",
            *args,
            cwd=settings.rip_mcp_cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"RIP command failed: {stderr.decode('utf-8', errors='replace')}")

        return stdout.decode('utf-8', errors='replace')

    async def health_check(self) -> bool:
        """Check if RIP is available."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "uv", "run", "repo", "--help",
                cwd=settings.rip_mcp_cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.wait()
            self.is_available = (proc.returncode == 0)
            return self.is_available
        except Exception as e:
            logger.warning("RIP health check failed", error=str(e))
            self.is_available = False
            return False
