"""MCP server tests (Phase 9)."""

import pytest
from gateway.mcp import get_tools


def test_tools_list():
    """Test that tools list has exactly 4 tools."""
    tools = get_tools()
    assert len(tools) == 4
    tool_names = [tool.name for tool in tools]
    assert "get_context" in tool_names
    assert "search_codebase" in tool_names
    assert "explain_architecture" in tool_names
    assert "validate_change" in tool_names


def test_get_context_tool_schema():
    """Test get_context tool schema has required fields."""
    tools = get_tools()
    get_context = next(t for t in tools if t.name == "get_context")
    assert "task" in get_context.inputSchema["properties"]
    assert "task" in get_context.inputSchema["required"]


def test_validate_change_tool_schema():
    """Test validate_change tool schema."""
    tools = get_tools()
    validate = next(t for t in tools if t.name == "validate_change")
    assert "diff" in validate.inputSchema["properties"]
    assert "diff" in validate.inputSchema["required"]
