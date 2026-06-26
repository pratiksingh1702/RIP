"""Source registry to manage available data sources."""

from typing import Dict

import structlog

from gateway.config import settings
from .base import BaseSource
from .rip_client import RIPSource
from .github import GitHubSource
from .jira import JiraSource
from .slack import SlackSource

logger = structlog.get_logger(__name__)


class SourceRegistry:
    """Registry for all available data sources."""

    def __init__(self):
        self._sources: Dict[str, BaseSource] = {}
        self._health: Dict[str, bool] = {}
        self._initialize_sources()

    def _initialize_sources(self) -> None:
        """Initialize all configured sources."""
        # RIP is always initialized
        rip = RIPSource()
        self._sources["rip"] = rip
        self._health["rip"] = True

        # Optional sources are always visible, but disabled until configured.
        self._sources["github"] = GitHubSource(enabled=settings.github_mcp_enabled)
        self._health["github"] = settings.github_mcp_enabled
        self._sources["jira"] = JiraSource(enabled=settings.jira_mcp_enabled)
        self._health["jira"] = settings.jira_mcp_enabled
        self._sources["slack"] = SlackSource(enabled=settings.slack_mcp_enabled)
        self._health["slack"] = settings.slack_mcp_enabled

    @property
    def sources(self) -> Dict[str, BaseSource]:
        """Get all registered sources."""
        return dict(self._sources)

    def get_source(self, name: str) -> BaseSource | None:
        """Get a source by name."""
        return self._sources.get(name)

    def list_sources(self) -> Dict[str, BaseSource]:
        """List all registered sources."""
        return dict(self._sources)

    async def check_all_health(self) -> Dict[str, bool]:
        """Check health of all registered sources."""
        health_results = {}
        for name, source in self._sources.items():
            try:
                health_results[name] = await source.health_check()
                self._health[name] = health_results[name]
            except Exception as e:
                logger.warning(f"Health check failed for {name}", error=str(e))
                health_results[name] = False
                self._health[name] = False
        return health_results

    def get_health(self, name: str) -> bool:
        """Get last known health status of a source."""
        return self._health.get(name, False)
    
    def is_healthy(self, name: str) -> bool:
        """Check if a source is healthy (alias for get_health)."""
        return self.get_health(name)

    def enabled_source_names(self) -> list[str]:
        """Return sources currently enabled for planner/executor use."""
        return [
            name
            for name, source in self._sources.items()
            if name == "rip" or getattr(source, "enabled", source.is_available())
        ]

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """Enable or disable a registered optional source for this process."""
        source = self._sources.get(name)
        if source is None or name == "rip":
            return False
        setattr(source, "enabled", enabled)
        source.available = enabled
        self._health[name] = enabled
        return True


# Global registry instance
_registry: SourceRegistry | None = None


def get_source_registry() -> SourceRegistry:
    """Get the global source registry."""
    global _registry
    if _registry is None:
        _registry = SourceRegistry()
    return _registry
