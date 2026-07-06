from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from gateway.core.blocks.context_retrieve import ContextRetrieveBlock
from gateway.core.blocks.github_deployment import GitHubOpenPrBlock
from gateway.core.blocks.terminal import TerminalRunTestsBlock
from gateway.core.events.bus import EventBus
from gateway.core.workflow.dag import WorkflowDAG
from gateway.core.workflow.run_state import RunState, StepState
from gateway.core.workflow.input_resolver import resolve_step_inputs
from gateway.core.workflow.engine import WorkflowEngine


class _Session:
    def __init__(self) -> None:
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        return None


def _session_factory():
    return _Session()


@pytest.mark.asyncio
async def test_event_bus_publish_subscribe_order(monkeypatch):
    import gateway.core.events.bus as bus_module

    monkeypatch.setattr(bus_module, "async_session_factory", _session_factory)
    bus = EventBus()
    subscription = bus.subscribe("workflow.step")
    first_task = asyncio.create_task(subscription.__anext__())
    await asyncio.sleep(0)

    first = await bus.publish("workflow.step", payload={"index": 1})
    received_first = await asyncio.wait_for(first_task, timeout=1)

    second_task = asyncio.create_task(subscription.__anext__())
    second = await bus.publish("workflow.step", payload={"index": 2})
    received_second = await asyncio.wait_for(second_task, timeout=1)
    await subscription.aclose()

    assert [received_first.id, received_second.id] == [first.id, second.id]
    assert [received_first.payload["index"], received_second.payload["index"]] == [1, 2]


@pytest.mark.asyncio
async def test_context_retrieve_block_matches_direct_pipeline(monkeypatch):
    expected = {"context": [{"text": "same"}], "intent": "explain", "domain": "code"}

    class Pipeline:
        async def run(self, **kwargs):
            return expected

    import gateway.core.blocks.context_retrieve as context_module

    monkeypatch.setattr(context_module, "get_context_pipeline", lambda: Pipeline())
    result = await ContextRetrieveBlock().run(
        SimpleNamespace(session_id="s1", project_id="p1", user_id="u1"),
        {"query": "explain auth"},
        {},
    )

    assert result.ok is True
    assert result.output == expected


def test_linear_dag_execution_order():
    dag = WorkflowDAG(
        [
            {"step_id": "step_1", "block_id": "context.retrieve"},
            {"step_id": "step_2", "block_id": "prompt.ask_ai"},
            {"step_id": "step_3", "block_id": "terminal.run_tests"},
        ]
    )

    assert dag.topological_order() == ["step_1", "step_2", "step_3"]


def test_run_state_round_trips_bindings_and_missing_input_answers():
    state = RunState(trigger_query="fix login")
    state.step_states["step_1"] = StepState(
        step_id="step_1",
        block_id="context.retrieve",
        status="completed",
        output={"content": "retrieved"},
    )
    state.missing_inputs["step_2"] = "command"
    state.provided_inputs["step_2.command"] = "pytest"

    restored = RunState.from_dict(state.to_dict())

    assert restored.trigger_query == "fix login"
    assert restored.step_states["step_1"].output["content"] == "retrieved"
    assert restored.missing_inputs["step_2"] == "command"
    assert restored.provided_inputs["step_2.command"] == "pytest"


def test_resolve_step_inputs_supports_prompt_variable_object_bindings():
    state = RunState(trigger_query="explain auth")
    state.step_states["step_1"] = StepState(
        step_id="step_1",
        block_id="context.retrieve",
        status="completed",
        output={"content": "retrieved context"},
    )

    inputs, missing = resolve_step_inputs(
        "step_2",
        {
            "prompt_id": {"source": "literal", "value": "Explain Flow"},
            "variables": {
                "source": "object",
                "fields": {
                    "query": {"source": "trigger_query"},
                    "context": {"source": "step_output", "step_id": "step_1", "field": "content"},
                },
            },
        },
        [],
        state,
    )

    assert missing is None
    assert inputs["prompt_id"] == "Explain Flow"
    assert inputs["variables"] == {"query": "explain auth", "context": "retrieved context"}


@pytest.mark.asyncio
async def test_terminal_block_rejects_non_allowlisted_command():
    result = await TerminalRunTestsBlock().run(
        SimpleNamespace(),
        {"command": "git push origin main"},
        {},
    )

    assert result.ok is False
    assert "allow-listed" in result.error


@pytest.mark.asyncio
async def test_deployment_block_refuses_when_policy_blocks(monkeypatch):
    import gateway.core.blocks.github_deployment as deployment_module

    async def blocked(action, repo=None):
        return False, "blocked by policy"

    monkeypatch.setattr(deployment_module, "workflow_action_allowed", blocked)
    result = await GitHubOpenPrBlock().run(
        SimpleNamespace(project_id="project"),
        {"repo": "owner/repo", "branch": "feature", "title": "PR"},
        {},
    )

    assert result.ok is False
    assert result.error == "blocked by policy"


@pytest.mark.asyncio
async def test_approval_resume_marks_gate_completed(monkeypatch):
    run_id = uuid4()
    state = RunState()
    state.step_states["step_1"] = StepState(
        step_id="step_1",
        block_id="workflow.approval",
        status="awaiting_approval",
    )
    run = SimpleNamespace(
        id=run_id,
        state=state.to_dict(),
        status="awaiting_approval",
        completed_at=None,
    )

    class Session(_Session):
        async def get(self, model, item_id):
            assert item_id == run_id
            return run

    import asyncio as py_asyncio
    import gateway.core.workflow.engine as engine_module

    monkeypatch.setattr(engine_module, "async_session_factory", lambda: Session())
    engine = WorkflowEngine()

    async def no_execute(*args, **kwargs):
        return None

    monkeypatch.setattr(engine, "_execute_run", no_execute)
    resumed = await engine.resume_run(run_id, True, approver="mobile", comment="ship it")

    approval = resumed["step_states"]["step_1"]
    assert run.status == "running"
    assert approval["status"] == "completed"
    assert approval["output"]["approved"] is True


@pytest.mark.asyncio
async def test_execute_run_resolves_trigger_query_binding(monkeypatch):
    run_id = uuid4()
    draft_id = uuid4()
    run = SimpleNamespace(
        id=run_id,
        draft_id=draft_id,
        state=RunState(trigger_query="trace parser").to_dict(),
        status="pending",
        started_at=None,
        completed_at=None,
    )
    draft = SimpleNamespace(
        id=draft_id,
        status="published",
        blocks=[
            {
                "step_id": "step_1",
                "block_id": "context.retrieve",
                "config": {},
                "input_bindings": {"query": {"source": "trigger_query"}},
            }
        ],
    )
    seen_inputs: dict[str, str] = {}

    class _Block:
        async def run(self, ctx, inputs, config):
            seen_inputs.update(inputs)
            return SimpleNamespace(ok=True, output={"content": "ok"}, error=None)

    class Session(_Session):
        async def get(self, model, item_id):
            if item_id == run_id:
                return run
            if item_id == draft_id:
                return draft
            return None

    import asyncio as py_asyncio
    import gateway.core.workflow.engine as engine_module

    monkeypatch.setattr(engine_module, "async_session_factory", lambda: Session())
    engine = WorkflowEngine()
    monkeypatch.setattr(engine.registry, "get", lambda _block_id: _Block())
    monkeypatch.setattr(engine.event_bus, "publish", lambda *args, **kwargs: asyncio.sleep(0))

    await engine._execute_run(run_id, "u1", "p1")

    assert seen_inputs["query"] == "trace parser"


@pytest.mark.asyncio
async def test_execute_run_resolves_step_output_binding(monkeypatch):
    run_id = uuid4()
    draft_id = uuid4()
    run = SimpleNamespace(
        id=run_id,
        draft_id=draft_id,
        state=RunState(trigger_query="context").to_dict(),
        status="pending",
        started_at=None,
        completed_at=None,
    )
    draft = SimpleNamespace(
        id=draft_id,
        status="published",
        blocks=[
            {
                "step_id": "step_1",
                "block_id": "context.retrieve",
                "config": {},
                "input_bindings": {"query": {"source": "trigger_query"}},
            },
            {
                "step_id": "step_2",
                "block_id": "prompt.ask_ai",
                "config": {},
                "input_bindings": {
                    "query": {"source": "step_output", "step_id": "step_1", "field": "content"}
                },
            },
        ],
    )

    step2_inputs: dict[str, str] = {}

    class _Step1:
        async def run(self, ctx, inputs, config):
            return SimpleNamespace(ok=True, output={"content": "parsed-output"}, error=None)

    class _Step2:
        async def run(self, ctx, inputs, config):
            step2_inputs.update(inputs)
            return SimpleNamespace(ok=True, output={"summary": "done"}, error=None)

    class Session(_Session):
        async def get(self, model, item_id):
            if item_id == run_id:
                return run
            if item_id == draft_id:
                return draft
            return None

    import gateway.core.workflow.engine as engine_module

    monkeypatch.setattr(engine_module, "async_session_factory", lambda: Session())
    engine = WorkflowEngine()
    monkeypatch.setattr(
        engine.registry,
        "get",
        lambda block_id: _Step1() if block_id == "context.retrieve" else _Step2(),
    )
    monkeypatch.setattr(engine.event_bus, "publish", lambda *args, **kwargs: asyncio.sleep(0))

    await engine._execute_run(run_id, "u1", "p1")

    assert step2_inputs["query"] == "parsed-output"


@pytest.mark.asyncio
async def test_answer_missing_input_round_trip(monkeypatch):
    run_id = uuid4()
    state = RunState(trigger_query="")
    state.missing_inputs["step_1"] = "command"
    state.step_states["step_1"] = StepState(
        step_id="step_1",
        block_id="terminal.run_tests",
        status="awaiting_input",
        error="missing input",
    )
    run = SimpleNamespace(
        id=run_id,
        state=state.to_dict(),
        status="awaiting_input",
        completed_at=None,
    )

    class Session(_Session):
        async def get(self, model, item_id):
            assert item_id == run_id
            return run

    import asyncio as py_asyncio
    import gateway.core.workflow.engine as engine_module

    monkeypatch.setattr(engine_module, "async_session_factory", lambda: Session())
    scheduled: list[str] = []

    def _fake_create_task(coro):
        scheduled.append("scheduled")
        coro.close()
        return SimpleNamespace()

    monkeypatch.setattr(py_asyncio, "create_task", _fake_create_task)

    engine = WorkflowEngine()
    updated = await engine.answer_missing_input(run_id, "step_1", "pytest -q")

    assert "step_1" not in updated["missing_inputs"]
    assert updated["provided_inputs"]["step_1.command"] == "pytest -q"
    assert updated["step_states"]["step_1"]["status"] == "pending"
    assert len(scheduled) == 1
