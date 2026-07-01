"""File-level dependency view command."""

from __future__ import annotations

import asyncio
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

from cli.output.formatters import print_json
from core.graph.client import Neo4jClient
from core.graph.queries.dependencies import file_dependencies
from core.projects import resolve_project_id
from server.config import get_settings

console = Console()


def dependencies(
    target: str,
    output_format: str = "text",
    project: str | None = None,
    limit: int = 25,
    mode: str = "auto",
) -> None:
    """Show file-level imports, dependencies, and contained symbols."""
    result = asyncio.run(_dependencies(target, project=project, limit=limit, mode=mode))
    if output_format == "json":
        print_json(result)
        return
    _print_dependency_view(result, limit=limit)


async def _dependencies(
    target: str, project: str | None = None, limit: int = 25, mode: str = "auto"
) -> dict:
    if mode in {"local", "auto"}:
        local_result = await _dependencies_runtime(target, project=project, limit=limit, mode=mode)
        if local_result is not None:
            return local_result
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        return await file_dependencies(
            client,
            target,
            project_id=resolve_project_id(project),
            limit=limit,
        )
    finally:
        await client.close()


async def _dependencies_runtime(
    target: str, project: str | None, limit: int, mode: str
) -> dict | None:
    from core.engine import ContextEngine
    from core.runtime.resolver import StorageResolver

    env = await StorageResolver(Path.cwd(), mode=mode).resolve()
    if mode == "auto" and env.mode.value != "local":
        await env.graph.close()
        await env.vector.close()
        await env.metadata.close()
        return None
    try:
        project_id = resolve_project_id(project)
        rows = await ContextEngine(env).dependencies(target, project_id)
        return {
            "target": target,
            "matched_file": {"path": target},
            "imported_by": [],
            "depends_on": [
                {
                    "target": edge.target,
                    "is_external": False,
                    "relationship_type": edge.relationship_type,
                }
                for edge in rows[:limit]
            ],
            "contains": [],
        }
    finally:
        await env.graph.close()
        await env.vector.close()
        await env.metadata.close()


def _display_path(path: str | None) -> str:
    if not path:
        return ""
    return Path(path.replace("\\", "/")).name


def _symbol_kind(row: dict) -> str:
    labels = [label for label in row.get("labels", []) if label not in {"Project"}]
    return labels[-1] if labels else "Symbol"


def _add_rows(
    tree: Tree, rows: list[dict], key: str, limit: int, suffix_key: str | None = None
) -> None:
    shown = rows[:limit]
    for row in shown:
        label = _display_path(str(row.get(key) or ""))
        if suffix_key and row.get(suffix_key):
            label = f"{label} [dim](package)[/dim]"
        tree.add(label or "[dim]<unknown>[/dim]")
    if len(rows) > limit:
        tree.add(f"[dim]... ({len(rows) - limit} more)[/dim]")


def _print_dependency_view(result: dict, limit: int) -> None:
    matched = result.get("matched_file")
    if not matched:
        console.print(f"[yellow]No indexed file matched:[/yellow] {result['target']}")
        return

    file_path = str(matched["path"])
    root = Tree(f"[bold cyan]{_display_path(file_path)}[/bold cyan] [dim]{file_path}[/dim]")

    imported_by = result["imported_by"]
    incoming = root.add(f"[bold]IMPORTED BY[/bold] [dim]({len(imported_by)} files)[/dim]")
    _add_rows(incoming, imported_by, "path", limit)

    depends_on = result["depends_on"]
    outgoing = root.add(f"[bold]DEPENDS ON[/bold] [dim]({len(depends_on)} files/packages)[/dim]")
    _add_rows(outgoing, depends_on, "target", limit, suffix_key="is_external")

    contains = result["contains"]
    symbols = root.add(f"[bold]CONTAINS[/bold] [dim]({len(contains)} symbols)[/dim]")
    for row in contains[:limit]:
        kind = _symbol_kind(row)
        name = row.get("name") or row.get("fqn") or "<unknown>"
        line = row.get("line_start")
        suffix = f" [dim]line {line}[/dim]" if line else ""
        symbols.add(f"{kind}: {name}{suffix}")
    if len(contains) > limit:
        symbols.add(f"[dim]... ({len(contains) - limit} more)[/dim]")

    console.print(root)
    console.print()
    console.print(Panel(_mermaid(result), title="GRAPH VIEW", border_style="cyan"))


def _mermaid(result: dict) -> str:
    file_name = _display_path(str(result["matched_file"]["path"]))
    lines = ["```mermaid", "graph TD"]

    def node(value: str) -> str:
        cleaned = value.replace('"', "'")
        return f'"{cleaned}"'

    for row in result["imported_by"][:8]:
        source = _display_path(str(row.get("path") or ""))
        if source:
            lines.append(f"    {node(source)} -->|IMPORTS| {node(file_name)}")
    for row in result["depends_on"][:8]:
        target = _display_path(str(row.get("target") or ""))
        if target:
            lines.append(f"    {node(file_name)} -->|DEPENDS_ON| {node(target)}")
    if len(lines) == 2:
        lines.append(f"    {node(file_name)}")
    lines.append("```")
    return "\n".join(lines)
