"""Architecture command."""

from __future__ import annotations

import asyncio
import json

from rich.console import Console

from core.analysis.architecture_generator import ArchitectureGenerator
from core.graph.client import Neo4jClient
from server.config import get_settings

console = Console()


def architecture(
    output_format: str = "mermaid",
) -> None:
    """Generate architecture overview."""
    asyncio.run(_architecture(output_format=output_format))


async def _architecture(output_format: str) -> None:
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        generator = ArchitectureGenerator(client)
        data = await generator.generate()

        if output_format == "json":
            console.print(
                json.dumps(
                    {
                        "services": data["services"],
                        "dependencies": data["dependencies"],
                    },
                    indent=2,
                )
            )
        else:
            console.print(data["mermaid"])
    finally:
        await client.close()
