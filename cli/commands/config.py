"""Config command for RIP CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel

from server.config import default_config_toml, get_settings

console = Console()


def config(
    repo_path: Path = Path("."),
    get_key: Optional[str] = None,
    set_key: Optional[str] = None,
    edit: bool = False,
    verbose: bool = False,
) -> None:
    """
    View and edit RIP configuration.
    
    Examples:
        repo config                    # Show all configuration
        repo config --get llm.primary_provider
        repo config --set llm.primary_provider=openai
        repo config --edit            # Open in editor
    """
    repo_intel_dir = repo_path / ".repo-intel"
    config_path = repo_intel_dir / "config.toml"

    # Ensure config directory exists
    repo_intel_dir.mkdir(exist_ok=True)

    # Create default config if it doesn't exist
    if not config_path.exists():
        project_name = repo_path.resolve().name
        config_content = default_config_toml(repo_path, project_name=project_name)
        config_path.write_text(config_content, encoding="utf-8")
        console.print(f"[green]Created default config at {config_path}[/green]")

    if edit:
        # Open config file in default editor
        import typer
        typer.launch(str(config_path))
        return

    if get_key:
        # Get specific key
        settings = get_settings()
        # Flatten settings to dictionary for easy access
        settings_dict = settings.model_dump()
        
        # Handle nested keys (like llm.primary_provider)
        keys = get_key.split(".")
        value = settings_dict
        try:
            for key in keys:
                value = value[key]
            console.print(f"[bold]{get_key}[/bold] = [cyan]{value}[/cyan]")
        except KeyError:
            console.print(f"[red]Key not found: {get_key}[/red]")
        return

    if set_key:
        # Set specific key (format: key=value)
        if "=" not in set_key:
            console.print("[red]Invalid format. Use: key=value[/red]")
            return
        
        key, value = set_key.split("=", 1)
        key = key.strip()
        value = value.strip()
        
        # Read current config
        current_config = config_path.read_text(encoding="utf-8")
        
        console.print(Panel(
            f"Would set [bold]{key}[/bold] to [cyan]{value}[/cyan]\n\n"
            f"[dim]Note: Full TOML editing requires the tomli-w package.[/dim]\n"
            f"[dim]For now, please edit the file directly with:[/dim]\n"
            f"[cyan]repo config --edit[/cyan]",
            title="Config Update",
            border_style="blue"
        ))
        return

    # Show all configuration
    console.print(Panel(
        config_path.read_text(encoding="utf-8"),
        title=f"Configuration: {config_path}",
        border_style="cyan"
    ))
    
    console.print("\n[dim]Use --get KEY to get a value, --set KEY=VALUE to set a value, or --edit to open in editor.[/dim]")
