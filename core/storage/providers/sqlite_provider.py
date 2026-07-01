"""SQLite metadata provider for local mode."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from core.projects import ProjectRef, project_ref_for_root
from core.runtime.capabilities import Capability
from core.storage.interfaces.metadata_store import MetadataStore
from core.storage.providers.local_paths import sqlite_path


class SQLiteProvider(MetadataStore):
    name = "SQLiteProvider"
    capabilities = {
        Capability.METADATA_STORAGE,
        Capability.PERSISTENT_STORAGE,
        Capability.INCREMENTAL_INDEX,
    }

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.path = sqlite_path(self.repo_root)
        self._conn: sqlite3.Connection | None = None

    async def setup(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                root TEXT,
                language TEXT DEFAULT 'mixed',
                files_count INTEGER DEFAULT 0,
                entities_count INTEGER DEFAULT 0,
                languages TEXT DEFAULT '',
                created_at TEXT,
                indexed_at TEXT,
                last_reindexed_at TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS file_hashes (
                project_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                sha256_hash TEXT NOT NULL,
                PRIMARY KEY (project_id, file_path)
            )
            """
        )
        self._conn.commit()

    async def save_project(
        self,
        root: Path,
        project_id: str | None = None,
        project_name: str | None = None,
        files_count: int = 0,
        entities_count: int = 0,
        languages: list[str] | None = None,
    ) -> ProjectRef:
        conn = self._require_conn()
        ref = project_ref_for_root(root)
        project_id = project_id or ref.id
        project_name = project_name or ref.name
        root_str = str(root)
        now = datetime.now(UTC).isoformat()
        existing = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE projects
                   SET name = ?, root = ?, files_count = ?, entities_count = ?,
                       languages = ?, last_reindexed_at = ?
                 WHERE id = ?
                """,
                (
                    project_name,
                    root_str,
                    files_count,
                    entities_count,
                    ",".join(languages or []),
                    now,
                    project_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO projects
                    (id, name, root, language, files_count, entities_count, languages,
                     created_at, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    project_name,
                    root_str,
                    "mixed",
                    files_count,
                    entities_count,
                    ",".join(languages or []),
                    now,
                    now,
                ),
            )
        conn.commit()
        return ProjectRef(
            id=project_id,
            name=project_name,
            root=root_str,
            files_count=files_count,
            entities_count=entities_count,
            languages=languages or [],
        )

    async def get_project(self, project_id: str) -> ProjectRef | None:
        row = self._require_conn().execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        return self._row_to_ref(row) if row else None

    async def list_projects(self) -> list[ProjectRef]:
        rows = self._require_conn().execute("SELECT * FROM projects ORDER BY created_at").fetchall()
        return [self._row_to_ref(row) for row in rows]

    async def save_file_hash(self, project_id: str, file_path: str, sha256_hash: str) -> None:
        conn = self._require_conn()
        conn.execute(
            """
            INSERT INTO file_hashes (project_id, file_path, sha256_hash)
            VALUES (?, ?, ?)
            ON CONFLICT(project_id, file_path) DO UPDATE SET sha256_hash = excluded.sha256_hash
            """,
            (project_id, file_path, sha256_hash),
        )
        conn.commit()

    async def get_file_hash(self, project_id: str, file_path: str) -> str | None:
        row = self._require_conn().execute(
            "SELECT sha256_hash FROM file_hashes WHERE project_id = ? AND file_path = ?",
            (project_id, file_path),
        ).fetchone()
        return str(row["sha256_hash"]) if row else None

    async def delete_project(self, project_id: str) -> bool:
        conn = self._require_conn()
        cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.execute("DELETE FROM file_hashes WHERE project_id = ?", (project_id,))
        conn.commit()
        return cursor.rowcount > 0

    async def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SQLiteProvider.setup() must be called before use")
        return self._conn

    @staticmethod
    def _row_to_ref(row: sqlite3.Row) -> ProjectRef:
        languages = [item for item in str(row["languages"] or "").split(",") if item]
        return ProjectRef(
            id=row["id"],
            name=row["name"],
            root=row["root"],
            language=row["language"] or "mixed",
            files_count=row["files_count"] or 0,
            entities_count=row["entities_count"] or 0,
            languages=languages,
        )
