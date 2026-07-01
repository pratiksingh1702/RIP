"""Thin runtime orchestrator."""

from __future__ import annotations

from core.runtime.environment import RuntimeEnvironment
from core.services import (
    ArchitectureService,
    DeadCodeService,
    DependenciesService,
    ImpactService,
    MetricsService,
    OnboardService,
    SearchService,
    TraceService,
)


class ContextEngine:
    def __init__(self, env: RuntimeEnvironment) -> None:
        self.env = env
        self.search_service = SearchService(env.vector)
        self.trace_service = TraceService(env.graph)
        self.impact_service = ImpactService(env.graph)
        self.architecture_service = ArchitectureService(env.graph)
        self.dependencies_service = DependenciesService(env.graph)
        self.dead_code_service = DeadCodeService(env.graph)
        self.metrics_service = MetricsService(env.graph)
        self.onboard_service = OnboardService(env.graph)

    async def search(self, query: str, project_id: str, limit: int = 20, filters=None):
        return await self.search_service.search(query, project_id, limit, filters)

    async def trace(self, symbol: str, project_id: str, depth: int = 8):
        return await self.trace_service.trace(symbol, project_id, depth)

    async def architecture(self, project_id: str):
        return await self.architecture_service.architecture(project_id)

    async def impact(self, symbol: str, project_id: str):
        return await self.impact_service.analyze(symbol, project_id)

    async def dependencies(self, target: str, project_id: str):
        return await self.dependencies_service.dependencies(target, project_id)

    async def dead_code(self, project_id: str, entity_type: str = "all"):
        return await self.dead_code_service.find_unused(project_id, entity_type)

    async def metrics(self, project_id: str):
        return await self.metrics_service.module_metrics(project_id)

    async def onboard_markdown(self, project_id: str):
        return await self.onboard_service.markdown(
            project_id,
            storage_description=self.env.description,
            mode=self.env.mode.value,
        )
