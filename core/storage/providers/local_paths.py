"""Local runtime storage paths."""

from __future__ import annotations

from pathlib import Path


def local_root(repo_root: Path) -> Path:
    return repo_root.resolve() / ".repo-intel" / "local"


def graph_path(repo_root: Path) -> Path:
    return local_root(repo_root) / "graph.json"


def vector_path(repo_root: Path) -> Path:
    return local_root(repo_root) / "vectors.json"


def sqlite_path(repo_root: Path) -> Path:
    return local_root(repo_root) / "rip.sqlite3"
