from __future__ import annotations

from gateway.core.workflow.run_state import RunState


def get_workflow_engine():
	from gateway.core.workflow.engine import get_workflow_engine as _get_workflow_engine

	return _get_workflow_engine()


async def seed_workflows():
	from gateway.core.workflow.engine import seed_workflows as _seed_workflows

	await _seed_workflows()


def __getattr__(name: str):
	if name == "WorkflowEngine":
		from gateway.core.workflow.engine import WorkflowEngine

		return WorkflowEngine
	raise AttributeError(name)


__all__ = ["WorkflowEngine", "get_workflow_engine", "RunState", "seed_workflows"]