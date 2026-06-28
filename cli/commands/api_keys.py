"""API Key management CLI commands."""

from __future__ import annotations

import asyncio
from typing import Annotated

from rich.console import Console
from rich.table import Table

from core.api_keys import create_api_key, list_api_keys, revoke_api_key
from core.storage.database import async_session_factory, ensure_storage_schema

console = Console()


async def _list_api_keys():
    """List all API keys."""
    await ensure_storage_schema()
    async with async_session_factory() as session:
        api_keys = await list_api_keys(session)
        
        if not api_keys:
            console.print("[yellow]No API keys found.[/yellow]")
            return
        
        table = Table(title="API Keys")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Prefix", style="green")
        table.add_column("Active", style="yellow")
        table.add_column("Expires At", style="blue")
        table.add_column("Last Used", style="blue")
        table.add_column("Created At", style="blue")
        table.add_column("Description", style="dim")
        
        for key in api_keys:
            table.add_row(
                str(key.id),
                key.name,
                key.prefix,
                "Yes" if key.is_active else "No",
                key.expires_at.strftime("%Y-%m-%d %H:%M") if key.expires_at else "-",
                key.last_used_at.strftime("%Y-%m-%d %H:%M") if key.last_used_at else "-",
                key.created_at.strftime("%Y-%m-%d %H:%M"),
                key.description or "-",
            )
        
        console.print(table)


def list_keys():
    """List all API keys."""
    asyncio.run(_list_api_keys())


async def _create_api_key(name: str, description: str | None, expires_in_days: int | None):
    """Create a new API key."""
    await ensure_storage_schema()
    async with async_session_factory() as session:
        plaintext_key, api_key = await create_api_key(
            session,
            name=name,
            description=description,
            expires_in_days=expires_in_days,
        )
        
        console.print("\n[green]API Key Created Successfully![/green]\n")
        console.print(f"[bold]Name:[/bold] {api_key.name}")
        console.print(f"[bold]Prefix:[/bold] {api_key.prefix}")
        if description:
            console.print(f"[bold]Description:[/bold] {description}")
        if expires_in_days:
            console.print(f"[bold]Expires in:[/bold] {expires_in_days} days")
        
        console.print("\n[bold red]IMPORTANT: Save this key now - it won't be shown again![/bold red]")
        console.print(f"\n[bold cyan]{plaintext_key}[/bold cyan]\n")


def create_key(
    name: str,
    description: str | None,
    expires_in_days: int | None,
):
    """Create a new API key."""
    asyncio.run(_create_api_key(name, description, expires_in_days))


async def _revoke_api_key(api_key_id: int):
    """Revoke an API key."""
    await ensure_storage_schema()
    async with async_session_factory() as session:
        success = await revoke_api_key(session, api_key_id)
        
        if success:
            console.print(f"[green]API Key ID {api_key_id} revoked successfully![/green]")
        else:
            console.print(f"[red]API Key ID {api_key_id} not found.[/red]")


def revoke_key(api_key_id: int):
    """Revoke an API key."""
    asyncio.run(_revoke_api_key(api_key_id))
