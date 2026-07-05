"""Workflow CLI commands."""
import asyncio
import json
from uuid import UUID

import typer

from gateway.core.workflow import get_workflow_engine
from gateway.server.request_context import gateway_user_id

workflow_app = typer.Typer(help="Manage and run workflows")


@workflow_app.command("create")
def create_workflow(name: str, scope: str = "project", project_id: str | None = None):
    """Create a new workflow draft."""

    async def _run():
        engine = get_workflow_engine()
        draft = await engine.create_draft(name, "cli", scope, project_id)
        typer.echo(f"Created workflow draft: {draft.id} - {draft.name}")

    asyncio.run(_run())


@workflow_app.command("list")
def list_workflows(project_id: str | None = None):
    """List all workflow drafts."""

    async def _run():
        engine = get_workflow_engine()
        drafts = await engine.list_drafts("cli", project_id)
        typer.echo("Workflow drafts:")
        for draft in drafts:
            typer.echo(
                f"  {draft.id} - {draft.name} (status: {draft.status}, {len(draft.blocks)} blocks)"
            )

    asyncio.run(_run())


@workflow_app.command("add-block")
def add_block(
    draft_id: UUID, block_id: str, config: str = "{}", input_bindings: str = "{}"
):
    """Append a block to a workflow draft."""

    async def _run():
        engine = get_workflow_engine()
        config_dict = json.loads(config)
        input_bindings_dict = json.loads(input_bindings)
        draft = await engine.append_block(
            draft_id, block_id, config_dict, input_bindings_dict
        )
        typer.echo(f"Added block {block_id} to draft {draft.id}")

    asyncio.run(_run())


@workflow_app.command("publish")
def publish_workflow(draft_id: UUID):
    """Publish a workflow draft."""

    async def _run():
        engine = get_workflow_engine()
        draft = await engine.publish_draft(draft_id)
        typer.echo(f"Published workflow: {draft.id}")

    asyncio.run(_run())


@workflow_app.command("run")
def run_workflow(draft_id: UUID, query: str, project_id: str | None = None):
    """Run a workflow."""

    async def _run():
        engine = get_workflow_engine()
        run = await engine.start_run(draft_id, query, "cli", project_id)
        typer.echo(f"Started workflow run: {run.id}")
        # Poll for completion
        while True:
            state = await engine.get_run_state(run.id)
            typer.echo(f"Status: {state.status}")
            if state.status in ["completed", "failed", "rejected"]:
                if state.final_output:
                    typer.echo("Final output:")
                    typer.echo(json.dumps(state.final_output, indent=2))
                if state.error:
                    typer.echo(f"Error: {state.error}", err=True)
                break
            await asyncio.sleep(1)

    asyncio.run(_run())
