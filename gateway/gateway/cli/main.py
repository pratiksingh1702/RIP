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
from gateway.storage import source_registry as source_store

app = typer.Typer(
    name="gateway",
    help="Context Gateway for intelligent code context orchestration",
    add_completion=False,
)

sources_app = typer.Typer(help="Manage data sources")
app.add_typer(sources_app, name="sources")

oauth_app = typer.Typer(help="Authorize OAuth-protected sources")
app.add_typer(oauth_app, name="oauth")

oauth_providers_app = typer.Typer(help="Manage custom OAuth providers")
oauth_app.add_typer(oauth_providers_app, name="providers")

mcp_app = typer.Typer(help="MCP helpers")
app.add_typer(mcp_app, name="mcp")


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


@sources_app.command("list")
def sources_list():
    """List all configured sources."""
    async def _run():
        sources = await source_store.list_sources()
        typer.echo("Sources:")
        for source in sources:
            marker = "X" if source.enabled else " "
            fixed = " (always active)" if source.protected else ""
            typer.echo(f"  [{marker}] {source.name:<20} (auth: {source.auth_type}, health: {source.health_status}){fixed}")

    asyncio.run(_run())


@sources_app.command("create")
def sources_create(
    name: str,
    transport: str = typer.Option("streamable_http", help="Transport type (stdio, http, streamable_http)"),
    endpoint_url: str | None = typer.Option(None, help="Endpoint URL for HTTP/streamable_http sources"),
    auth_type: str = typer.Option("none", help="Auth type (none, bearer, api_key, oauth2)"),
    credential: str | None = typer.Option(None, help="Credential for bearer/api_key auth"),
    tool_name: str = typer.Option("search", help="MCP tool name to use"),
    domain_hints: list[str] = typer.Option([], help="Domain hints (e.g., weather, git)"),
    priority_hint: int = typer.Option(50, help="Priority hint (higher = more likely to be used)"),
):
    """Create a new custom MCP source."""
    async def _run():
        mcp_config = {"tool_name": tool_name}
        record = await source_store.create_source(
            name=name,
            transport=transport,
            endpoint_url=endpoint_url,
            auth_type=auth_type,
            credential=credential,
            mcp_config=mcp_config,
            domain_hints=domain_hints,
            priority_hint=priority_hint,
            created_by="cli",
        )
        typer.echo(f"Created source '{record.name}' (id: {record.id})")

    asyncio.run(_run())


@sources_app.command("delete")
def sources_delete(name: str):
    """Delete a custom source."""
    async def _run():
        deleted = await source_store.delete_source(name)
        if deleted:
            typer.echo(f"Deleted source '{name}'")
        else:
            typer.echo(f"Source '{name}' not found", err=True)
            raise typer.Exit(1)

    asyncio.run(_run())


@sources_app.command("enable")
def sources_enable(source: str):
    """Enable a source for this gateway process."""
    async def _run():
        record = await source_store.update_source(source, {"enabled": True})
        if record is None:
            typer.echo(f"Cannot enable unknown source '{source}'", err=True)
            raise typer.Exit(1)
        typer.echo(f"Enabled source '{source}'")

    asyncio.run(_run())


@sources_app.command("disable")
def sources_disable(source: str):
    """Disable a source for this gateway process."""
    async def _run():
        record = await source_store.update_source(source, {"enabled": False})
        if record is None:
            typer.echo(f"Cannot disable unknown source '{source}'", err=True)
            raise typer.Exit(1)
        typer.echo(f"Disabled source '{source}'")

    asyncio.run(_run())


@oauth_providers_app.command("list")
def oauth_providers_list():
    """List all OAuth providers (builtin and custom)."""
    async def _run():
        providers = await oauth_manager.list_providers()
        typer.echo("OAuth Providers:")
        seed_ids = {seed.id for seed in oauth_manager.PROVIDER_SEEDS}
        for provider in providers:
            provider_type = "builtin" if provider["id"] in seed_ids else "custom"
            status = "configured" if provider["configured"] else "not configured"
            typer.echo(f"  {provider['id']:<20} ({provider_type}, {status}) - {provider['display_name']}")

    asyncio.run(_run())


@oauth_providers_app.command("add")
def oauth_providers_add(
    provider_id: str,
    display_name: str,
    authorize_url: str,
    token_url: str,
    client_id: str,
    client_secret: str = typer.Option(..., prompt=True, hide_input=True),
    revoke_url: str | None = typer.Option(None),
    default_scopes: list[str] = typer.Option([]),
    supports_pkce: bool = typer.Option(True),
    icon_key: str = typer.Option("custom"),
    allowed_redirect_uris: list[str] = typer.Option(["riplink://oauth/callback"]),
):
    """Add a new custom OAuth provider."""
    async def _run():
        await oauth_manager.add_custom_oauth_provider(
            provider_id=provider_id,
            display_name=display_name,
            authorize_url=authorize_url,
            token_url=token_url,
            revoke_url=revoke_url,
            client_id=client_id,
            client_secret=client_secret,
            default_scopes=default_scopes,
            supports_pkce=supports_pkce,
            icon_key=icon_key,
            allowed_redirect_uris=allowed_redirect_uris,
        )
        typer.echo(f"Added OAuth provider '{provider_id}'")

    asyncio.run(_run())


@oauth_providers_app.command("update")
def oauth_providers_update(
    provider_id: str,
    display_name: str | None = typer.Option(None),
    authorize_url: str | None = typer.Option(None),
    token_url: str | None = typer.Option(None),
    client_id: str | None = typer.Option(None),
    client_secret: str | None = typer.Option(None, prompt="New client secret (leave empty to keep existing)", hide_input=True),
    revoke_url: str | None = typer.Option(None),
    default_scopes: list[str] | None = typer.Option(None),
    supports_pkce: bool | None = typer.Option(None),
    enabled: bool | None = typer.Option(None),
):
    """Update an existing OAuth provider."""
    async def _run():
        await oauth_manager.update_oauth_provider(
            provider_id=provider_id,
            display_name=display_name,
            authorize_url=authorize_url,
            token_url=token_url,
            client_id=client_id,
            client_secret=client_secret if client_secret else None,
            revoke_url=revoke_url,
            default_scopes=default_scopes,
            supports_pkce=supports_pkce,
            enabled=enabled,
        )
        typer.echo(f"Updated OAuth provider '{provider_id}'")

    asyncio.run(_run())


@oauth_providers_app.command("delete")
def oauth_providers_delete(provider_id: str):
    """Delete a custom OAuth provider."""
    async def _run():
        try:
            deleted = await oauth_manager.delete_oauth_provider(provider_id)
            if deleted:
                typer.echo(f"Deleted OAuth provider '{provider_id}'")
            else:
                typer.echo(f"OAuth provider '{provider_id}' not found", err=True)
                raise typer.Exit(1)
        except ValueError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)

    asyncio.run(_run())


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


@app.command("add")
def add_source(
    source_name: str = typer.Argument(..., help="Source to add (github, slack, jira, linear, notion, salesforce, or custom name"),
):
    """Add a builtin or custom source to the project."""
    async def _run():
        # Map common builtin sources
        builtin_sources = {
            "github": {
                "display_name": "GitHub",
                "provider_id": "github",
                "needs_oauth": True,
                "default_domain_hints": ["git", "code", "pr", "pull request", "github"],
                "priority_hint": 70,
            },
            "slack": {
                "display_name": "Slack",
                "provider_id": "slack",
                "needs_oauth": True,
                "default_domain_hints": ["slack", "chat", "message"],
                "priority_hint": 55,
            },
            "jira": {
                "display_name": "Jira",
                "provider_id": "jira",
                "needs_oauth": True,
                "default_domain_hints": ["jira", "ticket", "issue"],
                "priority_hint": 65,
            },
            "linear": {
                "display_name": "Linear",
                "provider_id": "linear",
                "needs_oauth": True,
                "default_domain_hints": ["linear", "ticket", "issue"],
                "priority_hint": 60,
            },
            "notion": {
                "display_name": "Notion",
                "provider_id": "notion",
                "needs_oauth": True,
                "default_domain_hints": ["notion", "docs", "knowledge"],
                "priority_hint": 60,
            },
            "salesforce": {
                "display_name": "Salesforce",
                "provider_id": "salesforce",
                "needs_oauth": True,
                "default_domain_hints": ["salesforce", "crm"],
                "priority_hint": 60,
            },
        }

        source_config = builtin_sources.get(source_name.lower())

        if source_config:
            # Handle builtin source with OAuth
            typer.echo(f"Setting up {source_config['display_name']}...")

            existing_source_id = None

            # For GitHub, prompt for repo and store it on the source metadata.
            if source_name.lower() == "github":
                github_repo = typer.prompt("Enter your GitHub repo (owner/repo, e.g., octocat/Hello-World)")
                existing = await source_store.get_source("github")
                if existing is None:
                    raise typer.ClickException("Built-in GitHub source could not be initialized")
                existing_source_id = existing.id
                await source_store.update_source(
                    existing.id,
                    {
                        "endpoint_url": settings.github_api_url,
                        "auth_type": "oauth2",
                        "mcp_config": {"repo": github_repo},
                        "domain_hints": source_config["default_domain_hints"],
                        "priority_hint": source_config["priority_hint"],
                        "enabled": False,
                    },
                )

            # Check if provider is configured
            providers = await oauth_manager.list_providers()
            provider = next((p for p in providers if p["id"] == source_config["provider_id"]), None)

            if not provider or not provider["configured"]:
                typer.echo(f"\n{source_config['display_name']} OAuth not configured yet.")
                typer.echo("To set it up, you need to create an OAuth app:")
                if source_config["provider_id"] == "github":
                    typer.echo("\nStep 1: Go to https://github.com/settings/developers")
                    typer.echo("Step 2: Click 'New OAuth App'")
                typer.echo("Step 3: Create an OAuth app with callback URL: http://127.0.0.1/callback")
                client_id = typer.prompt("Enter your Client ID")
                client_secret = typer.prompt("Enter your Client Secret", hide_input=True)

                # Update provider in DB
                await oauth_manager.update_oauth_provider(
                    source_config["provider_id"],
                    client_id=client_id,
                    client_secret=client_secret,
                    enabled=True,
                )
                typer.echo(f"\n{source_config['display_name']} OAuth configured.")

            # Now run OAuth browser flow
            typer.echo("\nStarting OAuth flow...")
            await _oauth_browser_flow(
                source_config["provider_id"],
                source_name=source_name,
                existing_source_id=existing_source_id,
                domain_hints=source_config["default_domain_hints"],
                priority_hint=source_config["priority_hint"],
            )

            typer.echo(f"\n{source_config['display_name']} added successfully.")

        else:
            # Handle custom source (prompt user for details
            typer.echo("Adding custom source...")
            transport = typer.prompt("Transport type (stdio/http/streamable_http)", default="streamable_http")
            endpoint_url = None
            if transport in ["http", "streamable_http"]:
                endpoint_url = typer.prompt("Endpoint URL")

            auth_type = typer.prompt("Auth type (none/bearer/api_key/oauth2)", default="none")
            credential = None
            if auth_type in ["bearer", "api_key"]:
                credential = typer.prompt("Credential", hide_input=True)

            tool_name = typer.prompt("MCP tool name", default="search")
            domain_hints_input = typer.prompt("Domain hints (comma-separated)", default="")
            domain_hints = [h.strip() for h in domain_hints_input.split(",") if h.strip()]

            await source_store.create_source(
                name=source_name,
                transport=transport,
                endpoint_url=endpoint_url,
                auth_type=auth_type,
                credential=credential,
                mcp_config={"tool_name": tool_name},
                domain_hints=domain_hints,
                created_by="cli",
            )
            typer.echo(f"\nCustom source '{source_name}' added successfully.")

    asyncio.run(_run())


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
    existing_source_id: str | None = None,
    domain_hints: list[str] | None = None,
    priority_hint: int = 50,
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
                domain_hints=domain_hints or [],
                redirect_uri=redirect_uri,
                client_type="cli",
                requested_by="cli",
                existing_source_id=existing_source_id,
            )
        typer.echo(f"Starting local callback listener on {redirect_uri} ...")
        typer.echo("Opening browser for authorization...")
        typer.echo("If your browser did not open, visit:")
        typer.echo(f"  {initiate['authorize_url']}")
        webbrowser.open(initiate['authorize_url'])
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

        # Update the source with domain hints and priority
        source_id = result.get("source_id")
        if source_id and (domain_hints or priority_hint):
            await source_store.update_source(
                source_id,
                {
                    "domain_hints": domain_hints,
                    "priority_hint": priority_hint,
                }
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
