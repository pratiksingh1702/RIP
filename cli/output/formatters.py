"""CLI output formatters."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


def print_json(data: Any) -> None:
    console.print_json(json.dumps(data, default=str))


def print_key_values(title: str, values: dict[str, Any]) -> None:
    table = Table(title=title)
    table.add_column("Key")
    table.add_column("Value")
    for key, value in values.items():
        table.add_row(str(key), str(value))
    console.print(table)


def print_not_implemented(command: str) -> None:
    console.print(f"[yellow]{command} is not implemented yet.[/yellow]")
