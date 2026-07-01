"""Runtime diagnostics."""

from __future__ import annotations

import sys
from pathlib import Path

from core.runtime.capabilities import Capability
from core.runtime.resolver import StorageResolver


async def run_doctor(repo_root: Path, mode: str = "auto") -> dict[str, object]:
    repo_root = Path(str(repo_root))
    env = await StorageResolver(repo_root, mode=mode).resolve()
    venv = Path(sys.prefix)
    expected_venv = repo_root / ".venv"
    return {
        "python": sys.version.split()[0],
        "sys_prefix": str(venv),
        "expected_root_venv": str(expected_venv),
        "using_root_venv": str(venv) == str(expected_venv),
        "runtime": env.status(),
        "server_mode_available": env.has(Capability.REST_API),
        "local_storage": str(repo_root / ".repo-intel" / "local"),
        "recommendations": _recommendations(env),
    }


def _recommendations(env) -> list[str]:
    recs = []
    if not env.has(Capability.REST_API):
        recs.append("REST API, Flutter, Gateway, and remote Git indexing require server mode.")
        recs.append("Start server storage with: docker compose up -d")
    if env.mode.value == "local":
        recs.append("Local mode supports CLI, MCP, and VS Code subprocess workflows.")
    return recs
