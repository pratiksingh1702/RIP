"""Runtime doctor command."""

from __future__ import annotations

import asyncio
from pathlib import Path

from rich.console import Console
from rich.table import Table

from core.runtime.doctor import run_doctor

console = Console()


def doctor(repo_path: Path = Path("."), mode: str = "auto") -> None:
    result = asyncio.run(run_doctor(repo_path.resolve(), mode=mode))
    runtime = result["runtime"]
    console.print("[bold cyan]RIP Doctor[/bold cyan]")
    console.print(f"Python: {result['python']}")
    console.print(f"Runtime mode: {runtime['mode']}")
    console.print(f"Storage: {runtime['graph']} + {runtime['vector']} + {runtime['metadata']}")
    console.print(f"Root venv: {'yes' if result['using_root_venv'] else 'no'}")
    console.print(f"Local storage: {result['local_storage']}")

    table = Table(title="Capabilities")
    table.add_column("Capability")
    for cap in runtime["capabilities"]:
        table.add_row(str(cap))
    console.print(table)

    for item in result["recommendations"]:
        console.print(f"[yellow]{item}[/yellow]")
