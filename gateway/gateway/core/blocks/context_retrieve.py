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
            "session_id": {"type": "string"},
            "tokens_used": {"type": "integer"},
        },
    }
    config_schema = {}
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            pipeline = get_context_pipeline()
            # CORRECT METHOD: pipeline.get_context() with 'task' parameter
            result = await pipeline.get_context(
                task=inputs.get("query", ""),
                max_tokens=int(config.get("max_tokens", 8000)),
                role=str(config.get("role", "developer")),
                trace_session_id=ctx.session_id or ctx.workflow_run_id,
            )
            # Convert ContextPackage items to serializable dicts
            context_items = []
            if result.context:
                for item in result.context:
                    context_items.append({
                        "source": str(item.source),
                        "query_type": str(item.query_type),
                        "content": str(item.content),
                        "metadata": item.metadata,
                        "score": float(item.score) if item.score else 0.0,
                    })
            return BlockResult(
                ok=True,
                output={
                    "context": context_items,
                    "intent": str(result.intent),
                    "domain": str(result.domain) if result.domain else None,
                    "session_id": str(result.session_id),
                    "tokens_used": int(result.tokens_used),
                },
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
