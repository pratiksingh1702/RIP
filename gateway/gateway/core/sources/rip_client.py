"""RIP source client (MCP)."""

import asyncio
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
    # Enable dummy mode for testing
    DUMMY_MODE = False

    def __init__(self):
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._request_id = 0
        self.available = True

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
            self.available = False

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
            # Use dummy data for testing
            if self.DUMMY_MODE:
                result = self._get_dummy_response(query_type, query_params)
            else:
                # For now, use the CLI directly (simpler for initial implementation)
                result = await self._cli_query(query_type, query_params)
                
            latency_ms = int((time.time() - start_time) * 1000)

            return SourceResponse(
                source="rip",
                query_type=query_type,
                content=result,
                metadata={
                    "query_params": query_params,
                    "files": self._extract_file_paths(result),
                },
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
            
    def _get_dummy_response(self, query_type: str, query_params: dict[str, Any]) -> str:
        """Return dummy test data instead of real RIP CLI output."""
        dummy_responses = {
            "search": """
# Search results for "{}"

Found 5 relevant files:
- server/main.py: Contains the main application server logic
- gateway/gateway/server/main.py: Gateway server implementation
- cli/commands/serve.py: RIP serve command
- mcp/server.py: MCP server code
- tests/test_server.py: Server tests
""".format(query_params.get("query", "test")),
            
            "architecture": """
# Project Architecture

Core modules:
- server/: HTTP server
- gateway/: Context gateway
- cli/: Command-line interface
- mcp/: Model Context Protocol server
- tests/: Test suite
- rip/: RIP core functionality

Dependency graph:
server → cli → rip
gateway → rip
mcp → rip
""",
            
            "trace": """
# Call Trace

server.main:app → cli.commands.serve:serve → rip.server:run
→ gateway.core.pipeline:GatewayPipeline
→ gateway.core.classifier.engine:ClassifierEngine
→ gateway.core.planner.engine:PlannerEngine
→ gateway.core.executor.engine:ExecutorEngine
""",
            
            "impact": """
# Impact Analysis

Changes would affect:
- server/main.py (high impact)
- gateway/gateway/server/main.py (medium impact)
- tests/test_server.py (low impact)
""",
        }
        
        return dummy_responses.get(query_type, dummy_responses["search"])

    async def _cli_query(self, query_type: str, query_params: dict[str, Any]) -> str:
        """Execute a RIP CLI command."""
        args = ["run", "repo"]
        target = self._query_target(query_params)

        if query_type == "search":
            args.extend(["search", target])
            if "limit" in query_params:
                args.extend(["--limit", str(query_params["limit"])])
        elif query_type == "trace":
            args.extend(["trace", target])
        elif query_type == "impact":
            args.extend(["impact", target])
        elif query_type == "explain":
            args.extend(["explain", target])
        elif query_type == "architecture":
            args.append("architecture")
        elif query_type == "metrics":
            args.append("metrics")
        elif query_type == "onboard":
            args.append("onboard")
        else:
            # Default to search
            args.extend(["search", target])

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

    def _query_target(self, query_params: dict[str, Any]) -> str:
        """Choose the best CLI target from gateway query parameters."""
        for key in ("query", "task", "symbol", "topic", "diff"):
            value = query_params.get(key)
            if value:
                return str(value)
        files = query_params.get("files")
        if isinstance(files, list) and files:
            return " ".join(str(file) for file in files)
        return ""

    async def health_check(self) -> bool:
        """Check if RIP is available."""
        if self.DUMMY_MODE:
            self.available = True
            return True
            
        try:
            proc = await asyncio.create_subprocess_exec(
                "uv", "run", "repo", "--help",
                cwd=settings.rip_mcp_cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.wait()
            self.available = proc.returncode == 0
            return self.available
        except Exception as e:
            logger.warning("RIP health check failed", error=str(e))
            self.available = False
            return False

    def _extract_file_paths(self, text: str) -> list[str]:
        """Extract likely repository file paths from RIP CLI text."""
        import re

        patterns = [
            r"[\w./\\-]+\.(?:py|ts|tsx|js|jsx|dart|java|go|rs|md|toml|yaml|yml|json)",
            r"[A-Za-z]:\\[^\s:]+?\.(?:py|ts|tsx|js|jsx|dart|java|go|rs|md|toml|yaml|yml|json)",
        ]
        files: set[str] = set()
        for pattern in patterns:
            for match in re.findall(pattern, text):
                files.add(match.strip("`'\".,;)"))
        return sorted(files)
