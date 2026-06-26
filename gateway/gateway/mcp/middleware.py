"""Lightweight MCP request middleware helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

ToolHandler = Callable[[dict[str, Any]], Awaitable[str]]


async def with_logging(tool_name: str, arguments: dict[str, Any], handler: ToolHandler) -> str:
    """Run a tool handler with consistent structured logging."""
    logger.info("MCP tool request started", tool=tool_name)
    try:
        result = await handler(arguments)
        logger.info("MCP tool request completed", tool=tool_name, bytes=len(result))
        return result
    except Exception as exc:
        logger.exception("MCP tool request failed", tool=tool_name, error=str(exc))
        raise
