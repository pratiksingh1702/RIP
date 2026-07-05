"""Retry helper with exponential backoff."""

import asyncio
from collections.abc import Callable
from typing import TypeVar

import structlog

T = TypeVar("T")
logger = structlog.get_logger(__name__)


async def retry_async(
    func: Callable[..., asyncio.Future[T]],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0
) -> T:
    """Retry an async function with exponential backoff."""
    attempt = 0
    last_exception = None

    while attempt < max_attempts:
        try:
            return await func()
        except Exception as e:
            attempt += 1
            last_exception = e
            if attempt >= max_attempts:
                logger.warning(
                    "Max retry attempts reached",
                    func=func.__name__,
                    attempts=max_attempts,
                    error=str(e)
                )
                raise

            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            logger.info(
                "Retrying after failure",
                func=func.__name__,
                attempt=attempt,
                delay_seconds=delay
            )
            await asyncio.sleep(delay)

    raise last_exception or RuntimeError("Retry failed")
