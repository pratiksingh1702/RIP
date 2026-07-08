"""Individual RIP blocks for granular workflow control."""

from __future__ import annotations

from typing import Any

from gateway.core.blocks.base import Block, BlockKind, BlockResult, ExecutionContext
from gateway.core.sources.rip_client import RIPSource


class _RIPBlock(Block):
    """Base class for RIP blocks."""
    kind = BlockKind.RETRIEVAL
    query_type = ""
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            source = RIPSource()
            params = {**inputs, "project_id": ctx.project_id or inputs.get("project_id")}
            result = await source.query(self.query_type, params)
            return BlockResult(
                ok=result.success,
                output={"content": result.content, "metadata": result.metadata, "token_count": result.token_count},
            )
        except Exception as e:
            return BlockResult(ok=False, error=str(e))


class RIPSearchBlock(_RIPBlock):
    id = "rip.search"
    query_type = "search"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer", "default": 10},
            "project_id": {"type": "string", "nullable": True},
        },
        "required": ["query"],
    }
    output_schema = {"type": "object", "properties": {"content": {"type": "string"}, "metadata": {"type": "object"}}}
    config_schema = {}

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "RIP Search", "description": "Semantic search across the codebase", "category": "RIP", "display_icon": "🔍", "display_color": "#8B5CF6", "input_schema": self.input_schema, "output_schema": self.output_schema}


class RIPTraceBlock(_RIPBlock):
    id = "rip.trace"
    query_type = "trace"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Symbol to trace"},
            "depth": {"type": "integer", "default": 3},
        },
        "required": ["query"],
    }
    output_schema = {"type": "object", "properties": {"content": {"type": "string"}, "metadata": {"type": "object"}}}
    config_schema = {}

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "RIP Trace", "description": "Trace dependency chains", "category": "RIP", "display_icon": "📊", "display_color": "#8B5CF6", "input_schema": self.input_schema, "output_schema": self.output_schema}


class RIPExplainBlock(_RIPBlock):
    id = "rip.explain"
    query_type = "explain"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to explain"},
        },
        "required": ["query"],
    }
    output_schema = {"type": "object", "properties": {"content": {"type": "string"}, "metadata": {"type": "object"}}}
    config_schema = {}

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "RIP Explain", "description": "Explain code architecture and structure", "category": "RIP", "display_icon": "💡", "display_color": "#8B5CF6", "input_schema": self.input_schema, "output_schema": self.output_schema}


class RIPImpactBlock(_RIPBlock):
    id = "rip.impact"
    query_type = "impact"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What change to analyze"},
        },
        "required": ["query"],
    }
    output_schema = {"type": "object", "properties": {"content": {"type": "string"}, "metadata": {"type": "object"}}}
    config_schema = {}

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "RIP Impact", "description": "Analyze impact of changes", "category": "RIP", "display_icon": "🔬", "display_color": "#8B5CF6", "input_schema": self.input_schema, "output_schema": self.output_schema}


class RIPArchitectureBlock(_RIPBlock):
    id = "rip.architecture"
    query_type = "architecture"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What system to describe"},
        },
        "required": ["query"],
    }
    output_schema = {"type": "object", "properties": {"content": {"type": "string"}, "metadata": {"type": "object"}}}
    config_schema = {}

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "RIP Architecture", "description": "Generate architecture overview", "category": "RIP", "display_icon": "🏗️", "display_color": "#8B5CF6", "input_schema": self.input_schema, "output_schema": self.output_schema}


class RIPMetricsBlock(_RIPBlock):
    id = "rip.metrics"
    query_type = "metrics"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to measure"},
        },
        "required": ["query"],
    }
    output_schema = {"type": "object", "properties": {"content": {"type": "string"}, "metadata": {"type": "object"}}}
    config_schema = {}

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "RIP Metrics", "description": "Code metrics and complexity", "category": "RIP", "display_icon": "📈", "display_color": "#8B5CF6", "input_schema": self.input_schema, "output_schema": self.output_schema}


class RIPDeadCodeBlock(_RIPBlock):
    id = "rip.dead_code"
    query_type = "dead_code"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Module or path to scan"},
        },
        "required": ["query"],
    }
    output_schema = {"type": "object", "properties": {"content": {"type": "string"}, "metadata": {"type": "object"}}}
    config_schema = {}

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "RIP Dead Code", "description": "Detect unused code", "category": "RIP", "display_icon": "💀", "display_color": "#8B5CF6", "input_schema": self.input_schema, "output_schema": self.output_schema}


class RIPOnboardBlock(_RIPBlock):
    id = "rip.onboard"
    query_type = "onboard"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What area to onboard to"},
        },
        "required": ["query"],
    }
    output_schema = {"type": "object", "properties": {"content": {"type": "string"}, "metadata": {"type": "object"}}}
    config_schema = {}

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "RIP Onboard", "description": "Generate onboarding guide", "category": "RIP", "display_icon": "📚", "display_color": "#8B5CF6", "input_schema": self.input_schema, "output_schema": self.output_schema}
