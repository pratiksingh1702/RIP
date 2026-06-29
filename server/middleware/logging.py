"""Request logging middleware with beautiful console output."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from fastapi import Request, Response
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

logger = logging.getLogger(__name__)
console = Console()


async def log_requests(request: Request, call_next: Callable) -> Response:
    """Log requests and responses with timing and status codes."""
    start = time.perf_counter()
    
    # Process request
    response = await call_next(request)
    
    duration_ms = (time.perf_counter() - start) * 1000
    
    # Determine status color
    status_code = response.status_code
    if 200 <= status_code < 300:
        status_color = "green"
    elif 300 <= status_code < 400:
        status_color = "yellow"
    else:
        status_color = "red"

    # Determine method color
    method_colors = {
        "GET": "cyan",
        "POST": "magenta",
        "PUT": "blue",
        "DELETE": "red",
        "PATCH": "yellow",
    }
    method_color = method_colors.get(request.method, "white")

    # Log to standard logger for files
    logger.info(
        "%s %s - %d %s - %.2fms",
        request.method,
        request.url.path,
        status_code,
        status_color,
        duration_ms,
    )

    # Beautiful console output
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row(
        f"[{method_color}]{request.method:<7}[/]",
        f"[white]{request.url.path:<40}[/]",
        f"[{status_color}]{status_code}[/]",
        f"[dim]{duration_ms:>8.2f}ms[/]",
    )
    
    console.print(table)
    
    return response
