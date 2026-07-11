"""Agent Runtime API endpoints."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID as UUIDType, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from gateway.core.agent import get_agent_runtime
from gateway.core.llm_pool import get_llm_router
from gateway.server.request_context import gateway_user_id

router = APIRouter()

_agent_runs: dict[str, dict] = {}


class AgentExecuteRequest(BaseModel):
    query: str
    model_preference: str | None = None
    project_id: str | None = None
    max_turns: int = 50


class AgentApproveRequest(BaseModel):
    approved: bool
    comment: str | None = None


@router.post("/execute")
async def execute_agent(request: Request, body: AgentExecuteRequest):
    """Execute an AI agent to perform an engineering task."""
    try:
        user_id = gateway_user_id(request)
        project_id = body.project_id

        router = get_llm_router()
        llm_config = await router.get_config(config_id=body.model_preference or "primary")

        run_id = str(uuid4())
        _agent_runs[run_id] = {"status": "running", "steps": [], "query": body.query}

        runtime = get_agent_runtime()
        asyncio.create_task(_run_agent_background(run_id, runtime, body.query, llm_config, project_id, user_id))

        return {"run_id": run_id, "status": "running"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _run_agent_background(run_id: str, runtime, query: str, llm_config, project_id: str, user_id: str):
    try:
        result = await runtime.execute(query, llm_config, project_id, user_id)
        _agent_runs[run_id] = {
            "status": result.status,
            "query": query,
            "steps": result.steps,
            "changes_made": result.changes_made,
            "verification": result.verification,
            "summary": result.summary,
            "tokens_total": result.tokens_total,
            "duration_seconds": result.duration_seconds,
            "error": result.error,
        }
    except Exception as e:
        _agent_runs[run_id] = {"status": "failed", "error": str(e)}


@router.get("/runs/{run_id}")
async def get_agent_run(run_id: str):
    """Get the current state of an agent run."""
    run = _agent_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs")
async def list_agent_runs():
    """List all agent runs."""
    return {"runs": [{"id": k, "status": v.get("status"), "query": v.get("query", "")[:100]} for k, v in _agent_runs.items()]}


@router.get("/tools")
async def list_agent_tools():
    """List available tools for the agent."""
    runtime = get_agent_runtime()
    tools = runtime.tool_registry.get_for_llm()
    return {"tools": tools}
