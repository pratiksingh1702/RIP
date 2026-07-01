"""Resolved runtime environment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from core.runtime.capabilities import Capability


class RuntimeMode(StrEnum):
    AUTO = "auto"
    SERVER = "server"
    LOCAL = "local"


class CapabilityProvider(Protocol):
    name: str
    capabilities: set[Capability]


@dataclass
class RuntimeEnvironment:
    mode: RuntimeMode
    graph: CapabilityProvider
    vector: CapabilityProvider
    metadata: CapabilityProvider
    root: Path
    diagnostics: list[str]

    @property
    def capabilities(self) -> set[Capability]:
        caps: set[Capability] = set()
        caps.update(self.graph.capabilities)
        caps.update(self.vector.capabilities)
        caps.update(self.metadata.capabilities)
        if self.mode == RuntimeMode.SERVER:
            caps.update(
                {
                    Capability.REST_API,
                    Capability.WEBSOCKET,
                    Capability.CONCURRENT_USERS,
                    Capability.SHARED_INDEXES,
                    Capability.REMOTE_INDEXING,
                    Capability.FLUTTER_CLIENT,
                }
            )
        return caps

    def has(self, capability: Capability) -> bool:
        return capability in self.capabilities

    @property
    def description(self) -> str:
        return f"{self.graph.name} + {self.vector.name} + {self.metadata.name}"

    def status(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "graph": self.graph.name,
            "vector": self.vector.name,
            "metadata": self.metadata.name,
            "capabilities": sorted(cap.name for cap in self.capabilities),
            "diagnostics": self.diagnostics,
        }
