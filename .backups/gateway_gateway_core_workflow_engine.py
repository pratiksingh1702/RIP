"""Workflow engine implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID as UUIDType
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm.attributes import flag_modified

from gateway.core.blocks import ExecutionContext, get_block_registry, register_all_blocks
from gateway.core.events import get_event_bus
from gateway.core.workflow.dag import WorkflowDAG
from gateway.core.workflow.input_resolver import resolve_step_inputs
from gateway.core.workflow.run_state import RunState, StepState
from gateway.core.prompts.manager import seed_prompt_templates
from gateway.storage.database import async_session_factory
from gateway.storage.models import WorkflowDraft, WorkflowRun, WorkflowWire


def default_canvas_state() -> dict[str, Any]:
    return {
        "viewport": {
            "zoom": 1.0,
            "center": {"x": 420.0, "y": 320.0},
        }
    }


def _wire_to_dict(wire: WorkflowWire) -> dict[str, Any]:
    return {
        "id": str(wire.id),
        "workflow_id": str(wire.workflow_id),
        "source_step_id": wire.source_step_id,
        "source_port": wire.source_port,
        "target_step_id": wire.target_step_id,
        "target_port": wire.target_port,
        "mapping": wire.mapping or {"type": "direct"},
        "wire_color": wire.wire_color,
        "label": wire.label,
    }


def workflow_to_dict(draft: WorkflowDraft, wires: list[WorkflowWire] | None = None) -> dict[str, Any]:
    return {
        "draft_id": str(draft.id),
        "workflow_id": str(draft.id),
        "name": draft.name,
        "description": draft.description,
        "category": draft.category,
        "version": draft.version,
        "source": draft.source,
        "scope": draft.scope,
        "project_id": draft.project_id,
        "canvas_state": draft.canvas_state or default_canvas_state(),
        "visibility": draft.visibility,
        "status": draft.status,
        "blocks": draft.blocks or [],
        "wires": [_wire_to_dict(wire) for wire in (wires or [])],
        "run_count": draft.run_count,
        "last_run_at": draft.last_run_at.isoformat() if draft.last_run_at else None,
        "avg_duration_ms": draft.avg_duration_ms,
    }


async def seed_workflows():
    """Seed initial workflow templates and prompt templates."""
    await seed_prompt_templates()
    async with async_session_factory() as session:
        existing = (await session.execute(select(WorkflowDraft.id).limit(1))).first()
        if existing is not None:
            return

        # Seed a bug investigation workflow
        bug_workflow = WorkflowDraft(
            id=uuid4(),
            owner_user_id="system",
            scope="global",
            project_id=None,
            name="Bug Investigation",
            status="published",
            blocks=[
                {
                    "step_id": "step_1",
                    "block_id": "context.retrieve",
                    "position": {"x": 120.0, "y": 180.0},
                    "config": {},
                    "input_bindings": {"query": {"source": "trigger_query"}},
                },
                {
                    "step_id": "step_2",
                    "block_id": "terminal.run_tests",
                    "position": {"x": 420.0, "y": 180.0},
                    "config": {},
                    "input_bindings": {"command": {"source": "literal", "value": "npm test"}},
                },
            ],
        )
        session.add(bug_workflow)

        # Seed an architecture overview workflow
        arch_workflow = WorkflowDraft(
            id=uuid4(),
            owner_user_id="system",
            scope="global",
            project_id=None,
            name="Architecture Overview",
            status="published",
            blocks=[
                {
                    "step_id": "step_1",
                    "block_id": "context.retrieve",
                    "position": {"x": 120.0, "y": 180.0},
                    "config": {},
                    "input_bindings": {"query": {"source": "trigger_query"}},
                },
            ],
        )
        session.add(arch_workflow)

        await session.commit()


class WorkflowEngine:
    def __init__(self):
        register_all_blocks()
        self.registry = get_block_registry()
        self.event_bus = get_event_bus()

    async def create_draft(
        self,
        name: str,
        owner_user_id: str,
        scope: str = "project",
        project_id: str | None = None,
        description: str | None = None,
        category: str | None = None,
        canvas_state: dict[str, Any] | None = None,
    ) -> WorkflowDraft:
        async with async_session_factory() as session:
            draft = WorkflowDraft(
                id=uuid4(),
                name=name,
                description=description,
                category=category,
                owner_user_id=owner_user_id,
                scope=scope,
                project_id=project_id,
                canvas_state=canvas_state or default_canvas_state(),
                status="draft",
                blocks=[],
            )
            session.add(draft)
            await session.commit()
            await session.refresh(draft)
            return draft

    async def append_block(
        self,
        draft_id: UUIDType,
        block_id: str,
        config: dict[str, Any],
        input_bindings: dict[str, Any],
        position: dict[str, float] | None = None,
        display_name: str | None = None,
        display_color: str | None = None,
    ) -> WorkflowDraft:
        async with async_session_factory() as session:
            draft = await session.get(WorkflowDraft, draft_id)
            if not draft:
                raise ValueError("Draft not found")

            step_id = f"step_{len(draft.blocks) + 1}"
            new_block = {
                "step_id": step_id,
                "block_id": block_id,
                "position": position or {"x": 120.0 + (len(draft.blocks) * 260.0), "y": 180.0},
                "config": config,
                "input_bindings": input_bindings,
                "display_name": display_name,
                "display_color": display_color,
            }
            draft.blocks = [*draft.blocks, new_block]
            await session.commit()
            await session.refresh(draft)
            return draft

    async def patch_block(
        self,
        draft_id: UUIDType,
        step_id: str,
        block_id: str | None = None,
        config: dict[str, Any] | None = None,
        input_bindings: dict[str, Any] | None = None,
        position: dict[str, float] | None = None,
        display_name: str | None = None,
        display_color: str | None = None,
    ) -> WorkflowDraft:
        async with async_session_factory() as session:
            draft = await session.get(WorkflowDraft, draft_id)
            if not draft:
                raise ValueError("Draft not found")
            
            blocks = [dict(block) for block in draft.blocks]
            for i, block in enumerate(blocks):
                if block["step_id"] == step_id:
                    if block_id is not None:
                        blocks[i]["block_id"] = block_id
                    if config is not None:
                        blocks[i]["config"] = config
                    if input_bindings is not None:
                        blocks[i]["input_bindings"] = input_bindings
                    if position is not None:
                        blocks[i]["position"] = position
                    if display_name is not None:
                        blocks[i]["display_name"] = display_name
                    if display_color is not None:
                        blocks[i]["display_color"] = display_color
                    break
            else:
                raise ValueError("Step not found")

            draft.blocks = blocks
            flag_modified(draft, "blocks")
            await session.commit()
            await session.refresh(draft)
            return draft

    async def delete_block(
        self,
        draft_id: UUIDType,
        step_id: str,
    ) -> WorkflowDraft:
        async with async_session_factory() as session:
            draft = await session.get(WorkflowDraft, draft_id)
            if not draft:
                raise ValueError("Draft not found")
            
            draft.blocks = [block for block in draft.blocks if block["step_id"] != step_id]
            await session.execute(
                delete(WorkflowWire).where(
                    WorkflowWire.workflow_id == draft_id,
                    (WorkflowWire.source_step_id == step_id) | (WorkflowWire.target_step_id == step_id),
                )
            )
            await session.commit()
            await session.refresh(draft)
            return draft

    async def update_canvas(
        self,
        draft_id: UUIDType,
        canvas_state: dict[str, Any] | None = None,
        name: str | None = None,
        description: str | None = None,
        category: str | None = None,
        visibility: str | None = None,
    ) -> WorkflowDraft:
        async with async_session_factory() as session:
            draft = await session.get(WorkflowDraft, draft_id)
            if not draft:
                raise ValueError("Draft not found")
            if canvas_state is not None:
                draft.canvas_state = canvas_state
            if name is not None:
                draft.name = name
            if description is not None:
                draft.description = description
            if category is not None:
                draft.category = category
            if visibility is not None:
                draft.visibility = visibility
            await session.commit()
            await session.refresh(draft)
            return draft

    async def list_wires(self, draft_id: UUIDType) -> list[WorkflowWire]:
        async with async_session_factory() as session:
            return list(
                (
                    await session.execute(
                        select(WorkflowWire).where(WorkflowWire.workflow_id == draft_id)
                    )
                ).scalars().all()
            )

    async def add_wire(
        self,
        draft_id: UUIDType,
        source_step_id: str,
        target_step_id: str,
        target_port: str,
        source_port: str = "output",
        mapping: dict[str, Any] | None = None,
        wire_color: str = "#3B82F6",
        label: str | None = None,
    ) -> WorkflowWire:
        async with async_session_factory() as session:
            draft = await session.get(WorkflowDraft, draft_id)
            if not draft:
                raise ValueError("Draft not found")
            wires = list(
                (
                    await session.execute(
                        select(WorkflowWire).where(WorkflowWire.workflow_id == draft_id)
                    )
                ).scalars().all()
            )
            wire_dicts = [_wire_to_dict(wire) for wire in wires]
            dag = WorkflowDAG(draft.blocks or [], wire_dicts)
            if dag.would_create_cycle(source_step_id, target_step_id):
                raise ValueError("Connection would create a circular dependency")
            wire = WorkflowWire(
                id=uuid4(),
                workflow_id=draft_id,
                source_step_id=source_step_id,
                source_port=source_port,
                target_step_id=target_step_id,
                target_port=target_port,
                mapping=mapping or {"type": "direct"},
                wire_color=wire_color,
                label=label,
            )
            session.add(wire)
            await session.commit()
            await session.refresh(wire)
            return wire

    async def delete_wire(self, wire_id: UUIDType) -> None:
        async with async_session_factory() as session:
            await session.execute(delete(WorkflowWire).where(WorkflowWire.id == wire_id))
            await session.commit()

    async def reorder_blocks(
        self,
        draft_id: UUIDType,
        step_order: list[str],
    ) -> WorkflowDraft:
        async with async_session_factory() as session:
            draft = await session.get(WorkflowDraft, draft_id)
            if not draft:
                raise ValueError("Draft not found")
            
            # Validate all steps are present
            existing_step_ids = {b["step_id"] for b in draft.blocks}
            if not set(step_order).issubset(existing_step_ids):
                raise ValueError("Invalid step order")
            if len(step_order) != len(existing_step_ids):
                raise ValueError("Step order must include all steps")
            
            # Reorder blocks
            ordered_blocks = []
            for step_id in step_order:
                block = next(b for b in draft.blocks if b["step_id"] == step_id)
                ordered_blocks.append(block)
            
            draft.blocks = ordered_blocks
            await session.commit()
            await session.refresh(draft)
            return draft

    async def list_drafts(
        self,
        owner_user_id: str,
        project_id: str | None = None,
    ) -> list[WorkflowDraft]:
        async with async_session_factory() as session:
            query = select(WorkflowDraft).where(
                (WorkflowDraft.owner_user_id == owner_user_id)
                | (WorkflowDraft.owner_user_id == "system")
                | (WorkflowDraft.scope == "global")
            )
            if project_id:
                query = query.where(
                    (WorkflowDraft.project_id == project_id) | (WorkflowDraft.project_id.is_(None))
                )
            query = query.order_by(WorkflowDraft.updated_at.desc())
            return list((await session.execute(query)).scalars().all())

    async def get_workflow(self, draft_id: UUIDType) -> tuple[WorkflowDraft, list[WorkflowWire]]:
        async with async_session_factory() as session:
            draft = await session.get(WorkflowDraft, draft_id)
            if not draft:
                raise ValueError("Draft not found")
            wires = list(
                (
                    await session.execute(
                        select(WorkflowWire).where(WorkflowWire.workflow_id == draft_id)
                    )
                ).scalars().all()
            )
            return draft, wires

    async def publish_draft(self, draft_id: UUIDType) -> WorkflowDraft:
        async with async_session_factory() as session:
            draft = await session.get(WorkflowDraft, draft_id)
            if not draft:
                raise ValueError("Draft not found")
            draft.status = "published"
            await session.commit()
            await session.refresh(draft)
            return draft

    async def start_run(
        self,
        draft_id: UUIDType,
        trigger_query: str,
        user_id: str,
        project_id: str | None = None,
    ) -> WorkflowRun:
        async with async_session_factory() as session:
            draft = await session.get(WorkflowDraft, draft_id)
            if not draft or draft.status != "published":
                raise ValueError("Draft not found or not published")

            run = WorkflowRun(
                id=uuid4(),
                draft_id=draft_id,
                status="pending",
                state=RunState(trigger_query=trigger_query).to_dict(),
            )
            draft.run_count = (draft.run_count or 0) + 1
            draft.last_run_at = datetime.now(UTC)
            session.add(run)
            await session.commit()

            # Start execution in background
            import asyncio
            asyncio.create_task(self._execute_run(run.id, user_id, project_id))

            await session.refresh(run)
            return run

    async def get_run_state(self, run_id: UUIDType) -> dict[str, Any]:
        async with async_session_factory() as session:
            run = await session.get(WorkflowRun, run_id)
            if not run:
                raise ValueError("Run not found")
            return run.state

    async def resume_run(
        self,
        run_id: UUIDType,
        approved: bool,
        approver: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        async with async_session_factory() as session:
            run = await session.get(WorkflowRun, run_id)
            if not run:
                raise ValueError("Run not found")

            state = RunState.from_dict(run.state)
            approval_step = None
            for step_state in state.step_states.values():
                if step_state.block_id == "workflow.approval" and step_state.status == "awaiting_approval":
                    approval_step = step_state
                    break
            if approval_step is None:
                raise ValueError("No approval is awaiting a decision")

            if not approved:
                approval_step.status = "failed"
                approval_step.error = f"Rejected: {comment or 'No comment'}"
                approval_step.completed_at = datetime.now(UTC).isoformat()
                run.status = "failed"
                run.completed_at = datetime.now(UTC)
                state.final_output = {"approved": False, "comment": comment, "approver": approver}
                run.state = state.to_dict()
                await session.commit()
                return run.state

            approval_step.status = "completed"
            approval_step.output = {"approved": True, "approver": approver, "comment": comment}
            approval_step.completed_at = datetime.now(UTC).isoformat()
            run.status = "running"
            run.state = state.to_dict()
            await session.commit()

            import asyncio
            asyncio.create_task(self._execute_run(run.id, None, None))
            return run.state

    async def answer_missing_input(
        self,
        run_id: UUIDType,
        step_id: str,
        value: Any,
    ) -> dict[str, Any]:
        async with async_session_factory() as session:
            run = await session.get(WorkflowRun, run_id)
            if not run:
                raise ValueError("Run not found")

            state = RunState.from_dict(run.state)
            if step_id in state.missing_inputs:
                input_key = state.missing_inputs[step_id]
                state.provided_inputs[f"{step_id}.{input_key}"] = value
                del state.missing_inputs[step_id]
                if step_id in state.step_states:
                    state.step_states[step_id].status = "pending"
                    state.step_states[step_id].error = None

            # Update state and resume
            run.state = state.to_dict()
            await session.commit()

            import asyncio
            asyncio.create_task(self._execute_run(run.id, None, None))

            return run.state

    async def _execute_run(
        self,
        run_id: UUIDType,
        user_id: str | None,
        project_id: str | None,
    ):
        async with async_session_factory() as session:
            run = await session.get(WorkflowRun, run_id)
            if not run:
                return

            draft = await session.get(WorkflowDraft, run.draft_id)
            if not draft:
                return

            state = RunState.from_dict(run.state)
            wires = list(
                (
                    await session.execute(
                        select(WorkflowWire).where(WorkflowWire.workflow_id == draft.id)
                    )
                ).scalars().all()
            )
            wire_dicts = [_wire_to_dict(wire) for wire in wires]
            dag = WorkflowDAG(draft.blocks, wire_dicts)

            run.status = "running"
            run.started_at = datetime.now(UTC)
            await session.commit()

            try:
                for step_id in dag.topological_order():
                    block = next(b for b in draft.blocks if b["step_id"] == step_id)
                    step_state = state.step_states.get(step_id)
                    if not step_state:
                        step_state = StepState(
                            step_id=step_id,
                            block_id=block["block_id"],
                        )
                        state.step_states[step_id] = step_state

                    if step_state.status != "pending":
                        continue

                    step_state.status = "running"
                    step_state.started_at = datetime.now(UTC).isoformat()

                    if step_state.block_id == "workflow.approval":
                        step_state.status = "awaiting_approval"
                        step_state.inputs = dict(block.get("input_bindings", {}))
                        run.status = "awaiting_approval"
                        run.state = state.to_dict()
                        await session.commit()
                        await self.event_bus.publish(
                            "approval_required",
                            workflow_run_id=str(run_id),
                            payload={"step_id": step_id, "block_id": step_state.block_id},
                        )
                        return

                    block_config = block.get("config", {})
                    input_bindings = block.get("input_bindings", {})
                    inputs, missing_key = resolve_step_inputs(
                        step_id,
                        input_bindings,
                        wire_dicts,
                        state,
                    )
                    step_state.inputs = inputs
                    if missing_key:
                        state.missing_inputs[step_id] = missing_key
                        step_state.status = "awaiting_input"
                        run.status = "awaiting_input"
                        run.state = state.to_dict()
                        await session.commit()
                        return

                    # Run block
                    block_instance = self.registry.get(step_state.block_id)
                    if block_instance:
                        ctx = ExecutionContext(
                            session_id=str(run_id),
                            workflow_run_id=str(run_id),
                            project_id=project_id,
                            user_id=user_id,
                        )
                        result = await block_instance.run(ctx, inputs, block_config)
                        if result.ok:
                            step_state.status = "completed"
                            step_state.output = result.output
                        else:
                            step_state.status = "failed"
                            step_state.error = result.error
                    else:
                        step_state.status = "failed"
                        step_state.error = f"Block {step_state.block_id} not found"

                    step_state.completed_at = datetime.now(UTC).isoformat()

                    # Update run state
                    run.state = state.to_dict()
                    await session.commit()

                    if step_state.status == "failed":
                        break

                if any(s.status == "awaiting_input" for s in state.step_states.values()):
                    run.status = "awaiting_input"
                elif any(s.status == "awaiting_approval" for s in state.step_states.values()):
                    run.status = "awaiting_approval"
                elif not any(s.status == "failed" for s in state.step_states.values()):
                    run.status = "completed"
                    final_step = list(state.step_states.values())[-1] if state.step_states else None
                    state.final_output = final_step.output if final_step else None
                else:
                    run.status = "failed"

                if run.status in {"completed", "failed"}:
                    run.completed_at = datetime.now(UTC)
                run.state = state.to_dict()
                await session.commit()

                await self.event_bus.publish(
                    "workflow.completed",
                    workflow_run_id=str(run_id),
                    payload={"status": run.status},
                )
            except Exception as e:
                run.status = "failed"
                await session.commit()
                await self.event_bus.publish(
                    "workflow.failed",
                    workflow_run_id=str(run_id),
                    payload={"error": str(e)},
                )


_workflow_engine = WorkflowEngine()


def get_workflow_engine() -> WorkflowEngine:
    return _workflow_engine
