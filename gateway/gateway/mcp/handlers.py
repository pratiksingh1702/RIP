"""MCP tool handlers."""

import structlog
from typing import Any

from gateway.core.pipeline import GatewayPipeline
from gateway.core.sources.rip_client import RIPSource

logger = structlog.get_logger(__name__)

pipeline = GatewayPipeline()


async def handle_get_context(arguments: dict[str, Any]) -> str:
    """Handle get_context tool call."""
    try:
        task = arguments["task"]
        max_tokens = arguments.get("max_tokens", 12000)
        role = arguments.get("role", "developer")

        result = await pipeline.get_context(task, max_tokens, role)

        # Format as readable text
        output = []
        output.append(f"## Context for: {task[:100]}...")
        output.append(f"Intent: {result.intent} | Domain: {result.domain}")
        output.append(f"Session ID: {result.session_id}")
        output.append(f"Tokens used: {result.tokens_used}")
        output.append("")

        if result.conflicts:
            output.append("### ⚠️ Conflicts Detected:")
            for conflict in result.conflicts:
                output.append(f"- {conflict}")
            output.append("")

        output.append("### Context Items:")
        for i, item in enumerate(result.context, 1):
            output.append(f"{i}. [{item.source}/{item.query_type}] (Score: {item.score:.2f})")
            output.append(item.content[:300])
            if len(item.content) > 300:
                output.append("...")
            output.append("")

        return "\n".join(output)

    except Exception as e:
        logger.error("Error in get_context", error=str(e))
        return f"Error retrieving context: {str(e)}"


async def handle_search_codebase(arguments: dict[str, Any]) -> str:
    """Handle search_codebase tool call."""
    try:
        query = arguments["query"]
        limit = arguments.get("limit", 10)

        # Use RIP source directly
        rip = RIPSource()
        response = await rip.query("search", {"query": query, "limit": limit})

        if response.success:
            return response.content
        else:
            return f"Search failed: {response.error}"
    except Exception as e:
        logger.error("Error in search_codebase", error=str(e))
        return f"Error searching codebase: {str(e)}"


async def handle_explain_architecture(arguments: dict[str, Any]) -> str:
    """Handle explain_architecture tool call."""
    try:
        topic = arguments["topic"]
        include_diagrams = arguments.get("include_diagrams", True)

        rip = RIPSource()
        response = await rip.query("architecture", {"topic": topic})

        if response.success:
            output = [f"## Architecture: {topic}"]
            output.append("")
            output.append(response.content)
            return "\n".join(output)
        else:
            return f"Architecture explanation failed: {response.error}"
    except Exception as e:
        logger.error("Error in explain_architecture", error=str(e))
        return f"Error explaining architecture: {str(e)}"


async def handle_validate_change(arguments: dict[str, Any]) -> str:
    """Handle validate_change tool call."""
    try:
        diff = arguments["diff"]
        files = arguments.get("files", None)

        # Use RIP impact query
        rip = RIPSource()
        response = await rip.query("impact", {"diff": diff, "files": files})

        output = ["## Change Validation"]
        if response.success:
            output.append(response.content)
        else:
            output.append(f"⚠️  Validation failed: {response.error}")

        return "\n".join(output)
    except Exception as e:
        logger.error("Error in validate_change", error=str(e))
        return f"Error validating change: {str(e)}"
