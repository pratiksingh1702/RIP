"""Repository file traversal."""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass, field
from pathlib import Path

from core.parser.base import ParsedFile
from core.parser.registry import LanguageParserRegistry

logger = logging.getLogger(__name__)


DEFAULT_EXCLUDES = [
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "*.pyc",
    "*.min.js",
]


@dataclass
class TraversalConfig:
    max_file_size_kb: int = 500
    exclude: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDES))


class FileTraversal:
    def __init__(
        self,
        registry: LanguageParserRegistry,
        config: TraversalConfig | None = None,
    ) -> None:
        self.registry = registry
        self.config = config or TraversalConfig()

    def parse_repository(self, root: Path) -> list[ParsedFile]:
        parsed_files: list[ParsedFile] = []
        for file_path in self.iter_source_files(root):
            parser = self.registry.get_parser(file_path)
            if parser is None:
                logger.debug("Skipping unsupported file type: %s", file_path)
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                logger.warning("Skipping non-UTF-8 file: %s", file_path)
                continue
            except OSError as exc:
                logger.warning("Skipping unreadable file %s: %s", file_path, exc)
                continue

            try:
                parsed_files.append(parser.parse_file(file_path, content))
            except SyntaxError as exc:
                logger.warning("Skipping file with syntax error %s: %s", file_path, exc)
            except Exception as exc:  # noqa: BLE001 - parser failures must not abort indexing
                logger.exception("Parser failed for %s: %s", file_path, exc)

        return parsed_files

    def iter_source_files(self, root: Path) -> list[Path]:
        root = root.resolve()
        if root.is_file():
            logger.debug("Treating single file as repo: %s", root)
            return [root] if self._is_allowed(root, root.parent) else []

        logger.info("Scanning repository for source files under %s", root)
        files: list[Path] = []
        for path in root.rglob("*"):
            if path.is_file() and self._is_allowed(path, root):
                files.append(path)
        logger.info("Found %s candidate source files", len(files))
        return files

    def find_files(self, root: Path) -> list[Path]:
        """Compatibility alias used by incremental indexers."""
        return self.iter_source_files(root)

    def _is_allowed(self, path: Path, root: Path) -> bool:
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path

        rel_text = rel.as_posix()
        parts = set(rel.parts)

        for pattern in self.config.exclude:
            clean = pattern.rstrip("/")
            if (
                clean in parts
                or fnmatch.fnmatch(rel_text, pattern)
                or fnmatch.fnmatch(path.name, pattern)
            ):
                return False

        try:
            size_kb = path.stat().st_size / 1024
        except OSError:
            return False

        return size_kb <= self.config.max_file_size_kb
