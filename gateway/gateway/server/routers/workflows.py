"""Workflow API router."""

from typing import Any
from uuid import UUID as UUIDType

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from gateway.core.blocks import get_block_registry
from gateway.core.workflow import get_workflow_engine
from gateway.core.workflow.engine import _wire_to_dict, workflow_to_dict
from gateway.server.request_context import gateway_user_id
from gateway.storage.database import async_session_factory
from gateway.storage.models import PromptTemplate, WorkflowDraft, WorkflowWire

router = APIRouter()


KIND_DISPLAY = {
    "trigger": ("Flow", "play_circle", "#22C55E"),
    "retrieval": ("RIP", "search", "#2563EB"),
    "prompt": ("AI", "psychology", "#8B5CF6"),
    "model": ("AI", "smart_toy", "#8B5CF6"),
    "tool": ("Tools", "extension", "#0EA5E9"),
    "approval": ("Flow", "verified_user", "#F59E0B"),
    "verification": ("Verification", "checklist", "#10B981"),
    "deployment": ("GitHub", "call_merge", "#2DA44E"),
    "notification": ("Notifications", "notifications", "#EC4899"),
    "memory": ("Memory", "database", "#64748B"),
    "custom": ("Custom", "widgets", "#64748B"),
}


def _palette_card(block: dict[str, Any]) -> dict[str, Any]:
    kind = str(block.get("kind") or "custom")
    category, icon, color = KIND_DISPLAY.get(kind, KIND_DISPLAY["custom"])
    input_schema = block.get("input_schema") or {}
    output_schema = block.get("output_schema") or {}
    return {
        **block,
        "category": block.get("category") or category,
        "display_icon": block.get("display_icon") or icon,
        "display_color": block.get("display_color") or color,
        "input_ports": [
            {"name": name, "schema": schema}
            for name, schema in (input_schema.get("properties") or {}).items()
        ],
        "output_ports": [
            {"name": name, "schema": schema}
            for name, schema in (output_schema.get("properties") or {}).items()
        ] or [{"name": "output", "schema": output_schema}],
    }


class AppendBlockRequest(BaseModel):
    block_id: str
    config: dict[str, Any]
    input_bindings: dict[str, Any]
    position: dict[str, float] | None = None
    display_name: str | None = None
    display_color: str | None = None


class PatchBlockRequest(BaseModel):
    block_id: str | None = None
    config: dict[str, Any] | None = None
    input_bindings: dict[str, Any] | None = None
    position: dict[str, float] | None = None
    display_name: str | None = None
    display_color: str | None = None


class UpdateWorkflowRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    visibility: str | None = None
    canvas_state: dict[str, Any] | None = None


class AddWireRequest(BaseModel):
    source_step_id: str
    target_step_id: str
    target_port: str
    source_port: str = "output"
    mapping: dict[str, Any] | None = None
    wire_color: str = "#3B82F6"
    label: str | None = None


class ReorderBlocksRequest(BaseModel):
    step_order: list[str]


class RunWorkflowRequest(BaseModel):
    query: str
    project_id: str | None = None


class AnswerInputRequest(BaseModel):
    step_id: str
    value: Any


class ApproveRejectRequest(BaseModel):
    approved: bool
    comment: str | None = None
    approver: str | None = None


@router.post("")
async def create_workflow_draft(
    request: Request,
    name: str,
    scope: str = "project",
    project_id: str | None = None,
    description: str | None = None,
    category: str | None = None,
):
    """Create a new workflow draft."""
    try:
        engine = get_workflow_engine()
        user_id = gateway_user_id(request)
        draft = await engine.create_draft(name, user_id, scope, project_id, description, category)
        return workflow_to_dict(draft, [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{draft_id}/blocks")
async def append_block_to_draft(draft_id: UUIDType, body: AppendBlockRequest):
    """Append a block to a workflow draft."""
    try:
        engine = get_workflow_engine()
        draft = await engine.append_block(
            draft_id,
            body.block_id,
            body.config,
            body.input_bindings,
            body.position,
            body.display_name,
            body.display_color,
        )
        wires = await engine.list_wires(draft_id)
        return workflow_to_dict(draft, wires)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{draft_id}/blocks/{step_id}")
async def patch_block(draft_id: UUIDType, step_id: str, body: PatchBlockRequest):
    """Patch a block in a workflow draft."""
    try:
        engine = get_workflow_engine()
        draft = await engine.patch_block(
            draft_id,
            step_id,
            body.block_id,
            body.config,
            body.input_bindings,
            body.position,
            body.display_name,
            body.display_color,
        )
        wires = await engine.list_wires(draft_id)
        return workflow_to_dict(draft, wires)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{draft_id}/blocks/reorder")
async def reorder_blocks(draft_id: UUIDType, body: ReorderBlocksRequest):
    """Reorder blocks in a workflow draft."""
    try:
        engine = get_workflow_engine()
        draft = await engine.reorder_blocks(draft_id, body.step_order)
        wires = await engine.list_wires(draft_id)
        return workflow_to_dict(draft, wires)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{draft_id}/blocks/{step_id}")
async def delete_block(draft_id: UUIDType, step_id: str):
    """Delete a block from a workflow draft."""
    try:
        engine = get_workflow_engine()
        draft = await engine.delete_block(draft_id, step_id)
        wires = await engine.list_wires(draft_id)
        return workflow_to_dict(draft, wires)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{draft_id}")
async def update_workflow(draft_id: UUIDType, body: UpdateWorkflowRequest):
    """Update workflow metadata and canvas viewport state."""
    try:
        engine = get_workflow_engine()
        draft = await engine.update_canvas(
            draft_id,
            canvas_state=body.canvas_state,
            name=body.name,
            description=body.description,
            category=body.category,
            visibility=body.visibility,
        )
        wires = await engine.list_wires(draft_id)
        return workflow_to_dict(draft, wires)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{draft_id}/canvas")
async def get_workflow_canvas(draft_id: UUIDType):
    """Get the complete canvas definition: workflow metadata, blocks, wires, viewport."""
    try:
        engine = get_workflow_engine()
        draft, wires = await engine.get_workflow(draft_id)
        return workflow_to_dict(draft, wires)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{draft_id}/wires")
async def add_wire(draft_id: UUIDType, body: AddWireRequest):
    """Add a canvas wire between two workflow blocks."""
    try:
        engine = get_workflow_engine()
        wire = await engine.add_wire(
            draft_id,
            body.source_step_id,
            body.target_step_id,
            body.target_port,
            body.source_port,
            body.mapping,
            body.wire_color,
            body.label,
        )
        return _wire_to_dict(wire)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{draft_id}/wires")
async def list_wires(draft_id: UUIDType):
    """List canvas wires for a workflow."""
    try:
        engine = get_workflow_engine()
        wires = await engine.list_wires(draft_id)
        return {"wires": [_wire_to_dict(wire) for wire in wires]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{draft_id}/wires/{wire_id}")
async def delete_wire(draft_id: UUIDType, wire_id: UUIDType):
    """Delete one canvas wire."""
    try:
        engine = get_workflow_engine()
        await engine.delete_wire(wire_id)
        wires = await engine.list_wires(draft_id)
        return {"wires": [_wire_to_dict(wire) for wire in wires]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{draft_id}/publish")
async def publish_draft(draft_id: UUIDType):
    """Publish a workflow draft."""
    try:
        engine = get_workflow_engine()
        draft = await engine.publish_draft(draft_id)
        wires = await engine.list_wires(draft_id)
        return workflow_to_dict(draft, wires)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_workflows(request: Request, project_id: str | None = None):
    """List saved workflows."""
    try:
        engine = get_workflow_engine()
        user_id = gateway_user_id(request)
        drafts = await engine.list_drafts(user_id, project_id)
        payload = []
        for draft in drafts:
            wires = await engine.list_wires(draft.id)
            payload.append(workflow_to_dict(draft, wires))
        return payload
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/palette/blocks")
async def list_workflow_blocks():
    """List registered blocks for mobile palette rendering."""
    try:
        registry = get_block_registry()
        blocks = [_palette_card(block.describe()) for block in registry.list()]
        blocks.sort(key=lambda item: (item.get("kind", ""), item.get("name", item.get("id", ""))))
        grouped: dict[str, list[dict[str, Any]]] = {}
        for block in blocks:
            category = block.get("category") or block.get("kind") or "custom"
            grouped.setdefault(str(category), []).append(block)
        return {"blocks": blocks, "categories": grouped, "total": len(blocks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prompt-templates")
async def list_prompt_templates():
    """List saved prompt templates for Ask AI block configuration."""
    try:
        async with async_session_factory() as session:
            templates = (
                await session.execute(select(PromptTemplate).order_by(PromptTemplate.name))
            ).scalars().all()
        return {
            "templates": [
                {
                    "id": template.id,
                    "name": template.name,
                    "version": template.version,
                    "variables": template.variables,
                    "visibility": template.visibility,
                }
                for template in templates
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{draft_id}")
async def get_workflow(draft_id: UUIDType):
    """Get a specific workflow draft."""
    try:
        async with async_session_factory() as session:
            draft = await session.get(WorkflowDraft, draft_id)
            if not draft:
                raise HTTPException(status_code=404, detail="Workflow not found")
            wires = (
                await session.execute(select(WorkflowWire).where(WorkflowWire.workflow_id == draft_id))
            ).scalars().all()
        return workflow_to_dict(draft, list(wires))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{draft_id}/run")
async def run_workflow(draft_id: UUIDType, request: Request, body: RunWorkflowRequest):
    """Run a workflow."""
    try:
        engine = get_workflow_engine()
        user_id = gateway_user_id(request)
        run = await engine.start_run(draft_id, body.query, user_id, body.project_id)
        return {"run_id": run.id, "status": run.status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{draft_id}/runs/{run_id}")
async def get_run_state(run_id: UUIDType):
    """Get workflow run state."""
    try:
        engine = get_workflow_engine()
        state = await engine.get_run_state(run_id)
        return state
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{draft_id}/runs/{run_id}/answer_missing_input")
async def answer_missing_input(run_id: UUIDType, body: AnswerInputRequest):
    """Answer missing input for a workflow step."""
    try:
        engine = get_workflow_engine()
        state = await engine.answer_missing_input(run_id, body.step_id, body.value)
        return state
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{draft_id}/runs/{run_id}/approve")
async def approve_workflow_run(draft_id: UUIDType, run_id: UUIDType, body: ApproveRejectRequest):
    """Approve a paused workflow run at an approval gate."""
    try:
        engine = get_workflow_engine()
        state = await engine.resume_run(run_id, True, body.approver, body.comment)
        return {"run_id": run_id, "status": "resumed", "approved": True, "state": state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{draft_id}/runs/{run_id}/reject")
async def reject_workflow_run(draft_id: UUIDType, run_id: UUIDType, body: ApproveRejectRequest):
    """Reject a paused workflow run at an approval gate."""
    try:
        engine = get_workflow_engine()
        state = await engine.resume_run(run_id, False, body.approver, body.comment)
        return {"run_id": run_id, "status": "rejected", "state": state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
