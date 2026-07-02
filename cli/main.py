"""RIP CLI entry point."""

import asyncio
from pathlib import Path
from typing import Annotated, Optional

import typer

from cli.output.formatters import print_not_implemented
from cli.runtime_logging import run_with_verbose_logging

app = typer.Typer(help="Repository Intelligence Platform")


@app.callback()
def main() -> None:
    """Repository Intelligence Platform command line."""


def _run_command(
    command_name: str,
    *,
    verbose: bool,
    log_root: Path | None = None,
    params: dict[str, object] | None = None,
    action,
) -> None:
    run_with_verbose_logging(
        command_name,
        verbose=verbose,
        log_root=log_root,
        params=params or {},
        action=action,
    )


@app.command("init")
def init(
    repo_path: Annotated[Path, typer.Argument(help="Repository path to initialize")] = Path("."),
    project_name: Annotated[
        str | None,
        typer.Option("--project-name", help="Project name stored in .repo-intel/config.toml"),
    ] = None,
    isolation: Annotated[
        bool,
        typer.Option("--isolation/--no-isolation", help="Enable repository isolation filters"),
    ] = True,
    qdrant_strategy: Annotated[
        str,
        typer.Option(
            "--qdrant-strategy",
            help="Qdrant isolation strategy: payload_filter or collection_per_project",
        ),
    ] = "payload_filter",
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
) -> None:
    from cli.commands.init import init as init_command

    _run_command(
        "init",
        verbose=verbose,
        log_root=repo_path,
        params={
            "repo_path": repo_path,
            "project_name": project_name,
            "isolation": isolation,
            "qdrant_strategy": qdrant_strategy,
        },
        action=lambda: init_command(
            repo_path,
            project_name=project_name,
            isolation=isolation,
            qdrant_strategy=qdrant_strategy,
        ),
    )


@app.command("index")
def index(
    repo_path: Annotated[Path, typer.Argument(help="Repository path to index")] = Path("."),
    watch: Annotated[
        bool,
        typer.Option("--watch", help="Watch files and re-index on save"),
    ] = False,
    incremental: Annotated[
        bool,
        typer.Option("--incremental", help="Index only changed files"),
    ] = False,
    smart: Annotated[
        bool,
        typer.Option("--smart", help="Index only git-changed and untracked files"),
    ] = False,
    languages: Annotated[
        str | None,
        typer.Option("--languages", help="Comma-separated languages"),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs"),
    ] = False,
    mode: Annotated[str, typer.Option("--mode", help="Runtime mode: auto, server, or local")] = "auto",
) -> None:
    from cli.commands.index import index as index_command

    index_command(
        repo_path,
        watch=watch,
        incremental=incremental,
        smart=smart,
        languages=languages,
        verbose=verbose,
        mode=mode,
    )


@app.command("git-index")
def git_index(
    git_url: Annotated[str, typer.Argument(help="Git repository URL to clone and index")],
    folder_name: Annotated[
        str,
        typer.Option(
            "--folder-name",
            prompt=True,
            help="Single folder name to clone into under the configured git repositories root",
        ),
    ],
    project_name: Annotated[
        str | None,
        typer.Option("--project-name", help="Project name shown in RIP"),
    ] = None,
    subdirectory: Annotated[
        str | None,
        typer.Option("--subdir", help="Repository subfolder to initialize and index, for example lib"),
    ] = None,
    branch: Annotated[
        str,
        typer.Option("--branch", help="Git branch to clone"),
    ] = "main",
    keep_clone: Annotated[
        bool,
        typer.Option("--keep-clone/--remove-clone", help="Keep cloned source folder after indexing"),
    ] = True,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs"),
    ] = False,
) -> None:
    from core.git.cloner import CloneStatus, get_clone_service

    def action() -> None:
        name = project_name or _project_name_from_git_url(git_url)
        job = asyncio.run(
            get_clone_service().run_clone_and_index(
                git_url=git_url,
                project_name=name,
                folder_name=folder_name,
                subdirectory=subdirectory,
                branch=branch,
                keep_clone=keep_clone,
            )
        )
        if job.status == CloneStatus.FAILED:
            raise typer.BadParameter(job.error or "Git index failed")
        typer.echo(
            f"Indexed {job.files_indexed} files and {job.entities_found} entities "
            f"for {job.project_name} ({job.project_id})"
        )

    _run_command(
        "git-index",
        verbose=verbose,
        params={
            "git_url": git_url,
            "folder_name": folder_name,
            "project_name": project_name,
            "subdirectory": subdirectory,
            "branch": branch,
            "keep_clone": keep_clone,
        },
        action=action,
    )


def _project_name_from_git_url(git_url: str) -> str:
    name = git_url.rstrip("/").split("/")[-1]
    return name[:-4] if name.endswith(".git") else name


@app.command("trace")
def trace(
    entry_point: Annotated[str, typer.Argument(help="Function or symbol to trace")],
    depth: Annotated[int, typer.Option("--depth", help="Trace depth")] = 10,
    output_format: Annotated[str, typer.Option("--format", help="text or json")] = "text",
    project: Annotated[str | None, typer.Option("--project", help="Project id override")] = None,
    explain: Annotated[
        bool,
        typer.Option("--explain", help="Generate an explanation for the call path"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
    mode: Annotated[str, typer.Option("--mode", help="Runtime mode: auto, server, or local")] = "auto",
) -> None:
    from cli.commands.trace import trace as trace_command

    _run_command(
        "trace",
        verbose=verbose,
        params={
            "entry_point": entry_point,
            "depth": depth,
            "output_format": output_format,
            "project": project,
            "explain": explain,
            "mode": mode,
        },
        action=lambda: trace_command(
            entry_point,
            depth=depth,
            output_format=output_format,
            explain=explain,
            project=project,
            mode=mode,
        ),
    )


@app.command("impact")
def impact(
    symbol: Annotated[str, typer.Argument(help="Symbol or file to analyse")],
    output_format: Annotated[str, typer.Option("--format", help="text or json")] = "text",
    project: Annotated[str | None, typer.Option("--project", help="Project id override")] = None,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
    mode: Annotated[str, typer.Option("--mode", help="Runtime mode: auto, server, or local")] = "auto",
) -> None:
    from cli.commands.impact import impact as impact_command

    _run_command(
        "impact",
        verbose=verbose,
        params={"symbol": symbol, "output_format": output_format, "project": project, "mode": mode},
        action=lambda: impact_command(symbol, output_format=output_format, project=project, mode=mode),
    )


@app.command("dependencies")
def dependencies(
    target: Annotated[str, typer.Argument(help="File path or file name to inspect")],
    output_format: Annotated[str, typer.Option("--format", help="text or json")] = "text",
    project: Annotated[str | None, typer.Option("--project", help="Project id override")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum rows per section")] = 25,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
    mode: Annotated[str, typer.Option("--mode", help="Runtime mode: auto, server, or local")] = "auto",
) -> None:
    from cli.commands.dependencies import dependencies as dependencies_command

    _run_command(
        "dependencies",
        verbose=verbose,
        params={
            "target": target,
            "output_format": output_format,
            "project": project,
            "limit": limit,
            "mode": mode,
        },
        action=lambda: dependencies_command(
            target, output_format=output_format, project=project, limit=limit, mode=mode
        ),
    )


@app.command("explain")
def explain(
    symbol: Annotated[str, typer.Argument(help="What to explain (symbol or natural language query)")],
    context_level: Annotated[
        str,
        typer.Option("--level", help="Context scope"),
    ] = "file",
    provider: Annotated[
        str | None,
        typer.Option(
            "--provider",
            help="LLM provider to use (e.g., google, openrouter, openai, anthropic, ollama)",
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="LLM model to use (e.g., gemini-2.5-flash, deepseek/deepseek-chat)",
        ),
    ] = None,
    project: Annotated[str | None, typer.Option("--project", help="Project id override")] = None,
    diagram: Annotated[
        bool,
        typer.Option("--diagram", "-d", help="Show Mermaid diagram"),
    ] = False,
    tree: Annotated[
        bool,
        typer.Option("--tree", "-t", help="Show Rich tree view"),
    ] = False,
    dependencies: Annotated[
        bool,
        typer.Option("--deps", help="Show dependency table"),
    ] = False,
    code: Annotated[
        bool,
        typer.Option("--code", help="Show relevant indexed code snippets"),
    ] = False,
    no_llm: Annotated[
        bool,
        typer.Option("--no-llm", help="Skip LLM, show graph analysis only"),
    ] = False,
    max_hops: Annotated[
        int,
        typer.Option("--max-hops", help="Maximum workflow trace hops"),
    ] = 8,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
    mode: Annotated[str, typer.Option("--mode", help="Runtime mode: auto, server, or local")] = "auto",
) -> None:
    from cli.commands.explain import explain as explain_command

    _run_command(
        "explain",
        verbose=verbose,
        params={
            "symbol": symbol,
            "context_level": context_level,
            "provider": provider,
            "model": model,
            "project": project,
            "diagram": diagram,
            "tree": tree,
            "dependencies": dependencies,
            "code": code,
            "no_llm": no_llm,
            "max_hops": max_hops,
            "mode": mode,
        },
        action=lambda: explain_command(
            symbol=symbol,
            context_level=context_level,
            provider=provider,
            model=model,
            project=project,
            diagram=diagram,
            tree_view=tree,
            dependencies=dependencies,
            code=code,
            no_llm=no_llm,
            max_hops=max_hops,
            mode=mode,
        ),
    )


@app.command("search")
def search(
    query: Annotated[str, typer.Argument(help="Semantic search query")],
    limit: Annotated[int, typer.Option("--limit", help="Number of results to return")] = 20,
    language: Annotated[str | None, typer.Option("--language", help="Filter by language")] = None,
    service: Annotated[str | None, typer.Option("--service", help="Filter by service")] = None,
    entity_type: Annotated[
        str | None, typer.Option("--entity-type", help="Filter by entity type")
    ] = None,
    project: Annotated[str | None, typer.Option("--project", help="Project id override")] = None,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
    mode: Annotated[str, typer.Option("--mode", help="Runtime mode: auto, server, or local")] = "auto",
) -> None:
    from cli.commands.search import search as search_command

    _run_command(
        "search",
        verbose=verbose,
        params={
            "query": query,
            "limit": limit,
            "language": language,
            "service": service,
            "entity_type": entity_type,
            "project": project,
            "mode": mode,
        },
        action=lambda: search_command(
            query,
            limit=limit,
            language=language,
            service=service,
            entity_type=entity_type,
            project=project,
            mode=mode,
        ),
    )


@app.command("projects")
def projects(
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
) -> None:
    from cli.commands.projects import projects as projects_command

    _run_command("projects", verbose=verbose, params={}, action=projects_command)


@app.command("use")
def use(
    project_id: Annotated[str, typer.Argument(help="Project id to activate")],
    repo_path: Annotated[
        Path,
        typer.Option("--repo-path", help="Repository folder to store active project in"),
    ] = Path("."),
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
) -> None:
    from cli.commands.projects import use as use_command

    _run_command(
        "use",
        verbose=verbose,
        log_root=repo_path,
        params={"project_id": project_id, "repo_path": repo_path},
        action=lambda: use_command(project_id, repo_path=repo_path),
    )


@app.command("dead-code")
def dead_code(
    entity_type: Annotated[str, typer.Option("--type", help="functions or classes or all")] = "all",
    output_format: Annotated[str, typer.Option("--format", help="text or json")] = "text",
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
    mode: Annotated[str, typer.Option("--mode", help="Runtime mode: auto, server, or local")] = "auto",
) -> None:
    from cli.commands.dead_code import dead_code as dead_code_command

    _run_command(
        "dead-code",
        verbose=verbose,
        params={"entity_type": entity_type, "output_format": output_format, "mode": mode},
        action=lambda: dead_code_command(entity_type=entity_type, output_format=output_format, mode=mode),
    )


@app.command("onboard")
def onboard(
    output: Annotated[Path | None, typer.Option("--output", help="Save to file")] = None,
    mode: Annotated[str, typer.Option("--mode", help="Runtime mode: auto, server, or local")] = "auto",
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
) -> None:
    from cli.commands.onboard import onboard as onboard_command

    _run_command(
        "onboard",
        verbose=verbose,
        params={"output": output, "mode": mode},
        action=lambda: onboard_command(output=output, mode=mode),
    )


@app.command("architecture")
def architecture(
    output_format: Annotated[str, typer.Option("--format", help="mermaid or json")] = "mermaid",
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
    mode: Annotated[str, typer.Option("--mode", help="Runtime mode: auto, server, or local")] = "auto",
) -> None:
    from cli.commands.architecture import architecture as architecture_command

    _run_command(
        "architecture",
        verbose=verbose,
        params={"output_format": output_format, "mode": mode},
        action=lambda: architecture_command(output_format=output_format, mode=mode),
    )


@app.command("doctor")
def doctor(
    repo_path: Annotated[Path, typer.Argument(help="Repository path to diagnose")] = Path("."),
    mode: Annotated[str, typer.Option("--mode", help="Runtime mode: auto, server, or local")] = "auto",
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
) -> None:
    from cli.commands.doctor import doctor as doctor_command

    _run_command(
        "doctor",
        verbose=verbose,
        log_root=repo_path,
        params={"repo_path": repo_path, "mode": mode},
        action=lambda: doctor_command(repo_path=repo_path, mode=mode),
    )


@app.command("metrics")
def metrics(
    module: Annotated[
        str | None,
        typer.Option("--module", help="Metrics for a specific module"),
    ] = None,
    top_risk: Annotated[int | None, typer.Option("--top-risk", help="Top risk modules")] = None,
    mode: Annotated[str, typer.Option("--mode", help="Runtime mode: auto, server, or local")] = "auto",
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
) -> None:
    from cli.commands.metrics import metrics as metrics_command

    _run_command(
        "metrics",
        verbose=verbose,
        params={"module": module, "top_risk": top_risk, "mode": mode},
        action=lambda: metrics_command(module=module, top_risk=top_risk, mode=mode),
    )


@app.command("serve")
def serve(
    host: Annotated[str | None, typer.Option("--host", help="Host to bind")] = None,
    port: Annotated[int | None, typer.Option("--port", help="Port to bind")] = None,
    reload: Annotated[bool, typer.Option("--reload", help="Reload on code changes")] = False,
    mode: Annotated[str, typer.Option("--mode", help="Runtime mode: auto, server, or local")] = "server",
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
) -> None:
    from cli.commands.serve import serve as serve_command

    _run_command(
        "serve",
        verbose=verbose,
        params={"host": host, "port": port, "reload": reload, "mode": mode},
        action=lambda: serve_command(host=host, port=port, reload=reload, mode=mode),
    )


@app.command("status")
def status(
    repo_path: Annotated[
        Path,
        typer.Argument(help="Repository path to check status for"),
    ] = Path("."),
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
) -> None:
    from cli.commands.status import status as status_command

    _run_command(
        "status",
        verbose=verbose,
        log_root=repo_path,
        params={"repo_path": repo_path},
        action=lambda: status_command(repo_path=repo_path),
    )


@app.command("delete")
def delete(
    project: Annotated[
        str | None,
        typer.Option("--project", help="Delete only one project id"),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Delete without interactive confirmation"),
    ] = False,
    neo4j: Annotated[
        bool,
        typer.Option("--neo4j/--no-neo4j", help="Clear Neo4j graph data"),
    ] = True,
    qdrant: Annotated[
        bool,
        typer.Option("--qdrant/--no-qdrant", help="Delete Qdrant vector collection"),
    ] = True,
    storage: Annotated[
        bool,
        typer.Option("--storage/--no-storage", help="Reset RIP storage metadata tables"),
    ] = True,
    mode: Annotated[str, typer.Option("--mode", help="Runtime mode: server or local")] = "server",
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
) -> None:
    from cli.commands.delete import delete as delete_command

    _run_command(
        "delete",
        verbose=verbose,
        params={
            "project": project,
            "yes": yes,
            "neo4j": neo4j,
            "qdrant": qdrant,
            "storage": storage,
            "mode": mode,
        },
        action=lambda: delete_command(
            project=project, yes=yes, neo4j=neo4j, qdrant=qdrant, storage=storage, mode=mode
        ),
    )


@app.command("config")
def config(
    repo_path: Annotated[Path, typer.Argument(help="Repository path to configure")] = Path("."),
    get_key: Annotated[Optional[str], typer.Option("--get", help="Get a specific configuration value")] = None,
    set_key: Annotated[Optional[str], typer.Option("--set", help="Set a configuration value (key=value)")] = None,
    edit: Annotated[bool, typer.Option("--edit", "-e", help="Open config file in editor")] = False,
    verbose: Annotated[bool, typer.Option("-v", "--verbose", help="Show detailed output")] = False,
) -> None:
    """
    View and edit RIP configuration.
    
    Examples:
        repo config                    # Show all configuration
        repo config --get llm.primary_provider
        repo config --set llm.primary_provider=openai
        repo config --edit            # Open in editor
    """
    from cli.commands.config import config as _config_command
    
    _run_command(
        "config",
        verbose=verbose,
        log_root=repo_path,
        params={"repo_path": repo_path, "get_key": get_key, "set_key": set_key, "edit": edit},
        action=lambda: _config_command(
            repo_path=repo_path,
            get_key=get_key,
            set_key=set_key,
            edit=edit,
            verbose=verbose
        ),
    )


api_keys_app = typer.Typer(help="API Key management")
app.add_typer(api_keys_app, name="api-keys")


@api_keys_app.command("list")
def api_keys_list(
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
) -> None:
    """List all API keys."""
    from cli.commands.api_keys import list_keys
    _run_command("api-keys-list", verbose=verbose, params={}, action=list_keys)


@api_keys_app.command("create")
def api_keys_create(
    name: Annotated[str, typer.Argument(help="Human-readable name for the API key")],
    description: Annotated[
        str | None,
        typer.Option("--description", "-d", help="Optional description of the key's purpose"),
    ] = None,
    expires_in_days: Annotated[
        int | None,
        typer.Option("--expires-in", "-e", help="Optional number of days until the key expires"),
    ] = None,
    project_id: Annotated[
        str | None,
        typer.Option("--project-id", "-p", help="Optional project ID to associate with the key"),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
) -> None:
    """Create a new API key."""
    from cli.commands.api_keys import create_key
    _run_command(
        "api-keys-create",
        verbose=verbose,
        params={
            "name": name,
            "description": description,
            "expires_in_days": expires_in_days,
            "project_id": project_id,
        },
        action=lambda: create_key(name, description, expires_in_days, project_id),
    )


@api_keys_app.command("revoke")
def api_keys_revoke(
    api_key_id: Annotated[int, typer.Argument(help="ID of the API key to revoke")],
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
) -> None:
    """Revoke an API key."""
    from cli.commands.api_keys import revoke_key
    _run_command(
        "api-keys-revoke",
        verbose=verbose,
        params={"api_key_id": api_key_id},
        action=lambda: revoke_key(api_key_id),
    )


mcp_app = typer.Typer(help="MCP installation and configuration for AI agents")
app.add_typer(mcp_app, name="mcp")


@mcp_app.command("install")
def mcp_install_command(
    repo_path: Annotated[Path, typer.Option(help="Repository path to index")] = Path("."),
    agent: Annotated[str | None, typer.Option("--agent", "-a", help="Specific agent to configure (codex, claude, cursor, windsurf, aider)")] = None,
    all_agents: Annotated[bool, typer.Option("--all", help="Configure all detected agents")] = False,
    instructions_only: Annotated[bool, typer.Option("--instructions-only", help="Only update instructions files, skip MCP config")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be done without making changes")] = False,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
) -> None:
    """Install RIP MCP for AI agents (Codex, Claude, Cursor, Windsurf, Aider)."""
    from cli.commands.mcp import mcp_install

    _run_command(
        "mcp-install",
        verbose=verbose,
        log_root=repo_path,
        params={
            "repo_path": repo_path,
            "agent": agent,
            "all_agents": all_agents,
            "instructions_only": instructions_only,
            "dry_run": dry_run,
        },
        action=lambda: mcp_install(
            repo_path=repo_path,
            agent=agent,
            all_agents=all_agents,
            instructions_only=instructions_only,
            dry_run=dry_run,
        ),
    )


@mcp_app.command("status")
def mcp_status_command(
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
) -> None:
    """Show MCP installation status."""
    from cli.commands.mcp import mcp_status

    _run_command("mcp-status", verbose=verbose, params={}, action=mcp_status)


@mcp_app.command("remove")
def mcp_remove_command(
    agent: Annotated[str | None, typer.Option("--agent", "-a", help="Specific agent to remove MCP config from")] = None,
    all_agents: Annotated[bool, typer.Option("--all", help="Remove from all configured agents")] = False,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show detailed runtime logs and save a full log file"),
    ] = False,
) -> None:
    """Remove RIP MCP from AI agents."""
    from cli.commands.mcp import mcp_remove

    _run_command(
        "mcp-remove",
        verbose=verbose,
        params={"agent": agent, "all_agents": all_agents},
        action=lambda: mcp_remove(agent=agent, all_agents=all_agents),
    )
