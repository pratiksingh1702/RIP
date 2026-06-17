"""Initialize RIP configuration."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from core.projects import ensure_project, project_ref_for_root, write_active_project
from server.config import default_config_toml

console = Console()
METADATA_TIMEOUT_SECONDS = 5


def _load_toml(path: Path) -> dict:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    with open(path, "rb") as handle:
        return tomllib.load(handle)


def _write_toml(path: Path, data: dict) -> None:
    import tomli_w

    path.write_text(tomli_w.dumps(data), encoding="utf-8")


def init(
    repo_path: Path = Path("."),
    project_name: str | None = None,
    isolation: bool = True,
    qdrant_strategy: str = "payload_filter",
) -> None:
    target = repo_path.resolve()
    config_dir = target / ".repo-intel"
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "config.toml"
    if not config_path.exists():
        config_path.write_text(
            default_config_toml(
                target,
                project_name=project_name,
                isolation_enabled=isolation,
                qdrant_strategy=qdrant_strategy,
            ),
            encoding="utf-8",
        )
    elif project_name is not None or not isolation or qdrant_strategy != "payload_filter":
        config = _load_toml(config_path)
        project = config.setdefault("project", {})
        if project_name is not None:
            project["name"] = project_name
        project.setdefault("root", target.as_posix())
        isolation_config = config.setdefault("isolation", {})
        isolation_config["enabled"] = isolation
        isolation_config["qdrant_strategy"] = qdrant_strategy
        isolation_config["require_project_filter"] = True
        _write_toml(config_path, config)
    project_ref = project_ref_for_root(target)
    write_active_project(project_ref.id, target)
    _register_project_if_available(target)
    console.print(f"[green]Initialized RIP config:[/green] {config_path}")
    console.print(f"[green]Active project:[/green] {project_ref.name} ({project_ref.id})")


def _register_project_if_available(target: Path) -> None:
    import asyncio

    try:
        asyncio.run(_register_project(target))
    except Exception as exc:
        console.print(
            "[yellow]Project metadata storage is not ready; "
            "config and active project were still written locally.[/yellow]"
        )
        console.print(f"[dim]{exc}[/dim]")


async def _register_project(target: Path) -> None:
    import asyncio

    from core.storage.database import async_session_factory, ensure_storage_schema

    async def _work() -> None:
        await ensure_storage_schema()
        async with async_session_factory() as session:
            await ensure_project(session, target)

    await asyncio.wait_for(_work(), METADATA_TIMEOUT_SECONDS)
