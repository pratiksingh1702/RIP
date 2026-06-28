"""Analysis API router."""

from __future__ import annotations

import time

from fastapi import APIRouter, Query

from core.analysis.coupling_analyser import CouplingAnalyser
from core.analysis.dead_code_detector import DeadCodeDetector
from core.analysis.risk_scorer import RiskScorer
from core.graph.client import Neo4jClient
from server.config import get_settings
from server.schemas.responses import ApiEnvelope

router = APIRouter(tags=["analysis"])


@router.get("/dead-code", response_model=ApiEnvelope)
async def dead_code_endpoint(
    type: str = Query("all", description="functions|classes|all"),
    project_id: str = Query(None, description="Project id to detect dead code in"),
) -> ApiEnvelope:
    start = time.perf_counter()
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        detector = DeadCodeDetector(client)
        unused = await detector.detect(entity_type=type, project_id=project_id)
    finally:
        await client.close()

    return ApiEnvelope(
        success=True,
        data={
            "unused": unused,
            "total_count": len(unused),
        },
        error=None,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )


@router.get("/metrics", response_model=ApiEnvelope)
async def metrics_endpoint(
    module: str | None = Query(None, description="Specific module/file path"),
    top_risk: int | None = Query(None, description="Limit to top risk files"),
    project_id: str = Query(None, description="Project id to get metrics for"),
) -> ApiEnvelope:
    start = time.perf_counter()
    settings = get_settings()
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        if module:
            analyser = CouplingAnalyser(client)
            coupling_data = await analyser.analyze_module(module, project_id=project_id)
            scorer = RiskScorer(client)
            risk_data = await scorer.get_file_risk(module, project_id=project_id)
            result = [
                {
                    **coupling_data,
                    "risk_score": risk_data["risk_score"],
                    "change_frequency": risk_data["change_frequency"],
                    "incoming_calls": risk_data["incoming_calls"],
                }
            ]
        elif top_risk is not None:
            scorer = RiskScorer(client)
            all_risks = await scorer.get_all_risks(project_id=project_id)
            top_risky = all_risks[:top_risk]

            analyser = CouplingAnalyser(client)
            result = []
            for r in top_risky:
                coupling_data = await analyser.analyze_module(r["file_path"], project_id=project_id)
                result.append({**coupling_data, **r})
        else:
            analyser = CouplingAnalyser(client)
            all_coupling = await analyser.analyze_all(project_id=project_id)
            scorer = RiskScorer(client)
            all_risks = {r["file_path"]: r for r in await scorer.get_all_risks(project_id=project_id)}

            result = []
            for c in all_coupling:
                fp = c["module"]
                r = all_risks.get(
                    fp,
                    {"risk_score": 0.0, "change_frequency": 0, "incoming_calls": 0},
                )
                result.append(
                    {
                        **c,
                        "risk_score": r["risk_score"],
                        "change_frequency": r["change_frequency"],
                        "incoming_calls": r["incoming_calls"],
                    }
                )
    finally:
        await client.close()

    return ApiEnvelope(
        success=True,
        data={
            "modules": result,
        },
        error=None,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )
