"""Tool block wrapping a source."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gateway.core.blocks.base import Block, BlockKind, BlockResult, ExecutionContext
from gateway.core.sources.base import BaseSource


@dataclass
class ToolBlock(Block):
    source: BaseSource
    _id: str
    _kind: BlockKind = BlockKind.TOOL
    _requires_capabilities: list[str] = None

    def __init__(self, source: BaseSource):
        self.source = source
        self._id = f"tool.{getattr(source, 'id', source.name)}"
        self._requires_capabilities = []
        if hasattr(source, 'requires_capabilities'):
            self._requires_capabilities = source.requires_capabilities

    @property
    def id(self) -> str:
        return self._id

    @property
    def kind(self) -> BlockKind:
        return self._kind

    @property
    def input_schema(self) -> dict[str, Any]:
        if hasattr(self.source, 'input_schema'):
            return self.source.input_schema
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "query_type": {"type": "string"},
            },
        }

    @property
    def output_schema(self) -> dict[str, Any]:
        if hasattr(self.source, 'output_schema'):
            return self.source.output_schema
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "metadata": {"type": "object"},
                "success": {"type": "boolean"},
            },
        }

    @property
    def config_schema(self) -> dict[str, Any]:
        if hasattr(self.source, 'config_schema'):
            return self.source.config_schema
        return {"type": "object"}

    @property
    def requires_capabilities(self) -> list[str]:
        return self._requires_capabilities

    async def run(
        self,
        ctx: ExecutionContext,
        inputs: dict[str, Any],
        config: dict[str, Any],
    ) -> BlockResult:
        try:
            query = inputs.get("query", "")
            query_type = inputs.get("query_type", "search")
            result = await self.source.query(
                query_type,
                {**config, **inputs, "query": query, "project_id": ctx.project_id},
            )
            return BlockResult(
                ok=result.success,
                output={
                    "content": result.content,
                    "metadata": result.metadata,
                    "token_count": result.token_count,
                },
            )
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": self.source.name,
            "description": getattr(self.source, 'description', f"Tool block for {getattr(self.source, 'id', self.source.name)}"),
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "config_schema": self.config_schema,
            "requires_capabilities": self.requires_capabilities,
        }
