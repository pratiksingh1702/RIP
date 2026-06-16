"""RIP CLI entry point."""

from pathlib import Path
from typing import Annotated

import typer

from cli.commands.architecture import architecture as architecture_command
from cli.commands.dead_code import dead_code as dead_code_command
from cli.commands.explain import explain as explain_command
from cli.commands.impact import impact as impact_command
from cli.commands.index import index as index_command
from cli.commands.init import init as init_command
from cli.commands.metrics import metrics as metrics_command
from cli.commands.onboard import onboard as onboard_command
from cli.commands.search import search as search_command
from cli.commands.serve import serve as serve_command
from cli.commands.status import status as status_command
from cli.commands.trace import trace as trace_command
from cli.output.formatters import print_not_implemented

app = typer.Typer(help="Repository Intelligence Platform")


@app.callback()
def main() -> None:
    """Repository Intelligence Platform command line."""


@app.command("init")
def init(
    repo_path: Annotated[Path, typer.Argument(help="Repository path to initialize")] = Path("."),
) -> None:
    init_command(repo_path)


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
    languages: Annotated[
        str | None,
        typer.Option("--languages", help="Comma-separated languages"),
    ] = None,
) -> None:
    index_command(repo_path, watch=watch, incremental=incremental, languages=languages)


@app.command("trace")
def trace(
    entry_point: Annotated[str, typer.Argument(help="Function or symbol to trace")],
    depth: Annotated[int, typer.Option("--depth", help="Trace depth")] = 10,
    output_format: Annotated[str, typer.Option("--format", help="text or json")] = "text",
    explain: Annotated[
        bool,
        typer.Option("--explain", help="Generate an explanation for the call path"),
    ] = False,
) -> None:
    trace_command(entry_point, depth=depth, output_format=output_format, explain=explain)


@app.command("impact")
def impact(
    symbol: Annotated[str, typer.Argument(help="Symbol or file to analyse")],
    output_format: Annotated[str, typer.Option("--format", help="text or json")] = "text",
) -> None:
    impact_command(symbol, output_format=output_format)


@app.command("explain")
def explain(
    symbol: Annotated[str, typer.Argument(help="Symbol or file to explain")],
    context_level: Annotated[
        str,
        typer.Option("--level", help="Context level: file, class, function"),
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
) -> None:
    explain_command(symbol=symbol, context_level=context_level, provider=provider, model=model)


@app.command("search")
def search(
    query: Annotated[str, typer.Argument(help="Semantic search query")],
    limit: Annotated[int, typer.Option("--limit", help="Number of results to return")] = 20,
    language: Annotated[str | None, typer.Option("--language", help="Filter by language")] = None,
    service: Annotated[str | None, typer.Option("--service", help="Filter by service")] = None,
    entity_type: Annotated[
        str | None, typer.Option("--entity-type", help="Filter by entity type")
    ] = None,
) -> None:
    search_command(
        query,
        limit=limit,
        language=language,
        service=service,
        entity_type=entity_type,
    )


@app.command("dead-code")
def dead_code(
    entity_type: Annotated[str, typer.Option("--type", help="functions or classes or all")] = "all",
    output_format: Annotated[str, typer.Option("--format", help="text or json")] = "text",
) -> None:
    dead_code_command(entity_type=entity_type, output_format=output_format)


@app.command("onboard")
def onboard(
    output: Annotated[Path | None, typer.Option("--output", help="Save to file")] = None,
) -> None:
    onboard_command(output=output)


@app.command("architecture")
def architecture(
    output_format: Annotated[str, typer.Option("--format", help="mermaid or json")] = "mermaid",
) -> None:
    architecture_command(output_format=output_format)


@app.command("metrics")
def metrics(
    module: Annotated[
        str | None,
        typer.Option("--module", help="Metrics for a specific module"),
    ] = None,
    top_risk: Annotated[int | None, typer.Option("--top-risk", help="Top risk modules")] = None,
) -> None:
    metrics_command(module=module, top_risk=top_risk)


@app.command("serve")
def serve(
    host: Annotated[str | None, typer.Option("--host", help="Host to bind")] = None,
    port: Annotated[int | None, typer.Option("--port", help="Port to bind")] = None,
    reload: Annotated[bool, typer.Option("--reload", help="Reload on code changes")] = False,
) -> None:
    serve_command(host=host, port=port, reload=reload)


@app.command("status")
def status(
    repo_path: Annotated[
        Path,
        typer.Argument(help="Repository path to check status for"),
    ] = Path("."),
) -> None:
    status_command(repo_path=repo_path)


@app.command("config")
def config() -> None:
    print_not_implemented("repo config")
