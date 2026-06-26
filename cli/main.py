"""RIP CLI entry point."""

from pathlib import Path
from typing import Annotated

import typer

from cli.output.formatters import print_not_implemented

app = typer.Typer(help="Repository Intelligence Platform")


@app.callback()
def main() -> None:
    """Repository Intelligence Platform command line."""


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
) -> None:
    from cli.commands.init import init as init_command

    init_command(
        repo_path,
        project_name=project_name,
        isolation=isolation,
        qdrant_strategy=qdrant_strategy,
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
) -> None:
    from cli.commands.index import index as index_command

    index_command(
        repo_path,
        watch=watch,
        incremental=incremental,
        smart=smart,
        languages=languages,
        verbose=verbose,
    )


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
) -> None:
    from cli.commands.trace import trace as trace_command

    trace_command(
        entry_point,
        depth=depth,
        output_format=output_format,
        explain=explain,
        project=project,
    )


@app.command("impact")
def impact(
    symbol: Annotated[str, typer.Argument(help="Symbol or file to analyse")],
    output_format: Annotated[str, typer.Option("--format", help="text or json")] = "text",
    project: Annotated[str | None, typer.Option("--project", help="Project id override")] = None,
) -> None:
    from cli.commands.impact import impact as impact_command

    impact_command(symbol, output_format=output_format, project=project)


@app.command("dependencies")
def dependencies(
    target: Annotated[str, typer.Argument(help="File path or file name to inspect")],
    output_format: Annotated[str, typer.Option("--format", help="text or json")] = "text",
    project: Annotated[str | None, typer.Option("--project", help="Project id override")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum rows per section")] = 25,
) -> None:
    from cli.commands.dependencies import dependencies as dependencies_command

    dependencies_command(target, output_format=output_format, project=project, limit=limit)


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
    no_llm: Annotated[
        bool,
        typer.Option("--no-llm", help="Skip LLM, show graph analysis only"),
    ] = False,
    max_hops: Annotated[
        int,
        typer.Option("--max-hops", help="Maximum workflow trace hops"),
    ] = 8,
) -> None:
    from cli.commands.explain import explain as explain_command

    explain_command(
        symbol=symbol,
        context_level=context_level,
        provider=provider,
        model=model,
        project=project,
        diagram=diagram,
        tree_view=tree,
        dependencies=dependencies,
        no_llm=no_llm,
        max_hops=max_hops,
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
) -> None:
    from cli.commands.search import search as search_command

    search_command(
        query,
        limit=limit,
        language=language,
        service=service,
        entity_type=entity_type,
        project=project,
    )


@app.command("projects")
def projects() -> None:
    from cli.commands.projects import projects as projects_command

    projects_command()


@app.command("use")
def use(
    project_id: Annotated[str, typer.Argument(help="Project id to activate")],
    repo_path: Annotated[
        Path,
        typer.Option("--repo-path", help="Repository folder to store active project in"),
    ] = Path("."),
) -> None:
    from cli.commands.projects import use as use_command

    use_command(project_id, repo_path=repo_path)


@app.command("dead-code")
def dead_code(
    entity_type: Annotated[str, typer.Option("--type", help="functions or classes or all")] = "all",
    output_format: Annotated[str, typer.Option("--format", help="text or json")] = "text",
) -> None:
    from cli.commands.dead_code import dead_code as dead_code_command

    dead_code_command(entity_type=entity_type, output_format=output_format)


@app.command("onboard")
def onboard(
    output: Annotated[Path | None, typer.Option("--output", help="Save to file")] = None,
) -> None:
    from cli.commands.onboard import onboard as onboard_command

    onboard_command(output=output)


@app.command("architecture")
def architecture(
    output_format: Annotated[str, typer.Option("--format", help="mermaid or json")] = "mermaid",
) -> None:
    from cli.commands.architecture import architecture as architecture_command

    architecture_command(output_format=output_format)


@app.command("metrics")
def metrics(
    module: Annotated[
        str | None,
        typer.Option("--module", help="Metrics for a specific module"),
    ] = None,
    top_risk: Annotated[int | None, typer.Option("--top-risk", help="Top risk modules")] = None,
) -> None:
    from cli.commands.metrics import metrics as metrics_command

    metrics_command(module=module, top_risk=top_risk)


@app.command("serve")
def serve(
    host: Annotated[str | None, typer.Option("--host", help="Host to bind")] = None,
    port: Annotated[int | None, typer.Option("--port", help="Port to bind")] = None,
    reload: Annotated[bool, typer.Option("--reload", help="Reload on code changes")] = False,
) -> None:
    from cli.commands.serve import serve as serve_command

    serve_command(host=host, port=port, reload=reload)


@app.command("status")
def status(
    repo_path: Annotated[
        Path,
        typer.Argument(help="Repository path to check status for"),
    ] = Path("."),
) -> None:
    from cli.commands.status import status as status_command

    status_command(repo_path=repo_path)


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
) -> None:
    from cli.commands.delete import delete as delete_command

    delete_command(project=project, yes=yes, neo4j=neo4j, qdrant=qdrant, storage=storage)


@app.command("config")
def config() -> None:
    print_not_implemented("repo config")


mcp_app = typer.Typer(help="MCP installation and configuration for AI agents")
app.add_typer(mcp_app, name="mcp")


@mcp_app.command("install")
def mcp_install_command(
    repo_path: Annotated[Path, typer.Option(help="Repository path to index")] = Path("."),
    agent: Annotated[str | None, typer.Option("--agent", "-a", help="Specific agent to configure (codex, claude, cursor, windsurf, aider)")] = None,
    all_agents: Annotated[bool, typer.Option("--all", help="Configure all detected agents")] = False,
    instructions_only: Annotated[bool, typer.Option("--instructions-only", help="Only update instructions files, skip MCP config")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be done without making changes")] = False,
) -> None:
    """Install RIP MCP for AI agents (Codex, Claude, Cursor, Windsurf, Aider)."""
    from cli.commands.mcp import mcp_install

    mcp_install(
        repo_path=repo_path,
        agent=agent,
        all_agents=all_agents,
        instructions_only=instructions_only,
        dry_run=dry_run,
    )


@mcp_app.command("status")
def mcp_status_command() -> None:
    """Show MCP installation status."""
    from cli.commands.mcp import mcp_status

    mcp_status()


@mcp_app.command("remove")
def mcp_remove_command(
    agent: Annotated[str | None, typer.Option("--agent", "-a", help="Specific agent to remove MCP config from")] = None,
    all_agents: Annotated[bool, typer.Option("--all", help="Remove from all configured agents")] = False,
) -> None:
    """Remove RIP MCP from AI agents."""
    from cli.commands.mcp import mcp_remove

    mcp_remove(agent=agent, all_agents=all_agents)
