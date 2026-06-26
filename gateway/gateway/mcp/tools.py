"""MCP tool definitions."""

from typing import Any

from mcp.types import Tool


def get_tools() -> list[Tool]:
    """Get list of MCP tools for Context Gateway."""
    return [
        Tool(
            name="get_context",
            description=(
                "Get complete context for a coding task. ALWAYS call this before "
                "starting any code modification. Returns ranked, compressed context "
                "from the codebase, open PRs, tickets, and team discussions. "
                "Automatically detects conflicts with other active sessions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Full description of what you need to do"},
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum context tokens to return",
                        "default": 12000
                    },
                    "role": {
                        "type": "string",
                        "description": "Agent role for permission filtering",
                        "default": "developer",
                        "enum": ["junior_dev", "developer", "senior_dev", "ci_agent"]
                    }
                },
                "required": ["task"]
            }
        ),
        Tool(
            name="validate_change",
            description=(
                "Check if a code change will break anything. Run this BEFORE "
                "applying any patch. Returns impact analysis, affected tests, "
                "downstream services at risk, and breaking change detection."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "diff": {"type": "string", "description": "The git diff or code change to validate"},
                    "files": {"type": "array", "items": {"type": "string"}, "description": "Specific files being changed"}
                },
                "required": ["diff"]
            }
        ),
        Tool(
            name="search_codebase",
            description=(
                "Semantic search across the codebase by meaning. "
                "Finds code by what it does, not just keywords. "
                "Use when you need to find where something is implemented."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 10}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="explain_architecture",
            description=(
                "Get architectural explanation with call chains and dependency maps. "
                "Use when you need to understand how a system or feature works "
                "before making changes to it."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "What to explain (service, feature, or module name)"},
                    "include_diagrams": {"type": "boolean", "description": "Include Mermaid diagrams in response", "default": True}
                },
                "required": ["topic"]
            }
        )
    ]
