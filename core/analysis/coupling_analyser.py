"""Coupling analysis engine."""

from __future__ import annotations

from core.analysis.base import BaseAnalyser
from core.graph.queries.coupling import get_all_coupling, get_module_coupling


class CouplingAnalyser(BaseAnalyser):
    """Computes coupling metrics (afferent, efferent, instability) for modules and files."""

    async def analyze_module(
        self, 
        module_path: str,
        project_id: str | None = None,
    ) -> dict[str, object]:
        """Analyze coupling for a specific module/file path."""
        coupling = await get_module_coupling(self.graph_client, module_path, project_id=project_id)
        ca = coupling["afferent"]
        ce = coupling["efferent"]
        
        # Calculate Instability: I = Ce / (Ca + Ce)
        instability = 0.0
        if (ca + ce) > 0:
            instability = ce / (ca + ce)
            
        return {
            "module": module_path,
            "afferent_coupling": ca,
            "efferent_coupling": ce,
            "instability": instability,
        }

    async def analyze_all(
        self,
        project_id: str | None = None,
    ) -> list[dict[str, object]]:
        """Analyze coupling for all files/modules in the repository."""
        results = await get_all_coupling(self.graph_client, project_id=project_id)
        analysed = []
        for r in results:
            ca = r["afferent"]
            ce = r["efferent"]
            instability = 0.0
            if (ca + ce) > 0:
                instability = ce / (ca + ce)
            analysed.append({
                "module": r["file_path"],
                "afferent_coupling": ca,
                "efferent_coupling": ce,
                "instability": instability,
            })
        return analysed
