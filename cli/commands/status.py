"""Status command implementation."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.graph.client import Neo4jClient
from server.config import get_settings

console = Console()


def status(
    repo_path: Annotated[
        Path,
        typer.Argument(help="Repository path to check status for"),
    ] = Path("."),
) -> None:
    repo_path = repo_path.resolve()
    asyncio.run(_status(repo_path))


async def _status(repo_path: Path) -> None:
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        await client.connect()

        file_count_result = await client.execute("MATCH (f:File) RETURN count(f) AS count")
        entity_count_result = await client.execute(
            """
            MATCH (e)
            WHERE e:Class OR e:Function OR e:Interface OR e:APIRoute OR e:DBEntity
            RETURN count(e) AS count
            """
        )
        relationship_count_result = await client.execute(
            "MATCH ()-[r]->() RETURN count(r) AS count"
        )

        file_count = file_count_result[0]["count"] if file_count_result else 0
        entity_count = entity_count_result[0]["count"] if entity_count_result else 0
        relationship_count = (
            relationship_count_result[0]["count"] if relationship_count_result else 0
        )

        table = Table(title=f"Repository Status: {repo_path}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta", justify="right")

        table.add_row("Indexed Files", str(file_count))
        table.add_row("Entities", str(entity_count))
        table.add_row("Relationships", str(relationship_count))

        console.print(Panel(table))
    finally:
        await client.close()
