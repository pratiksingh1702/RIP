"""Supervisor REST API router for real-time task oversight and signal control."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from gateway.core.agent.supervisor import supervisor_agent
from gateway.core.agent.status_log import status_log
from gateway.core.agent.signal_channel import SignalType
from gateway.core.agent.guardrails import guardrail_checker
from gateway.core.agent.content_policy import content_policy

router = APIRouter(prefix="/gateway/api/supervisor", tags=["supervisor"])


class SupervisorChatRequest(BaseModel):
    task_id: str
    message: str
    llm_config_id: str | None = None
    provider: str | None = None
    model: str | None = None


class SupervisorSignalRequest(BaseModel):
    task_id: str
    signal_type: SignalType
    step_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/chat")
async def supervisor_chat(req: SupervisorChatRequest) -> dict[str, Any]:
    """Ask the Supervisor Agent a question about active task execution."""
    clean_message = content_policy.sanitize_user_input(req.message)

    # Resolve LLMConfig from the LLM router pool based on user preference
    from gateway.core.llm_pool.router import get_llm_router
    llm_router = get_llm_router()
    try:
        llm_cfg = await llm_router.get_config(
            config_id=req.llm_config_id,
            provider=req.provider,
            model=req.model,
        )
    except Exception:
        llm_cfg = None

    response = await supervisor_agent.answer_user_query(req.task_id, clean_message, llm_config=llm_cfg)
    return response


@router.post("/signal")
async def transmit_signal(req: SupervisorSignalRequest) -> dict[str, Any]:
    """Transmit a control signal (pause, resume, retask, rollback, abort) to Main Agent."""
    if req.signal_type == SignalType.MODIFY_PLAN:
        new_subtasks = req.payload.get("new_subtasks", [])
        validation = guardrail_checker.validate_retask_plan(req.task_id, new_subtasks)
        if not validation.allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Retask plan blocked by guardrails: {', '.join(validation.violations)}",
            )

    signal = await supervisor_agent.issue_signal(
        task_id=req.task_id,
        signal_type=req.signal_type,
        step_id=req.step_id,
        payload=req.payload,
        issued_by="user",
    )
    return {"status": "ok", "signal_id": signal.signal_id, "acknowledged": False}


@router.get("/status/{task_id}")
async def get_task_status(task_id: str) -> dict[str, Any]:
    """Fetch task progress and log event history."""
    progress = await status_log.get_task_progress(task_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Task not found")
    
    events = await status_log.get_events(task_id)
    return {
        "progress": progress.model_dump(mode="json"),
        "events": [e.model_dump(mode="json") for e in events],
    }
