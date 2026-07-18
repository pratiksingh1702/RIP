"""Agent Runtime API endpoints."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, is_dataclass
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
    project_root: str | None = None
    max_turns: int = 50


class AgentApproveRequest(BaseModel):
    run_id: str
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
        _agent_runs[run_id] = {
            "id": run_id,
            "status": "running",
            "steps": [],
            "query": body.query,
            "project_id": project_id,
            "pending_approval": None,
        }

        runtime = get_agent_runtime()
        asyncio.create_task(_run_agent_background(run_id, runtime, body.query, llm_config, project_id, user_id, body.project_root))

        return {"run_id": run_id, "status": "running"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _run_agent_background(run_id: str, runtime, query: str, llm_config, project_id: str | None, user_id: str, project_root: str | None):
    try:
        async def update_run_state(rid: str, updates: dict[str, Any]) -> None:
            current = _agent_runs.setdefault(rid, {"id": rid, "query": query})
            current.update(_jsonable(updates))
            current.setdefault("id", rid)
            current.setdefault("query", query)

        result = await runtime.execute(
            query,
            llm_config,
            project_id,
            user_id,
            project_root=project_root,
            run_id=run_id,
            on_state_change=update_run_state,
        )
        _agent_runs[run_id] = {
            "id": run_id,
            "status": result.status,
            "query": query,
            "steps": _jsonable(result.steps),
            "changes_made": result.changes_made,
            "verification": result.verification,
            "summary": result.summary,
            "tokens_total": result.tokens_total,
            "duration_seconds": result.duration_seconds,
            "error": result.error,
            "project_id": project_id,
            "project_root": _agent_runs.get(run_id, {}).get("project_root"),
            "pending_approval": None,
        }
    except Exception as e:
        _agent_runs[run_id] = {"id": run_id, "status": "failed", "query": query, "error": str(e), "pending_approval": None}


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


@router.post("/approve")
async def approve_agent_tool(body: AgentApproveRequest):
    """Approve or reject a pending agent tool execution."""
    runtime = get_agent_runtime()
    runtime.approve_tool(body.run_id, body.approved)
    if body.run_id in _agent_runs:
        _agent_runs[body.run_id]["last_approval"] = {"approved": body.approved, "comment": body.comment}
    return {"run_id": body.run_id, "approved": body.approved}


@router.get("/runs/{run_id}")
async def get_agent_run(run_id: str):
    """Get the current state of an agent run."""
    run = _agent_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    pending = get_agent_runtime().pending_approval(run_id)
    if pending:
        run = dict(run)
        run["pending_approval"] = pending
    return run


@router.get("/runs")
async def list_agent_runs():
    """List all agent runs."""
    return {"runs": [{"id": k, "status": v.get("status"), "query": v.get("query", "")[:100], "pending_approval": v.get("pending_approval")} for k, v in _agent_runs.items()]}


@router.get("/tools")
async def list_agent_tools():
    """List available tools for the agent."""
    runtime = get_agent_runtime()
    tools = runtime.tool_registry.get_for_llm()
    return {"tools": tools}
