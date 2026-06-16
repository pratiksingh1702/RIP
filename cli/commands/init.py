"""Initialize RIP configuration."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from server.config import default_config_toml

console = Console()


def init(repo_path: Path = Path(".")) -> None:
    target = repo_path.resolve()
    config_dir = target / ".repo-intel"
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "config.toml"
    if not config_path.exists():
        config_path.write_text(default_config_toml(target), encoding="utf-8")
    console.print(f"[green]Initialized RIP config:[/green] {config_path}")
