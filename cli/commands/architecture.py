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
    mode: str = "auto",
) -> None:
    """Generate architecture overview."""
    asyncio.run(_architecture(output_format=output_format, mode=mode))


async def _architecture(output_format: str, mode: str = "auto") -> None:
    if mode in {"local", "auto"}:
        handled = await _architecture_runtime(output_format=output_format, mode=mode)
        if handled:
            return
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


async def _architecture_runtime(output_format: str, mode: str) -> bool:
    from pathlib import Path

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
        data = await ContextEngine(env).architecture(resolve_project_id(None))
        if output_format == "json":
            console.print(
                json.dumps(
                    {"services": data["services"], "dependencies": data["dependencies"]},
                    indent=2,
                )
            )
        else:
            console.print(data["mermaid"])
        return True
    finally:
        await env.graph.close()
        await env.vector.close()
        await env.metadata.close()
