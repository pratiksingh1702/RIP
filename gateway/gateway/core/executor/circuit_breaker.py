"""Circuit breaker for unhealthy sources."""

from datetime import datetime, timedelta
from typing import Dict

import structlog

logger = structlog.get_logger(__name__)


class CircuitBreaker:
    """Circuit breaker to prevent cascading failures from unhealthy sources."""

    FAILURE_THRESHOLD = 3
    RESET_TIMEOUT_SECONDS = 300
    WINDOW_SECONDS = 60

    def __init__(self):
        self._failures: Dict[str, list[datetime]] = {}
        self._open_until: Dict[str, datetime] = {}

    def is_open(self, source_name: str) -> bool:
        """Check if the circuit is open for this source."""
        if source_name in self._open_until:
            if datetime.utcnow() < self._open_until[source_name]:
                return True
            else:
                del self._open_until[source_name]
        return False

    def record_failure(self, source_name: str) -> None:
        """Record a failure for the source."""
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.WINDOW_SECONDS)

        if source_name not in self._failures:
            self._failures[source_name] = []

        # Clean old failures
        self._failures[source_name] = [
            t for t in self._failures[source_name]
            if t > window_start
        ]

        self._failures[source_name].append(now)

        if len(self._failures[source_name]) >= self.FAILURE_THRESHOLD:
            self._open_until[source_name] = now + timedelta(seconds=self.RESET_TIMEOUT_SECONDS)
            logger.warning(
                "Circuit breaker opened",
                source=source_name,
                reset_at=self._open_until[source_name]
            )

    def record_success(self, source_name: str) -> None:
        """Record a success for the source (clears failures)."""
        if source_name in self._failures:
            del self._failures[source_name]


# Global circuit breaker instance
_circuit_breaker: CircuitBreaker | None = None


def get_circuit_breaker() -> CircuitBreaker:
    """Get the global circuit breaker instance."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
    return _circuit_breaker
