"""Typer CLI app for Context Gateway."""

import typer
import sys
import asyncio
import queue
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from gateway.config import settings
from gateway.core import oauth as oauth_manager
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

oauth_app = typer.Typer(help="Authorize OAuth-protected sources")
app.add_typer(oauth_app, name="oauth")


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


@oauth_app.command("list")
def oauth_list():
    """List OAuth providers and connected OAuth sources."""
    async def _run() -> None:
        providers = await oauth_manager.list_providers()
        from gateway.storage import source_registry as source_store

        sources = await source_store.list_sources()
        typer.echo("Providers available:")
        for provider in providers:
            status = "configured" if provider["configured"] else "operator setup required"
            typer.echo(f"  {provider['id']:<13} ({status})")
        typer.echo("\nConnected sources:")
        connected = [
            source for source in sources
            if source.auth_type == "oauth2" and source.oauth_status == "active"
        ]
        if not connected:
            typer.echo("  none")
        for source in connected:
            typer.echo(f"  {source.name:<13} {source.oauth_account_label or 'connected'}")

    asyncio.run(_run())


@oauth_app.command("setup")
def oauth_setup(provider: str, source_name: str | None = None):
    """Connect a provider via a localhost OAuth callback."""
    asyncio.run(_oauth_browser_flow(provider, source_name=source_name))


@oauth_app.command("reauthorize")
def oauth_reauthorize(source: str):
    """Re-authorize an existing OAuth source."""
    asyncio.run(_oauth_browser_flow(None, existing_source=source))


@oauth_app.command("revoke")
def oauth_revoke(source: str):
    """Disconnect and revoke an OAuth source."""
    if not typer.confirm(f"Disconnect {source}? This stops Gateway from querying it."):
        raise typer.Exit()
    async def _run() -> None:
        result = await oauth_manager.revoke_source(source, requested_by="cli")
        typer.echo(f"Disconnected: {result['source_id']}")

    asyncio.run(_run())


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


async def _oauth_browser_flow(
    provider: str | None,
    *,
    source_name: str | None = None,
    existing_source: str | None = None,
) -> None:
    port = _free_loopback_port()
    redirect_uri = f"http://127.0.0.1:{port}/callback"
    code_queue: queue.Queue[dict[str, str]] = queue.Queue(maxsize=1)
    server = _start_loopback_server(port, code_queue)
    try:
        if existing_source:
            initiate = await oauth_manager.reauthorize_source(
                existing_source,
                redirect_uri=redirect_uri,
                client_type="cli",
                requested_by="cli",
            )
        else:
            if provider is None:
                raise typer.BadParameter("provider is required")
            initiate = await oauth_manager.initiate_oauth(
                provider_id=provider,
                source_name=source_name or f"{provider}-oauth",
                domain_hints=[],
                redirect_uri=redirect_uri,
                client_type="cli",
                requested_by="cli",
            )
        typer.echo(f"Starting local callback listener on {redirect_uri} ...")
        typer.echo("Opening browser for authorization...")
        typer.echo("If your browser did not open, visit:")
        typer.echo(f"  {initiate['authorize_url']}")
        webbrowser.open(initiate["authorize_url"])
        typer.echo("\nWaiting for authorization... (this will time out in 10 minutes)")
        try:
            callback = code_queue.get(timeout=600)
        except queue.Empty as exc:
            raise typer.Exit(1) from exc
        if callback.get("error"):
            typer.echo(f"Authorization failed: {callback['error']}", err=True)
            raise typer.Exit(1)
        result = await oauth_manager.complete_callback(
            state=callback["state"],
            code=callback["code"],
            requested_by="cli",
        )
        typer.echo(f"Connected: {result['account_label']}")
    finally:
        server.shutdown()
        server.server_close()


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_loopback_server(port: int, code_queue: queue.Queue[dict[str, str]]) -> HTTPServer:
    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            payload = {
                "code": params.get("code", [""])[0],
                "state": params.get("state", [""])[0],
                "error": params.get("error", [""])[0],
            }
            if parsed.path == "/callback" and not code_queue.full():
                code_queue.put(payload)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Authorization captured. You can return to the terminal.")

        def log_message(self, format: str, *args) -> None:
            return

    server = HTTPServer(("127.0.0.1", port), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


if __name__ == "__main__":
    app()
