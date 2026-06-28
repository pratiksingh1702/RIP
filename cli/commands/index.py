"""Index repository command - fixed async, prints all logs, instant skip feedback."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import threading
import time
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from cli.runtime_logging import configure_verbose_logging
from core.graph.client import Neo4jClient
from core.indexer.incremental import incremental_index
from core.indexer.pipeline import IndexPipeline, IndexProgress, request_skip
from core.parser.registry import build_default_registry
from core.storage.database import async_session_factory
from server.config import get_settings

console = Console()
logger = logging.getLogger(__name__)

# ============================================================================
# CONSOLE LOG HANDLER - Prints logs directly to console
# ============================================================================

class ConsoleLogHandler(logging.Handler):
    """Custom handler that prints ALL parser/pipeline logs to Rich console."""
    
    COLORS = {
        logging.DEBUG: "dim",
        logging.INFO: "white",
        logging.WARNING: "yellow",
        logging.ERROR: "red",
        logging.CRITICAL: "bold red",
    }
    
    def emit(self, record):
        try:
            msg = self.format(record)
            color = self.COLORS.get(record.levelno, "white")
            
            # Show ALL logs from our packages
            if record.name.startswith(("core.", "cli.")):
                if record.levelno >= logging.WARNING:
                    console.print(f"[{color}]⚠ {msg}[/{color}]")
                else:
                    console.print(f"[{color}]{msg}[/{color}]")
        except Exception:
            pass
# ============================================================================
# SKIP LISTENER WITH IMMEDIATE FEEDBACK
# ============================================================================

_skip_pressed_count = 0

def _listen_for_skip():
    """Listen for 's' key with immediate console feedback."""
    global _skip_pressed_count
    try:
        import msvcrt
        while True:
            if msvcrt.kbhit():
                key = msvcrt.getch().lower()
                if key == b's':
                    _skip_pressed_count += 1
                    request_skip()
                    console.print(f"\n[yellow]⏭ SKIP REQUESTED (#{_skip_pressed_count}) - moving to next file...[/yellow]")
    except (ImportError, OSError):
        pass


def _listen_for_skip_unix():
    """Unix skip listener."""
    global _skip_pressed_count
    try:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        try:
            while True:
                if sys.stdin.read(1).lower() == 's':
                    _skip_pressed_count += 1
                    request_skip()
                    console.print(f"\n[yellow]⏭ SKIP (#{_skip_pressed_count})[/yellow]")
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except (ImportError, OSError):
        pass


def start_skip_listener():
    """Start skip listener."""
    try:
        import msvcrt
        target = _listen_for_skip
    except ImportError:
        target = _listen_for_skip_unix
    t = threading.Thread(target=target, daemon=True)
    t.start()


# ============================================================================
# COMMAND ENTRY
# ============================================================================

def index(
    repo_path: Path = Path("."),
    watch: bool = False,
    incremental: bool = False,
    smart: bool = False,
    languages: str | None = None,
    verbose: bool = False,
) -> None:
    if languages and "python" not in {item.strip() for item in languages.split(",")}:
        console.print("[yellow]Only Python parsing is implemented in Phase 1.[/yellow]")
    repo_path = repo_path.resolve()
    log_path = _configure_verbose_logging(repo_path) if verbose else None
    if log_path:
        console.print(f"[dim]Verbose log: {log_path}[/dim]")
        logger.info("Command started: repo index")
        logger.info(
            "Command parameters: repo_path=%r, watch=%r, incremental=%r, smart=%r, languages=%r",
            repo_path,
            watch,
            incremental,
            smart,
            languages,
        )
    started = time.perf_counter()
    try:
        if watch:
            console.print(f"[cyan]Watch mode on {repo_path}...[/cyan]")
            _watch_mode(repo_path, verbose=verbose)
        elif smart:
            console.print(f"[cyan]Smart index on {repo_path}...[/cyan]")
            asyncio.run(_smart_index(repo_path, verbose=verbose))
        elif incremental:
            console.print(f"[cyan]Incremental index on {repo_path}...[/cyan]")
            asyncio.run(_incremental_index(repo_path, verbose=verbose))
        else:
            console.print(f"[cyan]Full index on {repo_path}...[/cyan]")
            asyncio.run(_index(repo_path, verbose=verbose, log_path=log_path))
        if log_path:
            logger.info("Command completed: repo index in %.3fs", time.perf_counter() - started)
            console.print(f"[dim]Full log saved: {log_path}[/dim]")
    except Exception:
        if log_path:
            logger.exception("Command failed: repo index after %.3fs", time.perf_counter() - started)
            console.print(f"[red]Command failed. Full log: {log_path}[/red]")
        raise


def _configure_verbose_logging(repo_path: Path) -> Path:
    log_path = configure_verbose_logging("index", repo_path)
    logging.getLogger("core.parser").setLevel(logging.WARNING)  # Show WARNING and above
    logging.getLogger("core.parser.languages").setLevel(logging.WARNING)
    return log_path


# ============================================================================
# DISPLAY - Shows current file + recent warnings
# ============================================================================

def _make_display(repo_path: Path, p: IndexProgress) -> Panel:
    """Detailed status panel showing current file and recent warnings."""
    stage = p.current_stage or "Starting"
    elapsed = p.get_stage_elapsed()
    status = p.status_message or ""
    fname = ""

    if p.current_parsing_file:
        try:
            fname = Path(p.current_parsing_file).name
        except Exception:
            fname = str(p.current_parsing_file)

    lines = [
        f"[bold cyan]📂 {repo_path.name}[/bold cyan]",
        f"[bold yellow]⚡ {stage}[/bold yellow] [dim]({elapsed:.0f}s)[/dim]",
        f"[dim]{status[:120]}[/dim]",
        "",
    ]

    # Progress bar
    if p.files_scanned > 0:
        pct = min(p.files_parsed / max(p.files_scanned, 1) * 100, 100)
        bar_len = 30
        filled = int(bar_len * pct / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        lines.append(f"[dim]Progress:[/dim] {bar} {p.files_parsed}/{p.files_scanned} ({pct:.0f}%)")

    if p.entities_extracted > 0 and p.embeddings_generated > 0:
        epct = min(p.embeddings_generated / max(p.entities_extracted, 1) * 100, 100)
        ebar_len = 30
        efilled = int(ebar_len * epct / 100)
        ebar = "█" * efilled + "░" * (ebar_len - efilled)
        lines.append(f"[dim]Embeds:[/dim]   {ebar} {p.embeddings_generated}/{p.entities_extracted} ({epct:.0f}%)")

    lines.append("")
    lines.append(
        f"📊 Entities: {p.entities_extracted:,} | Relations: {p.relationships_extracted:,} | "
        f"Neo4j: {p.neo4j_entities_written:,} | Emb: {p.embeddings_generated:,}"
    )
    lines.append(
        f"⚠ Warnings: {p.parse_errors} | ⏭ Skipped: {len(p.skipped_files)} | "
        f"💾 Mem: {p.memory_mb:.0f}MB | 📦 Batches: {p.batches_completed}"
    )
    lines.append("")

    # Current file
    if fname:
        lines.append(f"[bold]📝 NOW:[/bold] [cyan]{fname}[/cyan]")
        if p.current_file_size > 0:
            sz = p.current_file_size / 1024
            lines.append(f"   Size: {sz:.1f}KB | Time: {p.current_file_duration:.1f}s | Entities: {p.current_file_entities}")
        if p.current_file_duration > 5:
            lines.append(f"   [yellow]⚠ SLOW FILE - taking {p.current_file_duration:.0f}s...[/yellow]")
        if p.current_file_duration > 15:
            lines.append("   [bold red]🐌 VERY SLOW - Press 's' to skip![/bold red]")
        lines.append("")

    lines.append(f"[dim]Press [bold yellow]'s'[/bold yellow] to skip current file | Skipped so far: {len(p.skipped_files)}[/dim]")

    # Recent warnings (last 5)
    if p.warnings:
        lines.append("")
        lines.append("[bold yellow]Recent warnings:[/bold yellow]")
        for w in p.warnings[-5:]:
            # Truncate long warnings
            short_w = w[:100] + "..." if len(w) > 100 else w
            lines.append(f"  [dim]{short_w}[/dim]")

    # Recent skips
    if p.skipped_files:
        lines.append("")
        lines.append("[yellow]Recently skipped:[/yellow]")
        for sf in p.skipped_files[-3:]:
            try:
                lines.append(f"  ⏭ [dim]{Path(sf).name}[/dim]")
            except Exception:
                lines.append(f"  ⏭ [dim]{sf}[/dim]")

    return Panel("\n".join(lines), title="[bold]🔍 Repository Indexing[/bold]",
                  border_style="cyan", padding=(1, 2))


# ============================================================================
# MAIN INDEX
# ============================================================================

async def _index(
    repo_path: Path,
    verbose: bool = False,
    log_path: Path | None = None,
) -> None:
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)

    p = IndexProgress()
    p.current_stage = "Connecting"
    p.status_message = "Connecting to Neo4j..."
    p.stage_start_time = time.perf_counter()

    start_skip_listener()
    console.print("[yellow]Starting index...[/yellow]")
    console.print("[dim]Press [bold yellow]'s'[/bold yellow] to skip stuck files[/dim]")
    console.print()

    try:
        await client.connect()
        logger.info("Connected to Neo4j")

        pipeline = IndexPipeline()

        with Live(_make_display(repo_path, p), refresh_per_second=4,
                  console=console, transient=False, screen=False) as live:

            async def updater():
                while True:
                    live.update(_make_display(repo_path, p))
                    await asyncio.sleep(0.25)

            task = asyncio.create_task(updater())
            try:
                result = await pipeline.run(repo_path, client, background=False, progress=p)
            finally:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            p.current_stage = "Complete"
            p.status_message = "Done!"
            live.update(_make_display(repo_path, p))
            await asyncio.sleep(0.5)

        # Results
        console.print()
        console.print(Panel(
            f"[green]✅ {result.files_indexed} files indexed[/green]\n"
            f"[green]✅ {result.progress.entities_extracted} entities extracted[/green]\n"
            f"[green]✅ {result.progress.embeddings_generated} embeddings generated[/green]",
            title="[bold]Index Complete[/bold]", border_style="green"))

        if p.skipped_files:
            console.print(f"\n[yellow]⚠ Skipped {len(p.skipped_files)} files:[/yellow]")
            for sf in p.skipped_files[:10]:
                console.print(f"  [dim]{sf}[/dim]")

        if p.warnings:
            console.print(f"\n[yellow]⚠ {len(p.warnings)} warnings (check log for details)[/yellow]")

        # Timing
        timing = p.timing_summary()
        console.print("\n[bold]⏱️  Timing:[/bold]")
        total = timing.get("Total", 1)
        for label, sec in timing.items():
            pct = (sec / total * 100) if total > 0 else 0
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            console.print(f"  {label:12} {bar} {sec:.1f}s ({pct:.0f}%)")

        # Stats
        console.print()
        t = Table(show_header=False, box=None, padding=(0, 2))
        t.add_column(style="dim")
        t.add_column(justify="right", style="cyan")
        for label, val in [
            ("Files scanned", p.files_scanned),
            ("Files parsed", p.files_parsed),
            ("Files skipped", len(p.skipped_files)),
            ("Parse warnings", p.parse_errors),
            ("Entities", p.entities_extracted),
            ("Relationships", p.relationships_extracted),
            ("Neo4j entities", p.neo4j_entities_written),
            ("Embeddings", p.embeddings_generated),
        ]:
            t.add_row(f"  {label}:", f"{val:,}")
        console.print(t)

    except Exception:
        logger.exception("Index failed")
        if log_path:
            console.print(f"\n[red]❌ Failed. Full log: {log_path}[/red]")
        raise
    finally:
        await client.close()


# ============================================================================
# INCREMENTAL
# ============================================================================

async def _incremental_index(repo_path: Path, verbose: bool = False) -> None:
    settings = get_settings()
    neo = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    await neo.connect()
    reg = build_default_registry()
    try:
        with console.status("[bold blue]Incremental index...[/bold blue]", spinner="dots"):
            async with async_session_factory() as db:
                r = await incremental_index(repo_path, neo, db, reg)
        console.print(f"[green]✅ {r['updated']} updated, {r['deleted']} deleted, {r['skipped']} skipped[/green]")
    finally:
        await neo.close()


async def _smart_index(repo_path: Path, verbose: bool = False) -> None:
    from core.indexer.incremental import smart_index

    settings = get_settings()
    neo = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    await neo.connect()
    reg = build_default_registry()
    try:
        with console.status("[bold blue]Smart index...[/bold blue]", spinner="dots"):
            async with async_session_factory() as db:
                r = await smart_index(repo_path, neo, db, reg)
        if r["updated"] == 0 and r["deleted"] == 0:
            console.print("[green]Nothing to index - git reports no source changes[/green]")
            return
        console.print(
            "[green]Indexed {updated} files, deleted {deleted}, "
            "{entities} entities in {duration:.1f}s[/green]".format(**r)
        )
    finally:
        await neo.close()


# ============================================================================
# WATCH MODE
# ============================================================================

class RepoChangeHandler(FileSystemEventHandler):
    def __init__(self, repo_path: Path):
        super().__init__()
        self.repo_path = repo_path
        self._pending = False

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        p = Path(event.src_path)
        if any(x in p.parts for x in (".git", "__pycache__", ".venv", ".repo-intel")):
            return
        if p.suffix in (".pyc", ".pyo"):
            return
        self._pending = True


def _watch_mode(repo_path: Path, verbose: bool = False) -> None:
    handler = RepoChangeHandler(repo_path)
    observer = Observer()
    observer.schedule(handler, str(repo_path), recursive=True)
    observer.start()
    recent = []

    def display():
        lines = [f"[bold]👀 Watching: {repo_path}[/bold]"]
        if recent:
            lines.append("\nRecent:")
            for _, msg in recent[-3:]:
                lines.append(f"  {msg}")
        lines.append("\n[dim]Ctrl+C to stop[/dim]")
        return Panel("\n".join(lines), title="Watch")

    async def loop():
        s = get_settings()
        neo = Neo4jClient(s.neo4j_uri, s.neo4j_user, s.neo4j_password)
        reg = build_default_registry()
        await neo.connect()
        try:
            while True:
                await asyncio.sleep(2)
                if handler._pending:
                    handler._pending = False
                    recent.append((time.time(), "🔄 Change detected..."))
                    try:
                        async with async_session_factory() as db:
                            r = await incremental_index(repo_path, neo, db, reg)
                        recent.append((time.time(), f"[green]✅ {r['updated']} updated[/green]"))
                    except Exception as e:
                        recent.append((time.time(), f"[red]❌ {e}[/red]"))
        finally:
            await neo.close()

    eloop = asyncio.get_event_loop()
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            eloop.add_signal_handler(sig, lambda: eloop.stop())
        eloop.create_task(loop())
        with Live(display(), refresh_per_second=1):
            eloop.run_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping...[/yellow]")
    finally:
        observer.stop()
        observer.join()
