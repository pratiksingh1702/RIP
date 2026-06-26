"""Unit tests for CLI commands."""

import pytest
from typer.testing import CliRunner

from gateway.cli.main import app


@pytest.fixture
def runner():
    """CLI test runner fixture."""
    return CliRunner()


def test_cli_status_command(runner):
    """Test that status command runs without errors."""
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Context Gateway Status" in result.stdout


def test_cli_sources_list(runner):
    """Test that sources list command works."""
    result = runner.invoke(app, ["sources", "list"])
    assert result.exit_code == 0
    assert "rip" in result.stdout


def test_cli_mcp_config(runner):
    """Test that mcp-config command outputs config."""
    result = runner.invoke(app, ["mcp-config"])
    assert result.exit_code == 0
    assert "context-gateway" in result.stdout
