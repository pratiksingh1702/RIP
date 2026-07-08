"""Data transformation blocks for workflow logic."""

from __future__ import annotations

import json
from typing import Any

from gateway.core.blocks.base import Block, BlockKind, BlockResult, ExecutionContext


class DataFilterBlock(Block):
    id = "data.filter"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "data": {"type": "array", "description": "Array to filter"},
            "field": {"type": "string", "description": "Field to check"},
            "operator": {"type": "string", "enum": ["equals", "not_equals", "contains", "greater_than", "less_than", "exists", "not_exists"], "default": "equals"},
            "value": {"description": "Value to compare against"},
        },
        "required": ["data", "field"],
    }
    output_schema = {"type": "object", "properties": {"filtered": {"type": "array"}, "count": {"type": "integer"}, "removed": {"type": "integer"}}}
    config_schema = {}
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            data = inputs["data"]
            if not isinstance(data, list):
                return BlockResult(ok=False, error="data must be an array")
            field = str(inputs["field"])
            operator = str(inputs.get("operator", "equals"))
            value = inputs.get("value")
            original_count = len(data)
            
            filtered = []
            for item in data:
                item_val = item.get(field) if isinstance(item, dict) else getattr(item, field, None)
                keep = False
                if operator == "equals": keep = item_val == value
                elif operator == "not_equals": keep = item_val != value
                elif operator == "contains": keep = value in str(item_val) if item_val else False
                elif operator == "greater_than": keep = (item_val or 0) > (value or 0)
                elif operator == "less_than": keep = (item_val or 0) < (value or 0)
                elif operator == "exists": keep = item_val is not None
                elif operator == "not_exists": keep = item_val is None
                if keep: filtered.append(item)
            
            return BlockResult(ok=True, output={"filtered": filtered, "count": len(filtered), "removed": original_count - len(filtered)})
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "Filter", "description": "Filter array by field condition", "category": "Data", "display_icon": "🔽", "display_color": "#F59E0B", "input_schema": self.input_schema, "output_schema": self.output_schema}


class DataExtractBlock(Block):
    id = "data.extract"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "data": {"description": "Object or array to extract from"},
            "path": {"type": "string", "description": "Dot-notation path like 'items[0].name'"},
            "default": {"description": "Default value if path not found"},
        },
        "required": ["data", "path"],
    }
    output_schema = {"type": "object", "properties": {"value": {}, "found": {"type": "boolean"}}}
    config_schema = {}
    requires_capabilities = []

    def _drill(self, obj: Any, path: str) -> tuple[Any, bool]:
        parts = path.replace("[", ".").replace("]", "").split(".")
        current = obj
        for part in parts:
            if current is None: return None, False
            if isinstance(current, dict): current = current.get(part)
            elif isinstance(current, list) and part.isdigit(): current = current[int(part)] if int(part) < len(current) else None
            elif hasattr(current, part): current = getattr(current, part)
            else: return None, False
        return current, True

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            value, found = self._drill(inputs["data"], str(inputs["path"]))
            if not found:
                value = inputs.get("default")
            return BlockResult(ok=True, output={"value": value, "found": found})
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "Extract", "description": "Extract a field by path", "category": "Data", "display_icon": "⛏️", "display_color": "#F59E0B", "input_schema": self.input_schema, "output_schema": self.output_schema}


class DataMergeBlock(Block):
    id = "data.merge"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "objects": {"type": "array", "description": "Array of objects to merge"},
        },
        "required": ["objects"],
    }
    output_schema = {"type": "object", "properties": {"result": {"type": "object"}}}
    config_schema = {}
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            objects = inputs["objects"]
            if not isinstance(objects, list):
                return BlockResult(ok=False, error="objects must be an array")
            result = {}
            for obj in objects:
                if isinstance(obj, dict):
                    result.update(obj)
            return BlockResult(ok=True, output={"result": result})
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "Merge", "description": "Merge multiple objects into one", "category": "Data", "display_icon": "🔗", "display_color": "#F59E0B", "input_schema": self.input_schema, "output_schema": self.output_schema}


class DataToJsonBlock(Block):
    id = "data.to_json"
    kind = BlockKind.TOOL
    input_schema = {
        "type": "object",
        "properties": {
            "data": {"description": "Any data to convert"},
            "pretty": {"type": "boolean", "default": True},
        },
        "required": ["data"],
    }
    output_schema = {"type": "object", "properties": {"json": {"type": "string"}}}
    config_schema = {}
    requires_capabilities = []

    async def run(self, ctx: ExecutionContext, inputs: dict[str, Any], config: dict[str, Any]) -> BlockResult:
        try:
            pretty = bool(inputs.get("pretty", True))
            result = json.dumps(inputs["data"], indent=2 if pretty else None, default=str)
            return BlockResult(ok=True, output={"json": result})
        except Exception as e:
            return BlockResult(ok=False, error=str(e))

    def describe(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "name": "To JSON", "description": "Convert data to JSON string", "category": "Data", "display_icon": "📝", "display_color": "#F59E0B", "input_schema": self.input_schema, "output_schema": self.output_schema}
