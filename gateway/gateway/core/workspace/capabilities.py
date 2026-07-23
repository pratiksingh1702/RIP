"""Capability Registry — maps intents to handlers. Add new handlers with one registration."""

from __future__ import annotations
from typing import Callable, Any


class CapabilityRegistry:
    def __init__(self):
        self._handlers: dict[str, dict] = {}

    def register(self, intent: str, handler: Callable, cost: str = "full"):
        self._handlers[intent] = {"handler": handler, "cost": cost}

    def get(self, intent: str) -> dict | None:
        return self._handlers.get(intent)


_registry = CapabilityRegistry()

def get_capability_registry() -> CapabilityRegistry:
    return _registry
