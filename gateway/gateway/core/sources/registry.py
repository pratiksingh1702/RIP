"""Source registry to manage available data sources."""


import structlog

from gateway.config import settings
from gateway.storage import source_registry as source_store
from gateway.storage.source_registry import SourceRecord

from .base import BaseSource
from .dynamic_mcp import DynamicMCPSource
from .github import GitHubSource
from .jira import JiraSource
from .rip_client import RIPSource
from .slack import SlackSource

logger = structlog.get_logger(__name__)


class SourceRegistry:
    """Registry for all available data sources."""

    def __init__(self):
        self._sources: dict[str, BaseSource] = {}
        self._health: dict[str, bool] = {}
        self._records: dict[str, SourceRecord] = {}
        self._project_id: str | None = None
        self._user_id: str | None = None
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

    async def refresh(self, project_id: str | None = None, user_id: str | None = None) -> None:
        """Hydrate the process registry from persistent source rows."""
        try:
            records = await source_store.list_sources(project_id=project_id, user_id=user_id)
        except Exception as exc:
            logger.warning("Failed to refresh persistent source registry", error=str(exc))
            return

        self._project_id = project_id
        self._user_id = user_id
        next_sources: dict[str, BaseSource] = {}
        next_health: dict[str, bool] = {}
        next_records: dict[str, SourceRecord] = {}
        for record in records:
            source = self._source_from_record(record)
            next_sources[record.name] = source
            next_health[record.name] = record.health_status == "ok" or bool(source.is_available())
            next_records[record.name] = record
        self._sources = next_sources
        self._health = next_health
        self._records = next_records

    def _source_from_record(self, record: SourceRecord) -> BaseSource:
        if record.name == "rip":
            return self._sources.get("rip") or RIPSource()
        if record.name == "github" and record.kind == "builtin":
            return GitHubSource(record=record)
        if record.name == "jira" and record.kind == "builtin":
            return JiraSource(record=record)
        if record.name == "slack" and record.kind == "builtin":
            return SlackSource(record=record)
        return DynamicMCPSource(record)

    @property
    def sources(self) -> dict[str, BaseSource]:
        """Get all registered sources."""
        return dict(self._sources)

    def get_source(self, name: str) -> BaseSource | None:
        """Get a source by name."""
        return self._sources.get(name)

    def get_record(self, name: str) -> SourceRecord | None:
        """Get persistent metadata for a source by name."""
        return self._records.get(name)

    def list_sources(self) -> dict[str, BaseSource]:
        """List all registered sources."""
        return dict(self._sources)

    async def check_all_health(self) -> dict[str, bool]:
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

    def enabled_source_names(self, project_id: str | None = None) -> list[str]:
        """Return sources currently enabled for planner/executor use."""
        if project_id != self._project_id:
            logger.debug("Source registry project differs from requested project", requested=project_id, active=self._project_id)
        enabled = []
        for name, source in self._sources.items():
            record = self._records.get(name)
            if record is not None:
                if record.protected or record.enabled:
                    enabled.append(name)
                continue
            if name == "rip" or getattr(source, "enabled", source.is_available()):
                enabled.append(name)
        return enabled

    def dynamic_source_records(self, project_id: str | None = None) -> list[SourceRecord]:
        """Return enabled non-built-in sources for planner hint matching."""
        return [
            record for record in self._records.values()
            if record.enabled and record.kind == "mcp" and not record.protected
            and (project_id is None or record.project_id in {None, project_id})
        ]

    def set_enabled(self, name: str, enabled: bool) -> bool:
        """Enable or disable a registered optional source for this process."""
        source = self._sources.get(name)
        if source is None or name == "rip":
            return False
        source.enabled = enabled
        source.available = enabled
        self._health[name] = enabled
        if name in self._records:
            self._records[name].enabled = enabled
        return True


# Global registry instance
_registry: SourceRegistry | None = None


def get_source_registry() -> SourceRegistry:
    """Get the global source registry."""
    global _registry
    if _registry is None:
        _registry = SourceRegistry()
    return _registry
