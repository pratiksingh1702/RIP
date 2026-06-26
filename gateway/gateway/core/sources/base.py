"""Base source interface for all sources."""

from abc import ABC, abstractmethod
from typing import Any

from .models import SourceResponse


class BaseSource(ABC):
    """Abstract base class for all data sources."""

    name: str
    is_available: bool = True

    @abstractmethod
    async def query(self, query_type: str, query_params: dict[str, Any]) -> SourceResponse:
        """Query the source with given type and parameters."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the source is healthy."""
        pass
