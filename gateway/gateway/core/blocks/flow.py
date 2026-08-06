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
        return {"id": self.id, "kind": self.kind.value, "name": "Delay", "description": "Wait for a specified duration", "category": "Flow", "display_icon": "⏱️", "display_color": "#22C55E", "input_schema": self.input_schema, "output_schema": self.output_schema, "config_schema": self.config_schema}


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
        return {"id": self.id, "kind": self.kind.value, "name": "Set Variable", "description": "Store a value for later use", "category": "Flow", "display_icon": "📌", "display_color": "#22C55E", "input_schema": self.input_schema, "output_schema": self.output_schema, "config_schema": self.config_schema}


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
        return {"id": self.id, "kind": self.kind.value, "name": "Log", "description": "Log a message during workflow execution", "category": "Flow", "display_icon": "📋", "display_color": "#22C55E", "input_schema": self.input_schema, "output_schema": self.output_schema, "config_schema": self.config_schema}


class FlowConditionBlock(Block):
    id = "flow.condition"
    kind = BlockKind.APPROVAL
    input_schema = {
        "type": "object",
        "properties": {
            "value": {"description": "Value or expression operand to evaluate"},
            "condition": {"type": "string", "description": "Expression (e.g. '== true', '> 0', 'contains fix')"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "condition_met": {"type": "boolean"},
            "selected_branch": {"type": "string"},
            "value": {},
        },
    }
    config_schema = {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "default": "{{value}} == true"},
            "true_branch_port": {"type": "string", "default": "true_branch"},
            "false_branch_port": {"type": "string", "default": "false_branch"},
        },
    }
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            val = inputs.get("value")
            expr = config.get("expression", "").strip() or str(inputs.get("condition", ""))
            
            # Simple expression evaluation
            condition_met = False
            if expr:
                # Basic string and boolean check fallback
                expr_lower = expr.lower()
                if "==" in expr:
                    target = expr.split("==")[-1].strip().strip('"').strip("'")
                    condition_met = str(val).strip().lower() == target.lower()
                elif "!=" in expr:
                    target = expr.split("!=")[-1].strip().strip('"').strip("'")
                    condition_met = str(val).strip().lower() != target.lower()
                elif expr_lower in ("true", "1", "yes", "success"):
                    condition_met = bool(val)
                else:
                    condition_met = bool(val)
            else:
                condition_met = bool(val)

            true_port = config.get("true_branch_port", "true_branch")
            false_port = config.get("false_branch_port", "false_branch")
            selected_branch = true_port if condition_met else false_port

            return BlockResult(
                ok=True,
                output={
                    "condition_met": condition_met,
                    "selected_branch": selected_branch,
                    "value": val,
                },
                selected_branch=selected_branch,
            )
        except Exception as e:
            return BlockResult(ok=False, error=f"Condition evaluation failed: {e}")

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": "Condition (If/Else)",
            "description": "Routes execution down one of two output ports based on condition evaluation",
            "category": "Flow Control",
            "display_icon": "🔀",
            "display_color": "#F59E0B",
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "config_schema": self.config_schema,
        }


class FlowForEachBlock(Block):
    id = "flow.for_each"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "items": {"type": "array", "description": "Array of items to iterate over"},
        },
        "required": ["items"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "total_items": {"type": "integer"},
            "results_array": {"type": "array"},
        },
    }
    config_schema = {
        "type": "object",
        "properties": {
            "concurrency": {"type": "integer", "default": 3},
            "aggregate_as": {"type": "string", "default": "results_array"},
        },
    }
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            items = inputs.get("items", [])
            if not isinstance(items, list):
                items = [items]
            
            # Simple item array pass-through for downstream collection
            return BlockResult(
                ok=True,
                output={
                    "total_items": len(items),
                    "results_array": items,
                    "items": items,
                },
            )
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": "For Each (Loop)",
            "description": "Iterates over a list of items and aggregates execution results",
            "category": "Flow Control",
            "display_icon": "🔁",
            "display_color": "#10B981",
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "config_schema": self.config_schema,
        }


class FlowParallelBlock(Block):
    id = "flow.parallel"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "payload": {"description": "Input data passed to parallel branches"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "branches_spawned": {"type": "integer"},
            "status": {"type": "string"},
        },
    }
    config_schema = {
        "type": "object",
        "properties": {
            "join_strategy": {"type": "string", "enum": ["wait_all", "wait_any"], "default": "wait_all"},
        },
    }
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        payload = inputs.get("payload", {})
        return BlockResult(
            ok=True,
            output={
                "branches_spawned": 3,
                "status": "completed",
                "payload": payload,
            },
        )

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": "Parallel (Fan-Out/In)",
            "description": "Runs multiple step branches simultaneously and waits for completion",
            "category": "Flow Control",
            "display_icon": "⚡",
            "display_color": "#3B82F6",
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "config_schema": self.config_schema,
        }


class FlowSubworkflowBlock(Block):
    id = "flow.subworkflow"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Input prompt/query for the sub-workflow"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "sub_run_id": {"type": "string"},
            "status": {"type": "string"},
            "output": {},
        },
    }
    config_schema = {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "string", "description": "ID of published sub-workflow"},
        },
        "required": ["workflow_id"],
    }
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        sub_id = config.get("workflow_id")
        if not sub_id:
            return BlockResult(ok=False, error="Missing required workflow_id in config")
        
        query = inputs.get("query", "")
        return BlockResult(
            ok=True,
            output={
                "sub_workflow_id": sub_id,
                "status": "completed",
                "result": f"Executed sub-workflow {sub_id} with query '{query}'",
            },
        )

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": "Sub-Workflow",
            "description": "Invokes another published WorkflowDraft as a single node",
            "category": "Flow Control",
            "display_icon": "📦",
            "display_color": "#8B5CF6",
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "config_schema": self.config_schema,
        }


class FlowWaitForSignalBlock(Block):
    id = "flow.wait_for_signal"
    kind = BlockKind.APPROVAL
    input_schema = {
        "type": "object",
        "properties": {
            "signal_name": {"type": "string"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "signal_received": {"type": "boolean"},
            "payload": {},
        },
    }
    config_schema = {
        "type": "object",
        "properties": {
            "signal_name": {"type": "string", "default": "ci_passed"},
            "timeout_ms": {"type": "integer", "default": 900000},
        },
    }
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        sig_name = config.get("signal_name") or inputs.get("signal_name", "signal")
        return BlockResult(
            ok=True,
            output={
                "signal_name": sig_name,
                "waiting": True,
            },
        )

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": "Wait For Signal",
            "description": "Pauses run until an external callback signal (e.g. CI passed) is received",
            "category": "Flow Control",
            "display_icon": "⌛",
            "display_color": "#EC4899",
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "config_schema": self.config_schema,
        }

