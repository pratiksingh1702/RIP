"""Project selection commands."""

from __future__ import annotations

import asyncio
from pathlib import Path

from rich.console import Console
from rich.table import Table
from sqlalchemy.exc import SQLAlchemyError

from core.projects import (
    ProjectRef,
    get_project,
    list_projects,
    project_ref_for_root,
    write_active_project,
)
from core.storage.database import async_session_factory

console = Console()
METADATA_TIMEOUT_SECONDS = 5


def projects() -> None:
    asyncio.run(_projects())


async def _projects() -> None:
    try:
        refs = await asyncio.wait_for(_list_projects_from_storage(), METADATA_TIMEOUT_SECONDS)
    except (SQLAlchemyError, TimeoutError) as exc:
        console.print(
            "[yellow]Project metadata tables are not available yet.[/yellow]\n"
            "Run database migrations, or use a project id from `.repo-intel/config.toml` "
            "with `repo use <project_id>`.\n"
            f"[dim]{exc}[/dim]"
        )
        return
    refs = _with_local_project(refs)
    table = Table(title="Indexed Projects")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Language", style="magenta")
    table.add_column("Root", style="white")
    for ref in refs:
        table.add_row(ref.id, ref.name, ref.language, ref.root)
    console.print(table)


def _with_local_project(refs: list[ProjectRef]) -> list[ProjectRef]:
    if refs:
        return refs
    local = project_ref_for_root(Path.cwd())
    config_path = Path.cwd().resolve() / ".repo-intel" / "config.toml"
    if config_path.exists():
        return [*refs, local]
    return refs


async def _list_projects_from_storage():
    from core.storage.database import ensure_storage_schema

    await ensure_storage_schema()
    async with async_session_factory() as session:
        return await list_projects(session)


def use(project_id: str, repo_path: Path = Path(".")) -> None:
    asyncio.run(_use(project_id, repo_path))


async def _use(project_id: str, repo_path: Path) -> None:
    try:
        ref = await asyncio.wait_for(
            _get_project_from_storage(project_id),
            METADATA_TIMEOUT_SECONDS,
        )
    except (SQLAlchemyError, TimeoutError):
        ref = None
        console.print(
            "[yellow]Project metadata tables are not available; "
            "storing the requested project id without validation.[/yellow]"
        )
    if ref is None:
        path = write_active_project(project_id, repo_path)
        console.print(f"[green]Active project set:[/green] {project_id}")
        console.print(f"[dim]Stored in {path}[/dim]")
        return
    path = write_active_project(project_id, repo_path)
    console.print(f"[green]Active project set:[/green] {ref.name} ({project_id})")
    console.print(f"[dim]Stored in {path}[/dim]")


async def _get_project_from_storage(project_id: str):
    from core.storage.database import ensure_storage_schema

    await ensure_storage_schema()
    async with async_session_factory() as session:
        return await get_project(session, project_id)
