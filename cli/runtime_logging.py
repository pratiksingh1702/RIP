"""Shared verbose logging helpers for CLI commands."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import ParamSpec, TypeVar

from rich.console import Console

P = ParamSpec("P")
R = TypeVar("R")

console = Console()
logger = logging.getLogger(__name__)


class RichVerboseLogHandler(logging.Handler):
    """Mirror RIP logs to the terminal while the full stream goes to a file."""

    COLORS = {
        logging.DEBUG: "dim",
        logging.INFO: "white",
        logging.WARNING: "yellow",
        logging.ERROR: "red",
        logging.CRITICAL: "bold red",
    }

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if not record.name.startswith(("cli.", "core.", "server.", "mcp.", "__main__")):
                return
            msg = self.format(record)
            color = self.COLORS.get(record.levelno, "white")
            prefix = "WARN " if record.levelno >= logging.WARNING else ""
            console.print(f"[{color}]{prefix}{msg}[/{color}]")
        except Exception:
            self.handleError(record)


def configure_verbose_logging(command_name: str, log_root: Path | None = None) -> Path:
    """Enable detailed console/file logging for one CLI command invocation."""

    root = (log_root or Path.cwd()).resolve()
    log_dir = root / ".repo-intel" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    safe_name = command_name.replace(" ", "-").replace("_", "-")
    log_path = log_dir / f"{safe_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    for handler in list(root_logger.handlers):
        if getattr(handler, "_rip_verbose_handler", False):
            root_logger.removeHandler(handler)
            handler.close()

    file_format = logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)-7s %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_format)
    file_handler._rip_verbose_handler = True
    root_logger.addHandler(file_handler)

    console_handler = RichVerboseLogHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    console_handler._rip_verbose_handler = True
    root_logger.addHandler(console_handler)

    for noisy in (
        "watchdog",
        "httpx",
        "httpcore",
        "urllib3",
        "neo4j",
        "neo4j.io",
        "neo4j.pool",
        "qdrant_client",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logger.info("Verbose logging enabled: %s", log_path)
    return log_path


def run_with_verbose_logging(
    command_name: str,
    *,
    verbose: bool,
    log_root: Path | None,
    params: dict[str, object],
    action: Callable[[], R],
) -> R:
    """Run a command and capture detailed diagnostics when verbose is enabled."""

    log_path = configure_verbose_logging(command_name, log_root) if verbose else None
    if log_path:
        console.print(f"[dim]Verbose log: {log_path}[/dim]")

    started = time.perf_counter()
    if verbose:
        logger.info("Command started: repo %s", command_name)
        logger.info("Command parameters: %s", _format_params(params))

    try:
        result = action()
        if verbose:
            elapsed = time.perf_counter() - started
            logger.info("Command completed: repo %s in %.3fs", command_name, elapsed)
            if log_path:
                console.print(f"[dim]Full log saved: {log_path}[/dim]")
        return result
    except Exception:
        elapsed = time.perf_counter() - started
        if verbose:
            logger.exception("Command failed: repo %s after %.3fs", command_name, elapsed)
        if log_path:
            console.print(f"[red]Command failed. Full log: {log_path}[/red]")
        raise


def _format_params(params: dict[str, object]) -> str:
    return ", ".join(f"{key}={value!r}" for key, value in sorted(params.items()))
