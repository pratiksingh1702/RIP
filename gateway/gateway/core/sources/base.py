"""Base source interface for all sources."""

from abc import ABC, abstractmethod
from typing import Any

from .models import SourceResponse


class BaseSource(ABC):
    """Abstract base class for all data sources."""

    name: str
    available: bool = True

    def is_available(self) -> bool:
        """Return the last known availability for display and routing."""
        return self.available

    @abstractmethod
    async def query(self, query_type: str, query_params: dict[str, Any]) -> SourceResponse:
        """Query the source with given type and parameters."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the source is healthy."""
        raise NotImplementedError
