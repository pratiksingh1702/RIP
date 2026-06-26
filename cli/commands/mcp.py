"""MCP installation and configuration command - auto-detects AI agents."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
logger = logging.getLogger(__name__)

# ============================================================================
# AGENT DETECTION
# ============================================================================

AGENT_CONFIGS = {
    "codex": {
        "name": "OpenAI Codex CLI",
        "config_paths": [
            # Windows
            Path.home() / ".codex" / "mcp.json",
            Path.home() / "AppData" / "Roaming" / "codex" / "mcp.json",
            # Linux/Mac
            Path.home() / ".config" / "codex" / "mcp.json",
        ],
        "instructions_file": "CODEX.md",
        "config_format": "json",
    },
    "claude": {
        "name": "Claude Desktop / Claude Code",
        "config_paths": [
            # Windows
            Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",
            # Linux/Mac
            Path.home() / ".config" / "claude" / "claude_desktop_config.json",
            # Claude Code (CLI)
            Path.home() / ".claude" / "mcp.json",
        ],
        "instructions_file": "CLAUDE.md",
        "config_format": "json",
    },
    "cursor": {
        "name": "Cursor IDE",
        "config_paths": [
            Path.home() / ".cursor" / "mcp.json",
            Path.home() / "AppData" / "Roaming" / "Cursor" / "mcp.json",
        ],
        "instructions_file": ".cursorrules",
        "config_format": "json",
    },
    "windsurf": {
        "name": "Windsurf IDE",
        "config_paths": [
            Path.home() / ".codeium" / "windsurf" / "mcp_config.json",
            Path.home() / ".windsurf" / "mcp.json",
        ],
        "instructions_file": ".windsurfrules",
        "config_format": "json",
    },
    "aider": {
        "name": "Aider AI",
        "config_paths": [
            Path.home() / ".aider" / "mcp.json",
        ],
        "instructions_file": "AIDER.md",
        "config_format": "json",
    },
}


def detect_installed_agents() -> dict[str, dict]:
    """Detect which AI agents are installed on the system."""
    detected = {}
    console.print("[bold cyan]🔍 Detecting AI agents...[/bold cyan]")
    
    for agent_id, agent_info in AGENT_CONFIGS.items():
        found_path = None
        for config_path in agent_info["config_paths"]:
            if config_path.exists():
                found_path = config_path
                break
        
        # Also check if the config directory exists (agent might be installed but not configured)
        config_dir_exists = any(p.parent.exists() for p in agent_info["config_paths"])
        
        # Check for CLI tools in PATH
        cli_installed = False
        for cli_name in [agent_id, agent_info["name"].lower().replace(" ", "")]:
            if shutil.which(cli_name):
                cli_installed = True
                break
        
        status = "✅" if found_path else ("⚠️" if (config_dir_exists or cli_installed) else "❌")
        console.print(f"  {status} {agent_info['name']}: ", end="")
        
        if found_path:
            console.print(f"[green]Configured[/green] ({found_path})")
        elif config_dir_exists:
            console.print("[yellow]Installed but not configured[/yellow]")
        elif cli_installed:
            console.print("[yellow]CLI found but no MCP config[/yellow]")
        else:
            console.print("[dim]Not detected[/dim]")
        
        if found_path or config_dir_exists or cli_installed:
            detected[agent_id] = {
                **agent_info,
                "config_path": found_path,
                "is_configured": found_path is not None,
                "is_installed": config_dir_exists or cli_installed,
            }
    
    return detected


# ============================================================================
# MCP CONFIGURATION
# ============================================================================

def generate_mcp_server_config(repo_path: Path) -> dict:
    """Generate the MCP server configuration entry."""
    rip_path = Path(__file__).resolve().parent.parent.parent
    return {
        "rip": {
            "command": "uv",
            "args": [
                "run", "python", "mcp/server.py",
                str(repo_path.resolve())
            ],
            "cwd": str(rip_path),
        }
    }


def update_json_config(config_path: Path, server_config: dict) -> bool:
    """Update or create a JSON MCP config file."""
    try:
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
        else:
            config = {}
        
        if "mcpServers" not in config:
            config["mcpServers"] = {}
        
        config["mcpServers"].update(server_config)
        
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        
        return True
    except Exception as e:
        logger.error("Failed to update %s: %s", config_path, e)
        return False


# ============================================================================
# INSTRUCTIONS GENERATION
# ============================================================================

MCP_INSTRUCTIONS_TEMPLATE = """# Repository Intelligence Platform (RIP) - AI Agent Instructions

> Auto-generated by `repo mcp install`. Last updated: {timestamp}

## MCP Tools Available

This repository is indexed with RIP. The following MCP tools are available:

| Tool | Use When | Example |
|------|----------|---------|
| `repo_search` | Finding, locating, or searching for code | "Find authentication logic" |
| `repo_explain` | Explaining how something works | "How does login work?" |
| `repo_impact` | Checking what depends on something | "What breaks if I change UserService?" |
| `repo_trace` | Tracing call chains | "Trace the login flow" |
| `repo_architecture` | Understanding project structure | "Show me the architecture" |
| `repo_onboard` | Getting project overview | "What is this project about?" |

## Tool Preference Rules

1. **For repository understanding tasks**, use RIP MCP tools FIRST before raw file reads or shell commands.
2. **For "how does X work" questions**, call `repo_explain` with `no_llm=true` for instant graph analysis.
3. **For finding code**, call `repo_search` before using `rg` or `grep`.
4. **For impact analysis**, call `repo_impact` before manually tracing dependencies.
5. Use shell commands (`rg`, `cat`, `Get-Content`) only for:
   - Verifying exact line numbers
   - Reading small file slices (<50 lines)
   - Running tests or build commands
   - Tasks not related to code understanding

## Repository Context

- **Indexed path**: {repo_path}
- **Total files indexed**: {indexed_files}
- **Total entities**: {total_entities}
- **Languages**: {languages}

## Quick Commands

```bash
# Re-index the repository
repo index --verbose .

# Check indexing status
repo status

# Search the codebase
repo search "your query"

# Explain a feature
repo explain "How feature X works"
```
"""


def generate_instructions(
    repo_path: Path,
    agent_id: str,
    agent_info: dict,
    indexed_files: int = 0,
    total_entities: int = 0,
    languages: str = "dart, python",
) -> str:
    """Generate agent-specific instructions file."""
    from datetime import datetime
    
    return MCP_INSTRUCTIONS_TEMPLATE.format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        repo_path=str(repo_path.resolve()),
        indexed_files=indexed_files,
        total_entities=total_entities,
        languages=languages,
    )


def write_instructions(repo_path: Path, agent_id: str, agent_info: dict) -> bool:
    """Write instructions file for a specific agent."""
    instructions_file = agent_info.get("instructions_file", f".{agent_id}rules")
    instructions_path = repo_path / instructions_file
    
    # Get index stats if available
    indexed_files = 0
    total_entities = 0
    try:
        from core.projects import project_ref_for_root
        project_ref_for_root(repo_path)
        # Try to get stats from Neo4j
    except Exception:
        pass
    
    content = generate_instructions(
        repo_path=repo_path,
        agent_id=agent_id,
        agent_info=agent_info,
        indexed_files=indexed_files,
        total_entities=total_entities,
    )
    
    try:
        # If file exists, check if it already has RIP section
        if instructions_path.exists():
            existing = instructions_path.read_text()
            if "Repository Intelligence Platform (RIP)" in existing:
                # Replace existing RIP section
                import re
                new_content = re.sub(
                    r"# Repository Intelligence Platform.*?(?=# |\Z)",
                    content,
                    existing,
                    flags=re.DOTALL,
                )
                instructions_path.write_text(new_content)
                console.print(f"  [green]✅ Updated[/green] {instructions_path}")
                return True
        
        # Create or overwrite
        instructions_path.write_text(content)
        console.print(f"  [green]✅ Created[/green] {instructions_path}")
        return True
    except Exception as e:
        logger.error("Failed to write %s: %s", instructions_path, e)
        console.print(f"  [red]❌ Failed: {e}[/red]")
        return False


# ============================================================================
# MAIN COMMAND
# ============================================================================

def mcp_install(
    repo_path: Path = Path("."),
    agent: str | None = None,
    all_agents: bool = False,
    instructions_only: bool = False,
    dry_run: bool = False,
) -> None:
    """Install and configure RIP MCP for AI agents.
    
    Auto-detects installed AI agents (Codex, Claude, Cursor, Windsurf, Aider)
    and configures them to use RIP for repository intelligence.
    """
    repo_path = repo_path.resolve()
    
    console.print()
    console.print(Panel(
        f"[bold cyan]🔧 RIP MCP Installer[/bold cyan]\n"
        f"Repository: {repo_path}\n"
        f"RIP Path: {Path(__file__).resolve().parent.parent.parent}",
        border_style="cyan",
    ))
    console.print()
    
    # Step 1: Detect agents
    if agent:
        if agent not in AGENT_CONFIGS:
            console.print(f"[red]❌ Unknown agent: {agent}[/red]")
            console.print(f"Available agents: {', '.join(AGENT_CONFIGS.keys())}")
            return
        detected = {agent: AGENT_CONFIGS[agent]}
    else:
        detected = detect_installed_agents()
    
    if not detected:
        console.print("\n[yellow]⚠️  No AI agents detected on this system.[/yellow]")
        console.print("[dim]Install one of: Codex CLI, Claude Desktop, Cursor, Windsurf, or Aider[/dim]")
        console.print("[dim]Then run this command again.[/dim]")
        return
    
    console.print()
    
    # Step 2: Generate MCP server config
    server_config = generate_mcp_server_config(repo_path)
    
    console.print("[bold cyan]📝 MCP Server Config:[/bold cyan]")
    console.print(f"  Command: {server_config['rip']['command']}")
    console.print(f"  Args: {' '.join(server_config['rip']['args'])}")
    console.print(f"  CWD: {server_config['rip']['cwd']}")
    console.print()
    
    if dry_run:
        console.print("[yellow]🏃 Dry run - no changes will be made[/yellow]\n")
    
    # Step 3: Configure each detected agent
    results = Table(title="Configuration Results")
    results.add_column("Agent", style="cyan")
    results.add_column("MCP Config", style="green")
    results.add_column("Instructions", style="green")
    results.add_column("Status", style="yellow")
    
    for agent_id, agent_info in detected.items():
        mcp_status = "⏭️ Skipped"
        instr_status = "⏭️ Skipped"
        overall = "⚠️"
        
        if not dry_run:
            # Update MCP config
            if not instructions_only and agent_info.get("config_path"):
                config_path = agent_info["config_path"]
                # Create parent directory if needed
                config_path.parent.mkdir(parents=True, exist_ok=True)
                if update_json_config(config_path, server_config):
                    mcp_status = f"✅ {config_path}"
                else:
                    mcp_status = "❌ Failed"
            
            # Write instructions file
            if write_instructions(repo_path, agent_id, agent_info):
                instr_status = f"✅ {agent_info['instructions_file']}"
                overall = "✅ Ready"
            else:
                overall = "⚠️ Partial"
        else:
            if not instructions_only and agent_info.get("config_path"):
                mcp_status = f"Would update: {agent_info['config_path']}"
            instr_status = f"Would write: {repo_path / agent_info['instructions_file']}"
            overall = "🏃 Dry run"
        
        results.add_row(
            agent_info["name"],
            mcp_status,
            instr_status,
            overall,
        )
    
    console.print(results)
    
    # Step 4: Summary
    console.print()
    console.print("[bold green]✅ MCP Installation Complete![/bold green]")
    console.print()
    console.print("[bold]Next Steps:[/bold]")
    console.print("1. Restart your AI agent (Codex, Claude, Cursor, etc.)")
    console.print("2. The agent will auto-discover RIP tools on startup")
    console.print("3. Ask questions like:")
    console.print('   - "How does login work?"')
    console.print('   - "Search for authentication logic"')
    console.print('   - "What depends on UserService?"')
    console.print('   - "Show me the architecture"')
    console.print()
    console.print("[dim]To re-index the repository: repo index --verbose .[/dim]")


def mcp_status() -> None:
    """Show MCP installation status for all agents."""
    console.print()
    console.print("[bold cyan]🔍 MCP Status[/bold cyan]")
    console.print()
    
    detected = detect_installed_agents()
    
    if not detected:
        console.print("[yellow]No AI agents detected.[/yellow]")
        console.print("[dim]Run 'repo mcp install' to configure.[/dim]")
        return
    
    console.print()
    
    table = Table(title="MCP Configuration Status")
    table.add_column("Agent", style="cyan")
    table.add_column("MCP Config", style="green")
    table.add_column("Instructions", style="green")
    table.add_column("Tools Available", style="yellow")
    
    for _agent_id, agent_info in detected.items():
        config_status = "✅" if agent_info.get("is_configured") else "❌"
        instr_file = agent_info.get("instructions_file", "N/A")
        instr_path = Path.cwd() / instr_file
        instr_status = "✅" if instr_path.exists() else "❌"
        tools_status = "✅" if agent_info.get("is_configured") else "⚠️ Needs config"
        
        table.add_row(
            agent_info["name"],
            config_status,
            instr_status,
            tools_status,
        )
    
    console.print(table)


def mcp_remove(
    agent: str | None = None,
    all_agents: bool = False,
) -> None:
    """Remove RIP MCP configuration from AI agents."""
    console.print()
    console.print("[bold yellow]🗑️  Removing RIP MCP Configuration[/bold yellow]")
    console.print()
    
    if agent:
        if agent not in AGENT_CONFIGS:
            console.print(f"[red]❌ Unknown agent: {agent}[/red]")
            return
        agents_to_remove = {agent: AGENT_CONFIGS[agent]}
    elif all_agents:
        agents_to_remove = detect_installed_agents()
    else:
        agents_to_remove = detect_installed_agents()
    
    for _agent_id, agent_info in agents_to_remove.items():
        config_path = agent_info.get("config_path")
        if config_path and config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                if "mcpServers" in config and "rip" in config["mcpServers"]:
                    del config["mcpServers"]["rip"]
                    with open(config_path, "w") as f:
                        json.dump(config, f, indent=2)
                    console.print(f"  [green]✅ Removed from {agent_info['name']}[/green]")
            except Exception as e:
                console.print(f"  [red]❌ Failed: {e}[/red]")
        
        # Remove instructions file
        instr_path = Path.cwd() / agent_info.get("instructions_file", "")
        if instr_path.exists():
            instr_path.unlink()
            console.print(f"  [green]✅ Removed {instr_path}[/green]")
    
    console.print()
    console.print("[bold green]✅ MCP Removal Complete[/bold green]")
