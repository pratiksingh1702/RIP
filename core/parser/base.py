"""Parser contracts.

The parser layer is intentionally storage-agnostic. Parsers emit typed
structures only; graph, search, CLI, and API layers consume them later.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ParsedEntity:
    entity_type: str
    name: str
    fqn: str
    file_path: str
    line_start: int
    line_end: int
    language: str
    docstring: str | None
    decorators: list[str]
    is_exported: bool
    raw_code: str
    project_id: str | None = None


@dataclass
class ParsedRelationship:
    from_fqn: str
    to_fqn: str
    relationship_type: str
    file_path: str
    line: int
    project_id: str | None = None


@dataclass
class ParsedFile:
    file_path: str
    language: str
    entities: list[ParsedEntity]
    relationships: list[ParsedRelationship]
    imports: list[str]
    sha256_hash: str
    project_id: str | None = None


class BaseParser(ABC):
    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """Return true if this parser supports the file."""

    @abstractmethod
    def parse_file(self, file_path: Path, content: str) -> ParsedFile:
        """Parse source content into typed entities and relationships."""
