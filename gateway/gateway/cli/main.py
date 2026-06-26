"""Typer CLI app for Context Gateway."""

import typer
import sys

from gateway.config import settings
from gateway.core.sources.registry import get_source_registry

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
    registry = get_source_registry()
    typer.echo("Context Gateway Status:")
    typer.echo(f"  Host: {settings.host}")
    typer.echo(f"  Port: {settings.port}")
    typer.echo(f"  Version: {settings.version}")
    typer.echo(f"  Debug: {settings.debug}")
    typer.echo("\nSources:")
    for name, source in registry.sources.items():
        state = "enabled" if source.is_available() else "disabled"
        health = "healthy" if registry.is_healthy(name) else "unchecked"
        typer.echo(f"  {name}: {state}, {health}")


sources_app = typer.Typer(help="Manage data sources")
app.add_typer(sources_app, name="sources")


@sources_app.command("list")
def sources_list():
    """List all configured sources."""
    registry = get_source_registry()
    typer.echo("Sources:")
    for name, source in registry.sources.items():
        marker = "X" if source.is_available() else " "
        fixed = " (always active)" if name == "rip" else ""
        typer.echo(f"  [{marker}] {name}{fixed}")


@sources_app.command("enable")
def sources_enable(source: str):
    """Enable a source for this gateway process."""
    registry = get_source_registry()
    if not registry.set_enabled(source, True):
        typer.echo(f"Cannot enable unknown or fixed source '{source}'", err=True)
        raise typer.Exit(1)
    typer.echo(f"Enabled source '{source}'")


@sources_app.command("disable")
def sources_disable(source: str):
    """Disable a source for this gateway process."""
    registry = get_source_registry()
    if not registry.set_enabled(source, False):
        typer.echo(f"Cannot disable unknown or fixed source '{source}'", err=True)
        raise typer.Exit(1)
    typer.echo(f"Disabled source '{source}'")


mcp_app = typer.Typer(help="MCP helpers")
app.add_typer(mcp_app, name="mcp")


@app.command("mcp-config")
def mcp_config():
    """Output MCP configuration for agents."""
    _print_mcp_config()


@mcp_app.command("config")
def mcp_config_group():
    """Output MCP configuration for agents."""
    _print_mcp_config()


@app.command("mcp-server")
def mcp_server():
    """Run the Context Gateway MCP stdio server."""
    import asyncio
    from gateway.mcp.server import main

    asyncio.run(main())


def _print_mcp_config():
    config = f"""
{{
  "mcpServers": {{
    "context-gateway": {{
      "command": "gateway",
      "args": ["mcp-server"],
      "env": {{
        "GATEWAY_RIP_MCP_CWD": "{settings.rip_mcp_cwd}"
      }}
    }}
  }}
}}
"""
    typer.echo(config.strip())


if __name__ == "__main__":
    app()
