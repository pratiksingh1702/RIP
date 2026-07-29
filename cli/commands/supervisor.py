"""CLI command for Supervisor Agent interaction and real-time oversight."""

from __future__ import annotations

import asyncclick as click
import rich
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cli.main import pass_config, Config

console = Console()


@click.group(name="supervisor", help="Interact with the Foreman Supervisor Agent.")
def supervisor_cmd():
    pass


@supervisor_cmd.command(name="chat")
@click.argument("task_id")
@click.argument("message")
@pass_config
async def supervisor_chat(config: Config, task_id: str, message: str):
    """Ask the Supervisor Agent a question or issue a retask directive."""
    client = config.get_client()
    try:
        res = await client.post("/gateway/api/supervisor/chat", json={
            "task_id": task_id,
            "message": message,
        })
        if res.status_code == 200:
            data = res.json()
            console.print(Panel(
                data.get("answer", "No response from Supervisor."),
                title=f"[bold cyan]Supervisor (Tier: {data.get('tier', 'unknown')})[/bold cyan]",
                border_style="cyan",
            ))
        else:
            console.print(f"[bold red]Error ({res.status_code}): {res.text}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Failed to reach Gateway Supervisor: {e}[/bold red]")


@supervisor_cmd.command(name="status")
@click.argument("task_id")
@pass_config
async def supervisor_status(config: Config, task_id: str):
    """Inspect active task status, step progress, and event history."""
    client = config.get_client()
    try:
        res = await client.get(f"/gateway/api/supervisor/status/{task_id}")
        if res.status_code == 200:
            data = res.json()
            progress = data.get("progress", {})
            events = data.get("events", [])

            table = Table(title=f"Task Progress ({task_id})", show_header=True)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="magenta")

            table.add_row("Query", progress.get("original_query", "N/A"))
            table.add_row("Status", progress.get("status", "N/A"))
            table.add_row("Active Step", str(progress.get("current_step_id", "None")))
            table.add_row("Git Branch", progress.get("git_branch", "main"))
            table.add_row("Files Changed", ", ".join(progress.get("files_changed", [])) or "None")

            console.print(table)
            console.print(f"\n[bold yellow]Recent Log Events ({len(events)}):[/bold yellow]")
            for ev in events[-5:]:
                console.print(f"  • [{ev.get('timestamp')[:19]}] {ev.get('event_type')}: {ev.get('data')}")
        else:
            console.print(f"[bold red]Task `{task_id}` not found ({res.status_code}).[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Failed to fetch status: {e}[/bold red]")


@supervisor_cmd.command(name="signal")
@click.argument("task_id")
@click.argument("signal_type", type=click.Choice(["pause", "resume", "abort"]))
@pass_config
async def supervisor_signal(config: Config, task_id: str, signal_type: str):
    """Send control signals (pause, resume, abort) to the Main Agent."""
    client = config.get_client()
    try:
        res = await client.post("/gateway/api/supervisor/signal", json={
            "task_id": task_id,
            "signal_type": signal_type,
        })
        if res.status_code == 200:
            console.print(f"[bold green]Signal `{signal_type.upper()}` sent successfully to task `{task_id}`![/bold green]")
        else:
            console.print(f"[bold red]Signal failed ({res.status_code}): {res.text}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Failed to transmit signal: {e}[/bold red]")
