"""Typer CLI app for Context Gateway."""

import typer
import subprocess
import sys
import os

from gateway.config import settings

app = typer.Typer(
    name="gateway",
    help="Context Gateway for intelligent code context orchestration",
    add_completion=False,
)


@app.command()
def start():
    """Start the Context Gateway HTTP server."""
    typer.echo("Starting Context Gateway server...")
    try:
        import uvicorn
        uvicorn.run(
            "gateway.server.main:app",
            host=settings.host,
            port=settings.port,
            reload=settings.debug,
        )
    except KeyboardInterrupt:
        typer.echo("\nServer stopped.")
    except Exception as e:
        typer.echo(f"Error starting server: {e}", err=True)
        sys.exit(1)


@app.command()
def status():
    """Check status of the Context Gateway."""
    typer.echo("Context Gateway Status:")
    typer.echo(f"  Host: {settings.host}")
    typer.echo(f"  Port: {settings.port}")
    typer.echo(f"  Version: {settings.version}")
    typer.echo(f"  Debug: {settings.debug}")
    typer.echo("\nSources:")
    typer.echo("  RIP: enabled (always)")
    typer.echo(f"  GitHub: {'enabled' if settings.github_mcp_enabled else 'disabled'}")
    typer.echo(f"  Jira: {'enabled' if settings.jira_mcp_enabled else 'disabled'}")
    typer.echo(f"  Slack: {'enabled' if settings.slack_mcp_enabled else 'disabled'}")


sources_app = typer.Typer(help="Manage data sources")
app.add_typer(sources_app, name="sources")


@sources_app.command("list")
def sources_list():
    """List all configured sources."""
    typer.echo("Sources:")
    typer.echo("  [X] rip (enabled, always active)")
    if settings.github_mcp_enabled:
        typer.echo("  [X] github (enabled)")
    else:
        typer.echo("  [ ] github (disabled)")
    if settings.jira_mcp_enabled:
        typer.echo("  [X] jira (enabled)")
    else:
        typer.echo("  [ ] jira (disabled)")
    if settings.slack_mcp_enabled:
        typer.echo("  [X] slack (enabled)")
    else:
        typer.echo("  [ ] slack (disabled)")


@sources_app.command("enable")
def sources_enable(source: str):
    """Enable a source (placeholder)."""
    typer.echo(f"Enabling source '{source}' (placeholder, edit config file to persist)")


@sources_app.command("disable")
def sources_disable(source: str):
    """Disable a source (placeholder)."""
    typer.echo(f"Disabling source '{source}' (placeholder, edit config file to persist)")


@app.command("mcp-config")
def mcp_config():
    """Output MCP configuration for agents."""
    config = f"""
{{
  "mcpServers": {{
    "context-gateway": {{
      "command": "python",
      "args": ["-m", "gateway.mcp.server"]
    }}
  }}
}}
"""
    typer.echo(config.strip())


if __name__ == "__main__":
    app()
