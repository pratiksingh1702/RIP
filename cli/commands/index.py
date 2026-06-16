"""Index repository command."""

from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path

from rich.console import Console
from rich.table import Table
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from core.graph.client import Neo4jClient
from core.indexer.incremental import incremental_index
from core.indexer.pipeline import IndexProgress, index_repository_with_resources
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
) -> None:
    if languages and "python" not in {item.strip() for item in languages.split(",")}:
        console.print("[yellow]Only Python parsing is implemented in Phase 1.[/yellow]")
    repo_path = repo_path.resolve()
    if watch:
        console.print(f"[cyan]Starting watch mode on {repo_path}...[/cyan]")
        _watch_mode(repo_path)
    elif incremental:
        console.print(f"[cyan]Starting incremental index on {repo_path}...[/cyan]")
        asyncio.run(_incremental_index(repo_path))
    else:
        console.print(f"[cyan]Starting full index on {repo_path}...[/cyan]")
        asyncio.run(_index(repo_path))


async def _index(repo_path: Path) -> None:
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
    parsing_task = progress.add_task("Discovering files...", total=None)
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)

    def make_display():
        lines = [Text(f"[bold]Indexing repository: {repo_path}[/bold]")]
        struct_ready = (
            index_progress.neo4j_relationships_written > 0
            and index_progress.embeddings_generated < index_progress.entities_extracted
        )
        if struct_ready:
            lines.append(
                Text(
                    "\n[green]✓ Structural analysis ready! "
                    "You can use repo trace, repo impact, etc.[/green]"
                )
            )
        if index_progress.current_parsing_file:
            lines.append(Text(f"\n  Parsing: {index_progress.current_parsing_file}"))
        return Panel(progress, title="Repository Indexing")

    with Live(make_display(), refresh_per_second=10):
        try:
            await client.connect()
            summary = await index_repository_with_resources(
                repo_path,
                client,
                progress=index_progress,
                rich_progress=progress,
                rich_task=parsing_task,
            )
            progress.update(parsing_task, description="Index complete!", visible=False)
            console.print()
            console.print(
                Panel(
                    f"[green]Indexed {summary.indexed_files} files and "
                    f"{summary.total_entities} entities.[/green]"
                )
            )
            _print_index_progress(summary.progress)
        finally:
            await client.close()


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


async def _incremental_index(repo_path: Path) -> None:
    settings = get_settings()
    neo_client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    await neo_client.connect()
    registry = build_default_registry()
    try:
        with console.status(
            "[bold blue]Running incremental index...[/bold blue]",
            spinner="dots",
        ):
            async with async_session_factory() as db_session:
                results = await incremental_index(repo_path, neo_client, db_session, registry)
        console.print(
            f"[green]Incremental index complete: {results['updated']} updated, "
            f"{results['deleted']} deleted, {results['skipped']} unchanged.[/green]"
        )
    finally:
        await neo_client.close()


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


def _watch_mode(repo_path: Path) -> None:
    """Watch directory for changes and run incremental indexes."""
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text

    handler = RepoChangeHandler(repo_path)
    observer = Observer()
    observer.schedule(handler, str(repo_path), recursive=True)
    observer.start()
    recent_updates = []  # Store (time, message)

    def make_display():
        lines = [Text(f"[bold]Watching repository: {repo_path}[/bold]")]
        if recent_updates:
            lines.append(Text("\nRecent updates:"))
            for _, msg in recent_updates[-3:]:  # Show last 3
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
                                repo_path, neo_client, db_session, registry
                            )
                        recent_updates.append((
                            asyncio.get_event_loop().time(),
                            (
                                f"[green]✓ Index complete: {results['updated']} updated, "
                                f"{results['deleted']} deleted[/green]"
                            ),
                        ))
                    except Exception as exc:
                        recent_updates.append((
                            asyncio.get_event_loop().time(),
                            f"[red]✗ Error: {exc}[/red]"
                        ))
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
        for t in pending:
            t.cancel()
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
