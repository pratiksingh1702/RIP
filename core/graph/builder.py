"""Graph builder - optimized for speed with detailed logging."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from pathlib import Path
from typing import TypeVar

import anyio

from core.graph.client import Neo4jClient
from core.graph.queries.ownership import (
    create_developers_and_commits_batch,
    relate_commits_to_files_batch,
    set_file_ownership_batch,
)
from core.parser.base import ParsedFile
from core.projects import DEFAULT_PROJECT_ID

T = TypeVar("T")
logger = logging.getLogger(__name__)


def _chunk_list(lst: Iterable[T], chunk_size: int = 1000) -> Iterable[list[T]]:
    """Split a list into chunks."""
    chunk = []
    for item in lst:
        chunk.append(item)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


ENTITY_LABELS = {
    "class": "Class",
    "function": "Function",
    "interface": "Interface",
    "api_route": "APIRoute",
    "db_model": "DBEntity",
    "module": "Module",
    "widget": "Widget",
}


def _module_name(file_path: str) -> str:
    normalized = file_path.replace("\\", "/")
    if normalized.endswith(".py"):
        normalized = normalized[:-3]
    return normalized.strip("/").replace("/", ".")


def _symbol_name(fqn: str) -> str:
    return fqn.rsplit(".", 1)[-1] if fqn else ""


class GraphBuilder:
    """Optimized graph builder with batched operations and detailed logging."""

    def __init__(self, client: Neo4jClient, project_id: str | None = None) -> None:
        self.client = client
        self.project_id = project_id or DEFAULT_PROJECT_ID
        self._stats = {"files": 0, "entities": 0, "relationships": 0}

    async def build_from_files(
        self,
        parsed_files: list[ParsedFile],
        progress: object | None = None,
    ) -> dict[str, int]:
        """Batch write parsed files with maximum speed."""
        if not parsed_files:
            return {"files": 0, "entities": 0, "relationships": 0}

        start = time.perf_counter()
        total_files = len(parsed_files)

        # Stamp all files with project ID
        for pf in parsed_files:
            self._stamp_project(pf)

        logger.info("🔗 Graph: Writing %d files to Neo4j...", total_files)

        # Phase 1: Upsert files and modules (fast - one query per batch)
        file_start = time.perf_counter()
        await self._upsert_files_batch_fast(parsed_files)
        file_time = time.perf_counter() - file_start
        logger.info("   📁 Files/Modules: %.1fs", file_time)

        # Phase 2: Upsert entities (bulk by type)
        entity_start = time.perf_counter()
        entity_count = await self._upsert_entities_batch_fast(parsed_files)
        entity_time = time.perf_counter() - entity_start
        logger.info("   🔷 Entities (%d): %.1fs (%.0f e/s)",
                   entity_count, entity_time,
                   entity_count / entity_time if entity_time > 0 else 0)

        # Phase 3: Upsert relationships (bulk by type)
        rel_start = time.perf_counter()
        rel_count = await self._upsert_relationships_batch_fast(parsed_files)
        rel_time = time.perf_counter() - rel_start
        logger.info("   🔗 Relations (%d): %.1fs (%.0f r/s)",
                   rel_count, rel_time,
                   rel_count / rel_time if rel_time > 0 else 0)

        total_time = time.perf_counter() - start
        logger.info("✅ Graph: %d files, %d entities, %d rels in %.1fs (%.0f f/s)",
                   total_files, entity_count, rel_count, total_time,
                   total_files / total_time if total_time > 0 else 0)

        return {
            "files": total_files,
            "entities": entity_count,
            "relationships": rel_count,
        }

    def _stamp_project(self, parsed_file: ParsedFile) -> None:
        """Stamp project ID on all objects."""
        project_id = parsed_file.project_id or self.project_id
        if not project_id:
            raise ValueError("project_id is required for graph indexing")
        parsed_file.project_id = project_id
        for entity in parsed_file.entities:
            entity.project_id = project_id
        for relationship in parsed_file.relationships:
            relationship.project_id = project_id

    # ========================================================================
    # FAST BATCH OPERATIONS
    # ========================================================================

    async def _upsert_files_batch_fast(self, parsed_files: list[ParsedFile]) -> None:
        """Ultra-fast file/module upsert in one query."""
        rows = [
            {
                "path": pf.file_path,
                "language": pf.language,
                "sha256_hash": pf.sha256_hash,
                "module_name": _module_name(pf.file_path),
                "project_id": pf.project_id,
            }
            for pf in parsed_files
        ]
        
        # Use larger chunks (500 files at once)
        for i, chunk in enumerate(_chunk_list(rows, chunk_size=500)):
            await self.client.execute(
                """
                UNWIND $rows AS row
                MERGE (p:Project {id: row.project_id})
                SET p.name = coalesce(p.name, row.project_id),
                    p.root = coalesce(p.root, ""),
                    p.language = coalesce(p.language, row.language)
                MERGE (f:File {path: row.path, project_id: row.project_id})
                SET f.language = row.language,
                    f.sha256_hash = row.sha256_hash,
                    f.project_id = row.project_id
                MERGE (p)-[:CONTAINS]->(f)
                MERGE (m:Module {module_key: row.module_name, project_id: row.project_id})
                SET m.file_path = row.path,
                    m.name = row.module_name,
                    m.language = row.language,
                    m.project_id = row.project_id
                MERGE (p)-[:OWNS]->(m)
                MERGE (m)-[:REPRESENTS]->(f)
                """,
                {"rows": chunk},
            )
            logger.debug("   File batch %d: %d files", i + 1, len(chunk))

    async def _upsert_entities_batch_fast(self, parsed_files: list[ParsedFile]) -> int:
        """Fast entity upsert grouped by type."""
        count = 0
        rows_by_label: dict[str, list[dict]] = {}

        for pf in parsed_files:
            for entity in pf.entities:
                row = {
                    "fqn": entity.fqn,
                    "name": entity.name,
                    "file_path": pf.file_path,
                    "line_start": entity.line_start,
                    "line_end": entity.line_end,
                    "language": pf.language,
                    "docstring": getattr(entity, 'docstring', ''),
                    "decorators": getattr(entity, 'decorators', []),
                    "is_exported": getattr(entity, 'is_exported', False),
                    "raw_code": getattr(entity, 'raw_code', ''),
                    "project_id": pf.project_id,
                }
                label = ENTITY_LABELS.get(entity.entity_type, "Function")
                rows_by_label.setdefault(label, []).append(row)
                count += 1

        # Process each entity type in bulk
        for label, rows in rows_by_label.items():
            for i, chunk in enumerate(_chunk_list(rows, chunk_size=2000)):
                await self.client.execute(
                    f"""
                    UNWIND $rows AS row
                    MATCH (p:Project {{id: row.project_id}})
                    MATCH (f:File {{path: row.file_path, project_id: row.project_id}})
                    MERGE (e:{label} {{fqn: row.fqn, project_id: row.project_id}})
                    SET e.name = row.name,
                        e.file_path = row.file_path,
                        e.line_start = row.line_start,
                        e.line_end = row.line_end,
                        e.language = row.language,
                        e.docstring = row.docstring,
                        e.decorators = row.decorators,
                        e.is_exported = row.is_exported,
                        e.raw_code = row.raw_code,
                        e.project_id = row.project_id
                    MERGE (p)-[:OWNS]->(e)
                    MERGE (f)-[:CONTAINS]->(e)
                    """,
                    {"rows": chunk},
                )
                logger.debug("   %s batch %d: %d entities", label, i + 1, len(chunk))

        return count

    async def _upsert_relationships_batch_fast(self, parsed_files: list[ParsedFile]) -> int:
        """Fast relationship upsert grouped by type."""
        count = 0
        rows_by_type: dict[str, list[dict]] = {}
        ALLOWED = {"CALLS", "IMPORTS", "EXTENDS", "IMPLEMENTS", "CONTAINS",
            "DEPENDS_ON", "REPRESENTS", "OWNS"}

        for pf in parsed_files:
            for rel in pf.relationships:
                if rel.relationship_type not in ALLOWED:
                    continue
                rows_by_type.setdefault(rel.relationship_type, []).append({
                    "from_fqn": rel.from_fqn,
                    "to_fqn": rel.to_fqn,
                    "to_name": _symbol_name(rel.to_fqn),
                    "file_path": pf.file_path,
                    "line": rel.line,
                    "project_id": pf.project_id,
                })
                count += 1

        # Process each relationship type
        queries = {
            "CALLS": """
                UNWIND $rows AS row
                MATCH (source {fqn: row.from_fqn, project_id: row.project_id})
                MERGE (target:Function {fqn: row.to_fqn, project_id: row.project_id})
                ON CREATE SET target.name = row.to_name, target.file_path = row.file_path,
                              target.project_id = row.project_id
                MERGE (source)-[r:CALLS]->(target)
                SET r.file_path = row.file_path, r.line = row.line
            """,
            "IMPORTS": """
                UNWIND $rows AS row
                MATCH (file:File {path: row.file_path, project_id: row.project_id})
                MERGE (module:Module {module_key: row.to_fqn, project_id: row.project_id})
                SET module.project_id = row.project_id, module.name = row.to_fqn
                MERGE (file)-[r:IMPORTS]->(module)
                SET r.line = row.line
                WITH row, file, module
                MATCH (source_module:Module {project_id: row.project_id})-[:REPRESENTS]->(file)
                MERGE (source_module)-[:DEPENDS_ON]->(module)
            """,
            "EXTENDS": """
                UNWIND $rows AS row
                MATCH (source:Class {fqn: row.from_fqn, project_id: row.project_id})
                MERGE (target:Class {name: row.to_name, project_id: row.project_id})
                ON CREATE SET target.fqn = row.to_fqn, target.file_path = row.file_path,
                              target.project_id = row.project_id
                MERGE (source)-[r:EXTENDS]->(target)
                SET r.file_path = row.file_path, r.line = row.line
            """,
            "IMPLEMENTS": """
                UNWIND $rows AS row
                MATCH (source:Class {fqn: row.from_fqn, project_id: row.project_id})
                MERGE (target:Interface {name: row.to_name, project_id: row.project_id})
                ON CREATE SET target.fqn = row.to_fqn, target.file_path = row.file_path,
                              target.project_id = row.project_id
                MERGE (source)-[r:IMPLEMENTS]->(target)
                SET r.file_path = row.file_path, r.line = row.line
            """,
            "CONTAINS": """
                UNWIND $rows AS row
                MATCH (source {fqn: row.from_fqn, project_id: row.project_id})
                MATCH (target {fqn: row.to_fqn, project_id: row.project_id})
                MERGE (source)-[r:CONTAINS]->(target)
                SET r.file_path = row.file_path, r.line = row.line
            """,
        }

        for rel_type, query in queries.items():
            if rows := rows_by_type.get(rel_type):
                for i, chunk in enumerate(_chunk_list(rows, chunk_size=2000)):
                    await self.client.execute(query, {"rows": chunk})
                    logger.debug("   %s batch %d: %d rels", rel_type, i + 1, len(chunk))

        return count

    # ========================================================================
    # SINGLE FILE OPERATIONS (kept for backward compatibility)
    # ========================================================================

    async def build_from_file(self, parsed_file: ParsedFile) -> None:
        """Build graph from single file."""
        self._stamp_project(parsed_file)
        await self._upsert_file(parsed_file)
        for entity in parsed_file.entities:
            await self._upsert_entity(parsed_file, entity.__dict__)
        for relationship in parsed_file.relationships:
            await self._upsert_relationship(relationship.__dict__)

    async def _upsert_file(self, parsed_file: ParsedFile) -> None:
        await self.client.execute(
            """
            MERGE (p:Project {id: $project_id})
            SET p.name = coalesce(p.name, $project_name),
                p.root = coalesce(p.root, $project_root),
                p.language = coalesce(p.language, $language)
            MERGE (f:File {path: $path, project_id: $project_id})
            SET f.language = $language, f.sha256_hash = $sha256_hash
            MERGE (p)-[:CONTAINS]->(f)
            MERGE (m:Module {module_key: $module_name, project_id: $project_id})
            SET m.file_path = $path, m.name = $module_name,
                m.language = $language, m.project_id = $project_id
            MERGE (p)-[:OWNS]->(m)
            MERGE (m)-[:REPRESENTS]->(f)
            """,
            {
                "path": parsed_file.file_path,
                "language": parsed_file.language,
                "sha256_hash": parsed_file.sha256_hash,
                "module_name": _module_name(parsed_file.file_path),
                "project_id": parsed_file.project_id,
                "project_name": parsed_file.project_id,
                "project_root": "",
            },
        )

    async def _upsert_entity(self, parsed_file: ParsedFile, entity: dict) -> None:
        label = ENTITY_LABELS.get(str(entity["entity_type"]), "Function")
        await self.client.execute(
            f"""
            MATCH (p:Project {{id: $project_id}})
            MATCH (f:File {{path: $file_path, project_id: $project_id}})
            MERGE (e:{label} {{fqn: $fqn, project_id: $project_id}})
            SET e.name = $name, e.file_path = $file_path,
                e.line_start = $line_start, e.line_end = $line_end,
                e.language = $language, e.docstring = $docstring,
                e.decorators = $decorators, e.is_exported = $is_exported,
                e.raw_code = $raw_code, e.project_id = $project_id
            MERGE (p)-[:OWNS]->(e)
            MERGE (f)-[:CONTAINS]->(e)
            """,
            {**entity, "file_path": parsed_file.file_path},
        )

    async def _upsert_relationship(self, relationship: dict) -> None:
        rel_type = str(relationship["relationship_type"])
        row = {**relationship, "to_name": _symbol_name(str(relationship["to_fqn"]))}
        
        queries = {
            "CALLS": """
                MATCH (source {fqn: $from_fqn, project_id: $project_id})
                MERGE (target:Function {fqn: $to_fqn, project_id: $project_id})
                ON CREATE SET target.name = $to_name, target.file_path = $file_path,
                              target.project_id = $project_id
                MERGE (source)-[r:CALLS]->(target) SET r.file_path = $file_path, r.line = $line
            """,
            "IMPORTS": """
                MATCH (file:File {path: $file_path, project_id: $project_id})
                MERGE (module:Module {module_key: $to_fqn, project_id: $project_id})
                SET module.project_id = $project_id, module.name = $to_fqn
                MERGE (file)-[r:IMPORTS]->(module) SET r.line = $line
                WITH file, module
                MATCH (source_module:Module {project_id: $project_id})-[:REPRESENTS]->(file)
                MERGE (source_module)-[:DEPENDS_ON]->(module)
            """,
            "EXTENDS": """
                MATCH (source:Class {fqn: $from_fqn, project_id: $project_id})
                MERGE (target:Class {name: $to_name, project_id: $project_id})
                ON CREATE SET target.fqn = $to_fqn, target.file_path = $file_path,
                              target.project_id = $project_id
                MERGE (source)-[r:EXTENDS]->(target) SET r.file_path = $file_path, r.line = $line
            """,
            "IMPLEMENTS": """
                MATCH (source:Class {fqn: $from_fqn, project_id: $project_id})
                MERGE (target:Interface {name: $to_name, project_id: $project_id})
                ON CREATE SET target.fqn = $to_fqn, target.file_path = $file_path,
                              target.project_id = $project_id
                MERGE (source)-[r:IMPLEMENTS]->(target) SET r.file_path = $file_path, r.line = $line
            """,
            "CONTAINS": """
                MATCH (source {fqn: $from_fqn, project_id: $project_id})
                MATCH (target {fqn: $to_fqn, project_id: $project_id})
                MERGE (source)-[r:CONTAINS]->(target) SET r.file_path = $file_path, r.line = $line
            """,
        }
        
        if query := queries.get(rel_type):
            await self.client.execute(query, row)

    async def delete_file_entities(self, file_path: str, project_id: str | None = None) -> None:
        """Delete stale entities and outgoing dependency edges for a file."""
        project_id = project_id or self.project_id
        if not project_id:
            return
        await self.client.execute(
            """
            MATCH (f:File {project_id: $project_id})
            WHERE f.path = $file_path
               OR replace(f.path, "\\\\", "/") ENDS WITH "/" + $file_path
            OPTIONAL MATCH (f)-[import_rel:IMPORTS]->()
            DELETE import_rel
            WITH f
            OPTIONAL MATCH (module:Module {project_id: $project_id})-[:REPRESENTS]->(f)
            OPTIONAL MATCH (module)-[dep_rel:DEPENDS_ON]->()
            DELETE dep_rel
            WITH f
            OPTIONAL MATCH (f)-[:CONTAINS]->(entity)
            DETACH DELETE entity
            """,
            {"file_path": file_path, "project_id": project_id},
        )

    # ========================================================================
    # GIT DATA
    # ========================================================================

    async def build_git_data(self, repo_path: Path) -> None:
        """Extract and insert Git data (optimized batch version)."""
        from core.parser.git_ingestor import GitIngestor

        logger.info("📊 Git: Extracting commit history...")
        git_start = time.perf_counter()

        repo_path = await anyio.to_thread.run_sync(lambda p: p.resolve(), repo_path)
        ingestor = GitIngestor(repo_path)
        if not ingestor.is_git_repo:
            logger.info("   ⚠ Not a git repository - skipping")
            return

        # Collect all commits and file relations first
        commits = ingestor.get_commits(limit=100)
        commit_rows = []
        file_rel_rows = []

        for commit in commits:
            commit_rows.append({
                "hash": commit.hash,
                "message": commit.message[:200],
                "timestamp": commit.timestamp.isoformat(),
                "author_name": commit.author_name,
                "author_email": commit.author_email,
            })
            for file_path in commit.files_modified:
                abs_path = await anyio.to_thread.run_sync(
                    lambda r, f: str((r / f).resolve()), repo_path, file_path
                )
                file_rel_rows.append({"hash": commit.hash, "file_path": abs_path})

        # Batch insert commits and developers
        t1 = time.perf_counter()
        await create_developers_and_commits_batch(self.client, commit_rows)
        logger.info("   📝 %d commits in %.1fs", len(commit_rows), time.perf_counter() - t1)

        # Batch insert file-commit relations
        t2 = time.perf_counter()
        for chunk in _chunk_list(file_rel_rows, chunk_size=500):
            await relate_commits_to_files_batch(self.client, chunk, self.project_id)
        logger.info(
            "   📁 %d file relations in %.1fs",
            len(file_rel_rows),
            time.perf_counter() - t2,
        )

        # Ownership data
        if not self.project_id:
            logger.info("   ⚠ No project ID - skipping ownership")
            return

        records = await self.client.execute(
            "MATCH (f:File {project_id: $project_id}) RETURN f.path AS path LIMIT 500",
            {"project_id": self.project_id},
        )
        
        repo_str = str(repo_path)
        ownership_rows = []

        for record in records:
            path = record.get("path")
            if not path:
                continue
            path_obj = await anyio.to_thread.run_sync(lambda p: Path(p).resolve(), path)
            if not str(path_obj).startswith(repo_str):
                continue
            try:
                await anyio.to_thread.run_sync(
                    lambda po, rp: po.relative_to(rp),
                    path_obj,
                    repo_path,
                )
            except ValueError:
                continue

            ownership = ingestor.get_file_ownership(path)
            for owner in ownership:
                ownership_rows.append({
                    "file_path": path,
                    "author_email": owner.developer_email,
                    "author_name": owner.developer_name,
                    "percentage": owner.percentage,
                    "line_count": owner.line_count,
                })

        # Batch insert ownership
        t3 = time.perf_counter()
        for chunk in _chunk_list(ownership_rows, chunk_size=500):
            await set_file_ownership_batch(self.client, chunk, self.project_id)
        logger.info("   👤 %d ownerships in %.1fs", len(ownership_rows), time.perf_counter() - t3)

        git_time = time.perf_counter() - git_start
        logger.info("✅ Git: %d commits, %d ownerships in %.1fs",
                   len(commit_rows), len(ownership_rows), git_time)
