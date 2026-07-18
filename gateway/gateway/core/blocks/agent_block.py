"""Agent block that runs the full Agent Runtime as a workflow step."""

from __future__ import annotations

from typing import Any

from gateway.core.agent import get_agent_runtime
from gateway.core.blocks.base import Block, BlockKind, BlockResult, ExecutionContext
from gateway.core.llm_pool import get_llm_router


class AgentBlock(Block):
    id = "agent.execute"
    kind = BlockKind.MODEL
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The engineering task to perform"},
            "model_preference": {"type": "string", "description": "LLM config ID to use"},
            "max_turns": {"type": "integer", "default": 50},
        },
        "required": ["query"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "steps": {"type": "array"},
            "changes_made": {"type": "array"},
            "verification": {"type": "object"},
            "tokens_total": {"type": "integer"},
            "duration_seconds": {"type": "number"},
            "status": {"type": "string"},
        },
    }
    config_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "nullable": True},
            "provider": {"type": "string", "nullable": True},
            "project_root": {"type": "string", "nullable": True},
        },
    }
    requires_capabilities = ["LLM", "NETWORK"]

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            query = str(inputs["query"])
            model_pref = None
            mp = inputs.get("model_preference")
            if isinstance(mp, dict):
                model_pref = mp.get("value")
            elif isinstance(mp, str) and mp:
                model_pref = mp

            router = get_llm_router()
            llm_config = await router.get_config(
                config_id=model_pref or config.get("model"),
                provider=config.get("provider"),
                model=config.get("model"),
            )

            runtime = get_agent_runtime()
            result = await runtime.execute(
                query=query,
                llm_config=llm_config,
                project_id=ctx.project_id,
                user_id=ctx.user_id or "",
                project_root=config.get("project_root"),
                run_id=ctx.workflow_run_id,
            )

            return BlockResult(ok=result.status == "completed", output={
                "summary": result.summary,
                "steps": result.steps,
                "changes_made": result.changes_made,
                "verification": result.verification,
                "tokens_total": result.tokens_total,
                "duration_seconds": result.duration_seconds,
                "status": result.status,
            })
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id, "kind": self.kind.value,
            "name": "AI Agent", "description": "Autonomous AI agent that plans, edits, and verifies code changes",
            "category": "AI", "display_icon": "🤖", "display_color": "#8B5CF6",
            "input_schema": self.input_schema, "output_schema": self.output_schema,
        }
