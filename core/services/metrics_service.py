"""Metrics domain service."""

from __future__ import annotations


class MetricsService:
    def __init__(self, graph_store) -> None:
        self.graph_store = graph_store

    async def module_metrics(self, project_id: str) -> dict[str, dict[str, int]]:
        data = await self.graph_store.architecture(project_id)
        counts: dict[str, dict[str, int]] = {}
        for row in data.get("dependencies", []):
            source = str(row.get("source") or "")
            target = str(row.get("target") or "")
            counts.setdefault(source, {"in": 0, "out": 0})["out"] += 1
            counts.setdefault(target, {"in": 0, "out": 0})["in"] += 1
        return counts
