"""Context retrieve block."""

from __future__ import annotations

from typing import Any

from gateway.core.blocks.base import Block, BlockKind, BlockResult, ExecutionContext
from gateway.core.pipeline import get_context_pipeline


class ContextRetrieveBlock(Block):
    id = "context.retrieve"
    kind = BlockKind.RETRIEVAL
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "project_id": {"type": "string", "nullable": True},
            "user_id": {"type": "string", "nullable": True},
        },
        "required": ["query"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "context": {"type": "array"},
            "intent": {"type": "string"},
            "domain": {"type": "string", "nullable": True},
        },
    }
    config_schema = {}
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            pipeline = get_context_pipeline()
            result = await pipeline.run(
                query=inputs["query"],
                project_id=inputs.get("project_id") or ctx.project_id,
                user_id=inputs.get("user_id") or ctx.user_id,
                session_id=ctx.session_id,
            )
            return BlockResult(
                ok=True,
                output=result,
            )
        except Exception as e:
            return BlockResult(
                ok=False,
                error=str(e),
            )

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": "Context Retrieve",
            "description": "Retrieves context using the existing Gateway pipeline",
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }
