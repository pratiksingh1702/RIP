"""Sandbox Filesystem — Safe file operations inside sandbox container."""
from __future__ import annotations
import logging
from pathlib import PurePosixPath
from gateway.core.sandbox.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)

class SandboxFilesystem:
    def __init__(self, sandbox_id: str):
        self.sandbox_id = sandbox_id
        self._orchestrator = get_orchestrator()

    def list_files(self, path: str = "/workspace") -> list[dict]:
        safe_path = self._safe_path(path)
        exit_code, output = self._orchestrator.exec_command(self.sandbox_id, f"find {safe_path} -maxdepth 3 -not -path '*/\\.*' | head -100")
        if exit_code != 0: return []
        files = []
        for line in output.strip().split("\n"):
            if not line: continue
            filepath = line.strip()
            is_dir = self._is_directory(filepath)
            files.append({"name": PurePosixPath(filepath).name, "path": filepath, "is_directory": is_dir, "size": self._file_size(filepath) if not is_dir else 0})
        return files

    def read_file(self, path: str) -> tuple[bool, str]:
        safe_path = self._safe_path(path)
        exit_code, output = self._orchestrator.exec_command(self.sandbox_id, f"cat {safe_path}")
        return exit_code == 0, output

    def write_file(self, path: str, content: str) -> bool:
        safe_path = self._safe_path(path)
        escaped = content.replace("'", "'\\''")
        exit_code, _ = self._orchestrator.exec_command(self.sandbox_id, f"echo '{escaped}' > {safe_path}")
        return exit_code == 0

    def create_directory(self, path: str) -> bool:
        safe_path = self._safe_path(path)
        exit_code, _ = self._orchestrator.exec_command(self.sandbox_id, f"mkdir -p {safe_path}")
        return exit_code == 0

    def delete_file(self, path: str) -> bool:
        safe_path = self._safe_path(path)
        exit_code, _ = self._orchestrator.exec_command(self.sandbox_id, f"rm -f {safe_path}")
        return exit_code == 0

    def file_exists(self, path: str) -> bool:
        safe_path = self._safe_path(path)
        exit_code, _ = self._orchestrator.exec_command(self.sandbox_id, f"test -f {safe_path}")
        return exit_code == 0

    def _is_directory(self, path: str) -> bool:
        exit_code, _ = self._orchestrator.exec_command(self.sandbox_id, f"test -d {path}")
        return exit_code == 0

    def _file_size(self, path: str) -> int:
        exit_code, output = self._orchestrator.exec_command(self.sandbox_id, f"stat -c%s {path}")
        if exit_code != 0: return 0
        try: return int(output.strip())
        except ValueError: return 0

    def _safe_path(self, path: str) -> str:
        p = PurePosixPath(path)
        if p.is_absolute():
            resolved = str(p)
        else:
            resolved = str(PurePosixPath("/workspace") / p)
        if ".." in resolved: raise ValueError("Path traversal not allowed")
        return resolved
