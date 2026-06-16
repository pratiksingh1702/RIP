"""Metrics command."""

from __future__ import annotations

import asyncio

from rich.console import Console
from rich.table import Table

from core.analysis.coupling_analyser import CouplingAnalyser
from core.analysis.risk_scorer import RiskScorer
from core.graph.client import Neo4jClient
from server.config import get_settings

console = Console()


def metrics(
    module: str | None = None,
    top_risk: int | None = None,
) -> None:
    """Show coupling, cohesion, instability, and risk metrics."""
    asyncio.run(_metrics(module=module, top_risk=top_risk))


async def _metrics(module: str | None, top_risk: int | None) -> None:
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        if module:
            analyser = CouplingAnalyser(client)
            coupling_data = await analyser.analyze_module(module)
            scorer = RiskScorer(client)
            risk_data = await scorer.get_file_risk(module)

            table = Table(title=f"Metrics for: {module}")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green", justify="right")

            table.add_row("Afferent Coupling (Ca)", str(coupling_data["afferent_coupling"]))
            table.add_row("Efferent Coupling (Ce)", str(coupling_data["efferent_coupling"]))
            table.add_row("Instability (I)", f"{coupling_data['instability']:.4f}")
            table.add_row("Change Frequency (Git Churn)", str(risk_data["change_frequency"]))
            table.add_row("Incoming Calls (Complexity)", str(risk_data["incoming_calls"]))
            table.add_row("Risk Score", f"{risk_data['risk_score']:.2f}")

            console.print(table)

        elif top_risk is not None:
            scorer = RiskScorer(client)
            all_risks = await scorer.get_all_risks()
            top_risky = all_risks[:top_risk]

            analyser = CouplingAnalyser(client)
            table = Table(title=f"Top {top_risk} Riskiest Modules")
            table.add_column("Module/File Path", style="cyan")
            table.add_column("Ca", style="magenta", justify="right")
            table.add_column("Ce", style="magenta", justify="right")
            table.add_column("Instability", style="yellow", justify="right")
            table.add_column("Churn", style="blue", justify="right")
            table.add_column("Incoming Calls", style="blue", justify="right")
            table.add_column("Risk Score", style="red", justify="right")

            for r in top_risky:
                coupling_data = await analyser.analyze_module(r["file_path"])
                table.add_row(
                    r["file_path"],
                    str(coupling_data["afferent_coupling"]),
                    str(coupling_data["efferent_coupling"]),
                    f"{coupling_data['instability']:.4f}",
                    str(r["change_frequency"]),
                    str(r["incoming_calls"]),
                    f"{r['risk_score']:.2f}",
                )
            console.print(table)

        else:
            analyser = CouplingAnalyser(client)
            all_coupling = await analyser.analyze_all()
            scorer = RiskScorer(client)
            all_risks = {r["file_path"]: r for r in await scorer.get_all_risks()}

            table = Table(title="Repository Metrics Summary")
            table.add_column("Module/File Path", style="cyan")
            table.add_column("Ca", style="magenta", justify="right")
            table.add_column("Ce", style="magenta", justify="right")
            table.add_column("Instability", style="yellow", justify="right")
            table.add_column("Churn", style="blue", justify="right")
            table.add_column("Incoming Calls", style="blue", justify="right")
            table.add_column("Risk Score", style="red", justify="right")

            for c in all_coupling:
                fp = c["module"]
                r = all_risks.get(
                    fp,
                    {"risk_score": 0.0, "change_frequency": 0, "incoming_calls": 0},
                )
                table.add_row(
                    fp,
                    str(c["afferent_coupling"]),
                    str(c["efferent_coupling"]),
                    f"{c['instability']:.4f}",
                    str(r["change_frequency"]),
                    str(r["incoming_calls"]),
                    f"{r['risk_score']:.2f}",
                )
            console.print(table)
    finally:
        await client.close()
