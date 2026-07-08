"""Flow control blocks for branching, looping, and delays."""

from __future__ import annotations

import asyncio
from typing import Any

from gateway.core.blocks.base import Block, BlockKind, BlockResult, ExecutionContext


class FlowDelayBlock(Block):
    id = "flow.delay"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "seconds": {"type": "number", "description": "Seconds to wait"},
            "reason": {"type": "string", "description": "Why we are waiting"},
        },
        "required": ["seconds"],
    }
    output_schema = {"type": "object", "properties": {"waited_seconds": {"type": "number"}}}
    config_schema = {"type": "object", "properties": {"max_seconds": {"type": "number", "default": 300}}}
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            seconds = float(inputs["seconds"])
            max_seconds = float(config.get("max_seconds", 300))
            if seconds > max_seconds:
                return BlockResult(ok=False, error=f"Delay {seconds}s exceeds max {max_seconds}s")
            if seconds < 0:
                return BlockResult(ok=False, error="Delay cannot be negative")
            reason = str(inputs.get("reason", "No reason provided"))
            await asyncio.sleep(seconds)
            return BlockResult(ok=True, output={"waited_seconds": seconds, "reason": reason})
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "Delay", "description": "Wait for a specified duration", "category": "Flow", "display_icon": "⏱️", "display_color": "#22C55E", "input_schema": self.input_schema, "output_schema": self.output_schema}


class FlowSetVariableBlock(Block):
    id = "flow.set_variable"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Variable name"},
            "value": {"description": "Value to store"},
        },
        "required": ["name", "value"],
    }
    output_schema = {"type": "object", "properties": {"name": {"type": "string"}, "value": {}}}
    config_schema = {}
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            name = str(inputs["name"])
            value = inputs["value"]
            return BlockResult(ok=True, output={"name": name, "value": value, f"var_{name}": value})
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "Set Variable", "description": "Store a value for later use", "category": "Flow", "display_icon": "📌", "display_color": "#22C55E", "input_schema": self.input_schema, "output_schema": self.output_schema}


class FlowLogBlock(Block):
    id = "flow.log"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "message": {"type": "string"},
            "level": {"type": "string", "enum": ["debug", "info", "warning", "error"], "default": "info"},
            "data": {"description": "Additional data to log"},
        },
        "required": ["message"],
    }
    output_schema = {"type": "object", "properties": {"logged": {"type": "boolean"}}}
    config_schema = {}
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        import structlog
        logger = structlog.get_logger(__name__)
        level = str(inputs.get("level", "info"))
        msg = str(inputs["message"])
        data = inputs.get("data", {})
        log_method = getattr(logger, level, logger.info)
        log_method(msg, **data if isinstance(data, dict) else {"data": data})
        return BlockResult(ok=True, output={"logged": True})

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "Log", "description": "Log a message during workflow execution", "category": "Flow", "display_icon": "📋", "display_color": "#22C55E", "input_schema": self.input_schema, "output_schema": self.output_schema}
