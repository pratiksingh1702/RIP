"""Onboard command."""

from __future__ import annotations

import asyncio
from pathlib import Path

from rich.console import Console

from core.analysis.onboard_engine import OnboardEngine
from core.graph.client import Neo4jClient
from server.config import get_settings

console = Console()


def onboard(
    output: Path | None = None,
) -> None:
    """Generate repository onboarding documentation."""
    asyncio.run(_onboard(output=output))


async def _onboard(output: Path | None) -> None:
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        engine = OnboardEngine(client)
        data = await engine.generate_onboarding_data()
        markdown = data["markdown"]

        if output:
            output.write_text(markdown, encoding="utf-8")  # noqa: ASYNC240
            console.print(f"[green]Saved onboarding document to: {output}[/green]")
        else:
            console.print(markdown)
    finally:
        await client.close()
