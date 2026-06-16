"""Dead code command."""

from __future__ import annotations

import asyncio
import json

from rich.console import Console
from rich.table import Table

from core.analysis.dead_code_detector import DeadCodeDetector
from core.graph.client import Neo4jClient
from server.config import get_settings

console = Console()


def dead_code(
    entity_type: str = "all",
    output_format: str = "text",
) -> None:
    """Find unused classes, functions, or files."""
    asyncio.run(_dead_code(entity_type=entity_type, output_format=output_format))


async def _dead_code(entity_type: str, output_format: str) -> None:
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        detector = DeadCodeDetector(client)
        unused = await detector.detect(entity_type=entity_type)

        if output_format == "json":
            console.print(json.dumps(unused, indent=2))
            return

        if not unused:
            console.print("[green]No dead code detected![/green]")
            return

        table = Table(title="Dead Code Detection Results")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("File Path", style="green")

        for item in unused:
            table.add_row(item["name"], item["type"], item["file_path"])

        console.print(table)
    finally:
        await client.close()
