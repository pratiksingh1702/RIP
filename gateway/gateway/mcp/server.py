"""MCP stdio server (Phase 9)."""

import asyncio
import structlog
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

from .tools import get_tools
from .handlers import (
    handle_get_context,
    handle_search_codebase,
    handle_explain_architecture,
    handle_validate_change
)
from .middleware import with_logging

logger = structlog.get_logger(__name__)


async def main():
    """Run the MCP server."""
    server = Server("context-gateway")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        logger.info("Listing tools")
        return get_tools()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> str:
        """Call a tool."""
        logger.info("Calling tool", tool_name=name, arguments=arguments)

        if name == "get_context":
            return await with_logging(name, arguments, handle_get_context)
        elif name == "search_codebase":
            return await with_logging(name, arguments, handle_search_codebase)
        elif name == "explain_architecture":
            return await with_logging(name, arguments, handle_explain_architecture)
        elif name == "validate_change":
            return await with_logging(name, arguments, handle_validate_change)
        else:
            raise ValueError(f"Unknown tool: {name}")

    async with stdio_server() as (read_stream, write_stream):
        logger.info("Starting MCP server")
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
