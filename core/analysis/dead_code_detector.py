"""Dead code detection engine."""

from __future__ import annotations

from core.analysis.base import BaseAnalyser
from core.graph.queries.dead_code import get_dead_classes, get_dead_functions


class DeadCodeDetector(BaseAnalyser):
    """Detects unused/dead code in the repository."""

    async def detect(
        self,
        entity_type: str = "all",
        known_entry_points: list[str] | None = None,
        project_id: str | None = None,
    ) -> list[dict]:
        """Detect unused code entities (functions, classes, or all)."""
        entry_points = known_entry_points or ["main"]
        dead_entities = []

        if entity_type in ("functions", "all"):
            funcs = await get_dead_functions(self.graph_client, entry_points, project_id=project_id)
            for f in funcs:
                f["type"] = "function"
                dead_entities.append(f)

        if entity_type in ("classes", "all"):
            cls_list = await get_dead_classes(self.graph_client, project_id=project_id)
            for c in cls_list:
                c["type"] = "class"
                dead_entities.append(c)

        return dead_entities
