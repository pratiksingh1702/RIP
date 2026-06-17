"""Index repository command."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from core.graph.client import Neo4jClient
from core.indexer.incremental import incremental_index
from core.indexer.pipeline import IndexProgress, IndexPipeline
from core.parser.registry import build_default_registry
from core.storage.database import async_session_factory
from server.config import get_settings

console = Console()
logger = logging.getLogger(__name__)


def index(
    repo_path: Path = Path("."),
    watch: bool = False,
    incremental: bool = False,
    languages: str | None = None,
    verbose: bool = False,
) -> None:
    if languages and "python" not in {item.strip() for item in languages.split(",")}:
        console.print("[yellow]Only Python parsing is implemented in Phase 1.[/yellow]")
    repo_path = repo_path.resolve()
    log_path = _configure_verbose_logging(repo_path) if verbose else None
    if log_path:
        console.print(f"[dim]Verbose index log: {log_path}[/dim]")
    if watch:
        console.print(f"[cyan]Starting watch mode on {repo_path}...[/cyan]")
        _watch_mode(repo_path, verbose=verbose)
    elif incremental:
        console.print(f"[cyan]Starting incremental index on {repo_path}...[/cyan]")
        asyncio.run(_incremental_index(repo_path, verbose=verbose))
    else:
        console.print(f"[cyan]Starting full index on {repo_path}...[/cyan]")
        asyncio.run(_index(repo_path, verbose=verbose, log_path=log_path))


def _configure_verbose_logging(repo_path: Path) -> Path:
    log_dir = repo_path / ".repo-intel" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"index-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    for handler in list(root_logger.handlers):
        if getattr(handler, "_rip_verbose_handler", False):
            root_logger.removeHandler(handler)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s:%(lineno)d - %(message)s"
    )
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler._rip_verbose_handler = True  # type: ignore[attr-defined]

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler._rip_verbose_handler = True  # type: ignore[attr-defined]

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    logging.getLogger("watchdog").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("neo4j.notifications").setLevel(logging.WARNING)
    logging.getLogger("neo4j.io").setLevel(logging.WARNING)
    logging.getLogger("neo4j.pool").setLevel(logging.WARNING)
    logger.info("Verbose logging enabled: %s", log_path)
    return log_path


async def _index(
    repo_path: Path,
    verbose: bool = False,
    log_path: Path | None = None,
) -> None:
    from rich.console import Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
    from rich.text import Text

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )
    index_progress = IndexProgress()
    parsing_task = progress.add_task("Starting...", total=None)
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    logger.info("Starting full index: repo_path=%s verbose=%s", repo_path, verbose)

    def make_display():
        header = Text.from_markup(f"[bold cyan]Indexing:[/bold cyan] {repo_path}")
        status = Text.from_markup(
            f"[bold]Phase:[/bold] {index_progress.current_stage}  "
            f"[dim]{index_progress.status_message}[/dim]"
        )

        stats = Table.grid(expand=True)
        stats.add_column(ratio=1)
        stats.add_column(ratio=1)
        stats.add_column(ratio=1)
        stats.add_row(
            f"Files: {index_progress.files_parsed}/{index_progress.files_scanned}",
            f"Skipped: {index_progress.files_skipped}",
            f"Warnings: {index_progress.parse_errors}",
        )
        stats.add_row(
            f"Entities: {index_progress.entities_extracted}",
            f"Relationships: {index_progress.relationships_extracted}",
            f"Neo4j rels: {index_progress.neo4j_relationships_written}",
        )
        stats.add_row(
            f"Neo4j files: {index_progress.neo4j_files_written}",
            f"Qdrant deleted: {index_progress.qdrant_points_deleted}",
            f"Embeddings: {index_progress.embeddings_generated}",
        )

        notes = []
        struct_ready = (
            index_progress.neo4j_entities_written > 0
            and index_progress.embeddings_generated < index_progress.entities_extracted
        )
        if struct_ready:
            notes.append(
                Text.from_markup(
                    "[green]Structural analysis complete![/green] Semantic index running in background."
                )
            )
        if index_progress.current_parsing_file:
            notes.append(
                Text.from_markup(
                    f"[dim]Current file:[/dim] {index_progress.current_parsing_file}"
                )
            )
        if not notes:
            notes.append(
                Text.from_markup(
                    "[dim]I am working; counters will rise as each stage completes.[/dim]"
                )
            )

        return Panel(
            Group(header, status, stats, progress, *notes),
            title="Repository Indexing",
            border_style="cyan",
        )

    with Live(make_display(), refresh_per_second=10):
        try:
            index_progress.current_stage = "Connecting graph"
            index_progress.status_message = f"Connecting to Neo4j at {settings.neo4j_uri}."
            progress.update(parsing_task, description="Connecting to Neo4j...", total=None)
            await client.connect()
            logger.info("Connected to Neo4j: %s", settings.neo4j_uri)
            pipeline = IndexPipeline()
            console.print("[yellow]Starting full indexing (waiting for semantic indexing to complete)...[/yellow]")
            result = await pipeline.run(
                repo_path,
                client,
                background=False,  # Wait for semantic indexing to complete!
                progress=index_progress,
                rich_progress=progress,
                rich_task=parsing_task,
            )
            logger.info(
                "Index complete: phase=%s files=%s entities=%s relationships=%s",
                result.phase,
                result.files_indexed,
                result.progress.entities_extracted,
                result.progress.relationships_extracted,
            )
            progress.update(parsing_task, description="Index complete!", visible=False)
            console.print()
            console.print(
                Panel(
                    f"[green]Indexed {result.files_indexed} files and "
                    f"{result.progress.entities_extracted} entities.[/green]"
                )
            )
            _print_index_progress(result.progress)
            _print_index_timing(result.progress)
        except Exception:
            logger.exception("Full index failed for %s", repo_path)
            if log_path:
                console.print(f"[red]Index failed. Full verbose log:[/red] {log_path}")
            raise
        finally:
            await client.close()
            logger.info("Closed Neo4j connection")


def _print_index_progress(progress: IndexProgress) -> None:
    table = Table(title="Index Progress")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    rows = {
        "Files scanned": progress.files_scanned,
        "Files skipped": progress.files_skipped,
        "Files parsed": progress.files_parsed,
        "Parse warnings": progress.parse_errors,
        "Entities extracted": progress.entities_extracted,
        "Relationships extracted": progress.relationships_extracted,
        "Neo4j files written": progress.neo4j_files_written,
        "Neo4j entities written": progress.neo4j_entities_written,
        "Neo4j relationships written": progress.neo4j_relationships_written,
        "Embeddings generated": progress.embeddings_generated,
        "Qdrant points deleted": progress.qdrant_points_deleted,
        "Qdrant vectors stored": progress.qdrant_vectors_stored,
    }
    for label, value in rows.items():
        table.add_row(label, str(value))
    console.print(table)


def _print_index_timing(progress: IndexProgress) -> None:
    table = Table(title="Index Timing")
    table.add_column("Stage")
    table.add_column("Duration", justify="right")
    for label, seconds in progress.timing_summary().items():
        table.add_row(label, f"{seconds:.2f} sec")
    console.print(table)


async def _incremental_index(repo_path: Path, verbose: bool = False) -> None:
    settings = get_settings()
    neo_client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    logger.info("Starting incremental index: repo_path=%s verbose=%s", repo_path, verbose)
    await neo_client.connect()
    registry = build_default_registry()
    try:
        with console.status(
            "[bold blue]Running incremental index...[/bold blue]",
            spinner="dots",
        ):
            async with async_session_factory() as db_session:
                results = await incremental_index(repo_path, neo_client, db_session, registry)
        logger.info("Incremental index completed: %s", results)
        console.print(
            f"[green]Incremental index complete: {results['updated']} updated, "
            f"{results['deleted']} deleted, {results['skipped']} unchanged.[/green]"
        )
    finally:
        await neo_client.close()
        logger.info("Closed Neo4j connection")


class RepoChangeHandler(FileSystemEventHandler):
    """Watchdog event handler for repo changes."""

    def __init__(self, repo_path: Path):
        super().__init__()
        self.repo_path = repo_path
        self._pending = False

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if (
            any(p in path.parts for p in (".git", "__pycache__", ".venv"))
            or path.suffix in (".pyc", ".pyo")
        ):
            return
        logger.debug("Change detected: %s", event)
        self._pending = True


def _watch_mode(repo_path: Path, verbose: bool = False) -> None:
    """Watch directory for changes and run incremental indexes."""
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text

    handler = RepoChangeHandler(repo_path)
    logger.info("Starting watch mode: repo_path=%s verbose=%s", repo_path, verbose)
    observer = Observer()
    observer.schedule(handler, str(repo_path), recursive=True)
    observer.start()
    recent_updates = []

    def make_display():
        lines = [Text(f"[bold]Watching repository: {repo_path}[/bold]")]
        if recent_updates:
            lines.append(Text("\nRecent updates:"))
            for _, msg in recent_updates[-3:]:
                lines.append(Text(f"  {msg}"))
        lines.append(Text("\n[dim]Press Ctrl+C to stop[/dim]"))
        return Panel("\n".join([str(line) for line in lines]), title="Repo Watch")

    async def watch_loop():
        settings = get_settings()
        neo_client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
        registry = build_default_registry()
        await neo_client.connect()
        try:
            while True:
                await asyncio.sleep(2)
                if handler._pending:
                    handler._pending = False
                    recent_updates.append((asyncio.get_event_loop().time(), "Change detected..."))
                    try:
                        async with async_session_factory() as db_session:
                            results = await incremental_index(
                                repo_path,
                                neo_client,
                                db_session,
                                registry,
                            )
                        recent_updates.append(
                            (
                                asyncio.get_event_loop().time(),
                                (
                                    f"[green]Index complete: {results['updated']} updated, "
                                    f"{results['deleted']} deleted[/green]"
                                ),
                            )
                        )
                    except Exception as exc:
                        recent_updates.append(
                            (
                                asyncio.get_event_loop().time(),
                                f"[red]Error: {exc}[/red]",
                            )
                        )
                        logger.error("Error during watch index: %s", exc, exc_info=True)
        finally:
            await neo_client.close()

    loop = asyncio.get_event_loop()
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: loop.stop())
        loop.create_task(watch_loop())
        with Live(make_display(), refresh_per_second=1):
            loop.run_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping watch mode...[/yellow]")
    finally:
        observer.stop()
        observer.join()
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
