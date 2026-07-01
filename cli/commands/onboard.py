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
    mode: str = "auto",
) -> None:
    """Generate repository onboarding documentation."""
    asyncio.run(_onboard(output=output, mode=mode))


async def _onboard(output: Path | None, mode: str = "auto") -> None:
    if mode in {"local", "auto"}:
        handled = await _onboard_runtime(output=output, mode=mode)
        if handled:
            return
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


async def _onboard_runtime(output: Path | None, mode: str) -> bool:
    from core.engine import ContextEngine
    from core.projects import resolve_project_id
    from core.runtime.resolver import StorageResolver

    env = await StorageResolver(Path.cwd(), mode=mode).resolve()
    if mode == "auto" and env.mode.value != "local":
        await env.graph.close()
        await env.vector.close()
        await env.metadata.close()
        return False
    try:
        markdown = await ContextEngine(env).onboard_markdown(resolve_project_id(None))
        if output:
            output.write_text(markdown, encoding="utf-8")  # noqa: ASYNC240
            console.print(f"[green]Saved onboarding document to: {output}[/green]")
        else:
            console.print(markdown)
        return True
    finally:
        await env.graph.close()
        await env.vector.close()
        await env.metadata.close()
