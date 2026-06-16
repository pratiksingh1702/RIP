"""Analysis engine contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.graph.client import Neo4jClient


class BaseAnalyser:
    """Abstract base class for all repository analysis engines."""

    def __init__(self, graph_client: Neo4jClient) -> None:
        self.graph_client = graph_client
