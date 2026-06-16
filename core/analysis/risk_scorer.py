"""Risk scoring engine."""

from __future__ import annotations

from core.analysis.base import BaseAnalyser


class RiskScorer(BaseAnalyser):
    """Computes risk scores for files based on churn, complexity, and test coverage."""

    async def get_file_risk(self, file_path: str, coverage: float = 0.8) -> dict[str, object]:
        """Compute the risk score for a single file."""
        query = """
        MATCH (f:File)
        WHERE f.path = $file_path OR f.path ENDS WITH $suffix
        OPTIONAL MATCH (c:Commit)-[:MODIFIES]->(f)
        OPTIONAL MATCH (f)-[:CONTAINS]->(fn:Function)
        OPTIONAL MATCH (other)-[:CALLS]->(fn)
        RETURN f.path AS path,
               count(DISTINCT c) AS change_frequency,
               count(DISTINCT other) AS incoming_calls
        """
        suffix = file_path.replace("\\", "/").lstrip("/")
        if not suffix.startswith("/"):
            suffix = "/" + suffix

        records = await self.graph_client.execute(query, {"file_path": file_path, "suffix": suffix})
        if not records:
            return {
                "file_path": file_path,
                "change_frequency": 0,
                "incoming_calls": 0,
                "coverage": coverage,
                "risk_score": 0.0,
            }

        rec = records[0]
        path = rec.get("path") or file_path
        change_freq = rec.get("change_frequency", 0) or 0
        incoming = rec.get("incoming_calls", 0) or 0

        score = float(change_freq * incoming * (1.0 - coverage))

        return {
            "file_path": path,
            "change_frequency": change_freq,
            "incoming_calls": incoming,
            "coverage": coverage,
            "risk_score": round(score, 2),
        }

    async def get_all_risks(self, default_coverage: float = 0.8) -> list[dict[str, object]]:
        """Compute risk scores for all files in the repository."""
        query = """
        MATCH (f:File)
        OPTIONAL MATCH (c:Commit)-[:MODIFIES]->(f)
        OPTIONAL MATCH (f)-[:CONTAINS]->(fn:Function)
        OPTIONAL MATCH (other)-[:CALLS]->(fn)
        RETURN f.path AS path,
               count(DISTINCT c) AS change_frequency,
               count(DISTINCT other) AS incoming_calls
        """
        records = await self.graph_client.execute(query)
        results = []
        for r in records:
            path = r.get("path")
            if not path:
                continue
            change_freq = r.get("change_frequency", 0) or 0
            incoming = r.get("incoming_calls", 0) or 0
            score = float(change_freq * incoming * (1.0 - default_coverage))
            results.append({
                "file_path": path,
                "change_frequency": change_freq,
                "incoming_calls": incoming,
                "coverage": default_coverage,
                "risk_score": round(score, 2),
            })

        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results
