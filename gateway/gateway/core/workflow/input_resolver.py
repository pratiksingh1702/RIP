"""Resolve workflow block inputs from trigger data, bindings, and canvas wires."""

from __future__ import annotations

from typing import Any

from gateway.core.workflow.run_state import RunState


MISSING = object()


def extract_path(value: Any, path: str | None) -> Any:
    """Extract a dotted path from nested dict/list data."""
    if not path:
        return value
    current = value
    for part in path.split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if index < len(current) else None
            continue
        return None
    return current


def _resolve_binding(step_id: str, key: str, binding: Any, state: RunState) -> Any:
    provided_key = f"{step_id}.{key}"
    if provided_key in state.provided_inputs:
        return state.provided_inputs[provided_key]
    if not isinstance(binding, dict):
        return MISSING

    source = binding.get("source")
    if source == "trigger_query":
        return state.trigger_query or MISSING
    if source in {"literal", "fixed"}:
        value = binding.get("value", binding.get("fixed_value"))
        return value if value not in (None, "") else MISSING
    if source == "object":
        fields = binding.get("fields")
        if not isinstance(fields, dict):
            return MISSING
        resolved: dict[str, Any] = {}
        for field, field_binding in fields.items():
            value = _resolve_binding(step_id, f"{key}.{field}", field_binding, state)
            if value is MISSING:
                return MISSING
            resolved[str(field)] = value
        return resolved
    if source == "step_output":
        source_step_id = binding.get("step_id") or binding.get("source_step_id")
        source_step = state.step_states.get(source_step_id)
        if not source_step or source_step.output is None:
            return MISSING
        value = extract_path(source_step.output, binding.get("field") or binding.get("source_field"))
        return value if value is not None else MISSING
    return MISSING


def resolve_step_inputs(
    step_id: str,
    input_bindings: dict[str, Any],
    wires: list[dict[str, Any]],
    state: RunState,
) -> tuple[dict[str, Any], str | None]:
    """Resolve inputs for a step and return missing field name if unresolved."""
    inputs: dict[str, Any] = {}
    wire_bindings: dict[str, dict[str, Any]] = {}
    for wire in wires:
        if wire.get("target_step_id") != step_id:
            continue
        target_port = wire.get("target_port")
        if not target_port:
            continue
        mapping = wire.get("mapping") or {}
        wire_bindings[target_port] = {
            "source": "step_output",
            "source_step_id": wire.get("source_step_id"),
            "source_field": mapping.get("source_field") or mapping.get("field"),
        }

    merged_bindings = {**input_bindings, **wire_bindings}
    for key, binding in merged_bindings.items():
        value = _resolve_binding(step_id, key, binding, state)
        if value is MISSING:
            return inputs, key
        inputs[key] = value
    return inputs, None
