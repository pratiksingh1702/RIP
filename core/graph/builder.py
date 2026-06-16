"""Graph builder."""

from __future__ import annotations

from pathlib import Path

from core.graph.client import Neo4jClient
from core.parser.base import ParsedFile

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
    def __init__(self, client: Neo4jClient) -> None:
        self.client = client

    async def build_from_file(self, parsed_file: ParsedFile) -> None:
        await self._upsert_file(parsed_file)
        for entity in parsed_file.entities:
            await self._upsert_entity(parsed_file, entity.__dict__)
        for relationship in parsed_file.relationships:
            await self._upsert_relationship(relationship.__dict__)

    async def build_from_files(
        self,
        parsed_files: list[ParsedFile],
        progress: object | None = None,
    ) -> dict[str, int]:
        """Batch write parsed files while preserving existing graph semantics."""
        if not parsed_files:
            return {"files": 0, "entities": 0, "relationships": 0}

        await self._upsert_files_batch(parsed_files)
        entity_count = await self._upsert_entities_batch(parsed_files)
        relationship_count = await self._upsert_relationships_batch(parsed_files)
        return {
            "files": len(parsed_files),
            "entities": entity_count,
            "relationships": relationship_count,
        }

    async def delete_file_entities(self, file_path: str) -> None:
        await self.client.execute(
            """
            MATCH (f:File {path: $file_path})-[:CONTAINS]->(entity)
            DETACH DELETE entity
            """,
            {"file_path": file_path},
        )

    async def _upsert_file(self, parsed_file: ParsedFile) -> None:
        await self.client.execute(
            """
            MERGE (f:File {path: $path})
            SET f.language = $language,
                f.sha256_hash = $sha256_hash
            MERGE (m:Module {name: $module_name})
            SET m.file_path = $path,
                m.language = $language
            MERGE (m)-[:REPRESENTS]->(f)
            """,
            {
                "path": parsed_file.file_path,
                "language": parsed_file.language,
                "sha256_hash": parsed_file.sha256_hash,
                "module_name": _module_name(parsed_file.file_path),
            },
        )

    async def _upsert_files_batch(self, parsed_files: list[ParsedFile]) -> None:
        rows = [
            {
                "path": parsed_file.file_path,
                "language": parsed_file.language,
                "sha256_hash": parsed_file.sha256_hash,
                "module_name": _module_name(parsed_file.file_path),
            }
            for parsed_file in parsed_files
        ]
        await self.client.execute(
            """
            UNWIND $rows AS row
            MERGE (f:File {path: row.path})
            SET f.language = row.language,
                f.sha256_hash = row.sha256_hash
            MERGE (m:Module {name: row.module_name})
            SET m.file_path = row.path,
                m.language = row.language
            MERGE (m)-[:REPRESENTS]->(f)
            """,
            {"rows": rows},
        )

    async def _upsert_entity(self, parsed_file: ParsedFile, entity: dict[str, object]) -> None:
        label = ENTITY_LABELS.get(str(entity["entity_type"]), "Function")
        await self.client.execute(
            f"""
            MATCH (f:File {{path: $file_path}})
            MERGE (e:{label} {{fqn: $fqn}})
            SET e.name = $name,
                e.file_path = $file_path,
                e.line_start = $line_start,
                e.line_end = $line_end,
                e.language = $language,
                e.docstring = $docstring,
                e.decorators = $decorators,
                e.is_exported = $is_exported,
                e.raw_code = $raw_code
            MERGE (f)-[:CONTAINS]->(e)
            """,
            {
                **entity,
                "file_path": parsed_file.file_path,
            },
        )

    async def _upsert_entities_batch(self, parsed_files: list[ParsedFile]) -> int:
        count = 0
        rows_by_label: dict[str, list[dict[str, object]]] = {}
        for parsed_file in parsed_files:
            for entity in parsed_file.entities:
                row = {**entity.__dict__, "file_path": parsed_file.file_path}
                label = ENTITY_LABELS.get(entity.entity_type, "Function")
                rows_by_label.setdefault(label, []).append(row)
                count += 1

        for label, rows in rows_by_label.items():
            await self.client.execute(
                f"""
                UNWIND $rows AS row
                MATCH (f:File {{path: row.file_path}})
                MERGE (e:{label} {{fqn: row.fqn}})
                SET e.name = row.name,
                    e.file_path = row.file_path,
                    e.line_start = row.line_start,
                    e.line_end = row.line_end,
                    e.language = row.language,
                    e.docstring = row.docstring,
                    e.decorators = row.decorators,
                    e.is_exported = row.is_exported,
                    e.raw_code = row.raw_code
                MERGE (f)-[:CONTAINS]->(e)
                """,
                {"rows": rows},
            )
        return count

    async def _upsert_relationship(self, relationship: dict[str, object]) -> None:
        rel_type = str(relationship["relationship_type"])
        row = {**relationship, "to_name": _symbol_name(str(relationship["to_fqn"]))}
        if rel_type == "CALLS":
            await self.client.execute(
                """
                MATCH (source {fqn: $from_fqn})
                MERGE (target:Function {fqn: $to_fqn})
                ON CREATE SET target.name = $to_name, target.file_path = $file_path
                MERGE (source)-[r:CALLS]->(target)
                SET r.file_path = $file_path,
                    r.line = $line
                """,
                row,
            )
        elif rel_type == "IMPORTS":
            await self.client.execute(
                """
                MATCH (file:File {path: $file_path})
                MERGE (module:Module {name: $to_fqn})
                MERGE (file)-[r:IMPORTS]->(module)
                SET r.line = $line
                WITH file, module
                MATCH (source_module:Module)-[:REPRESENTS]->(file)
                MERGE (source_module)-[:DEPENDS_ON]->(module)
                """,
                row,
            )
        elif rel_type == "EXTENDS":
            await self.client.execute(
                """
                MATCH (source:Class {fqn: $from_fqn})
                MERGE (target:Class {name: $to_name})
                ON CREATE SET target.fqn = $to_fqn, target.file_path = $file_path
                MERGE (source)-[r:EXTENDS]->(target)
                SET r.file_path = $file_path,
                    r.line = $line
                """,
                row,
            )
        elif rel_type == "IMPLEMENTS":
            await self.client.execute(
                """
                MATCH (source:Class {fqn: $from_fqn})
                MERGE (target:Interface {name: $to_name})
                ON CREATE SET target.fqn = $to_fqn, target.file_path = $file_path
                MERGE (source)-[r:IMPLEMENTS]->(target)
                SET r.file_path = $file_path,
                    r.line = $line
                """,
                row,
            )
        elif rel_type == "CONTAINS":
            await self.client.execute(
                """
                MATCH (source {fqn: $from_fqn})
                MATCH (target {fqn: $to_fqn})
                MERGE (source)-[r:CONTAINS]->(target)
                SET r.file_path = $file_path,
                    r.line = $line
                """,
                row,
            )

    async def _upsert_relationships_batch(self, parsed_files: list[ParsedFile]) -> int:
        count = 0
        rows_by_type: dict[str, list[dict[str, object]]] = {}
        allowed = {"CALLS", "IMPORTS", "EXTENDS", "IMPLEMENTS", "CONTAINS"}
        for parsed_file in parsed_files:
            for relationship in parsed_file.relationships:
                rel_type = relationship.relationship_type
                if rel_type not in allowed:
                    continue
                rows_by_type.setdefault(rel_type, []).append(
                    {**relationship.__dict__, "to_name": _symbol_name(relationship.to_fqn)}
                )
                count += 1

        if rows := rows_by_type.get("CALLS"):
            await self.client.execute(
                """
                UNWIND $rows AS row
                MATCH (source {fqn: row.from_fqn})
                MERGE (target:Function {fqn: row.to_fqn})
                ON CREATE SET target.name = row.to_name, target.file_path = row.file_path
                MERGE (source)-[r:CALLS]->(target)
                SET r.file_path = row.file_path,
                    r.line = row.line
                """,
                {"rows": rows},
            )
        if rows := rows_by_type.get("IMPORTS"):
            await self.client.execute(
                """
                UNWIND $rows AS row
                MATCH (file:File {path: row.file_path})
                MERGE (module:Module {name: row.to_fqn})
                MERGE (file)-[r:IMPORTS]->(module)
                SET r.line = row.line
                WITH file, module
                MATCH (source_module:Module)-[:REPRESENTS]->(file)
                MERGE (source_module)-[:DEPENDS_ON]->(module)
                """,
                {"rows": rows},
            )
        if rows := rows_by_type.get("EXTENDS"):
            await self.client.execute(
                """
                UNWIND $rows AS row
                MATCH (source:Class {fqn: row.from_fqn})
                MERGE (target:Class {name: row.to_name})
                ON CREATE SET target.fqn = row.to_fqn, target.file_path = row.file_path
                MERGE (source)-[r:EXTENDS]->(target)
                SET r.file_path = row.file_path,
                    r.line = row.line
                """,
                {"rows": rows},
            )
        if rows := rows_by_type.get("IMPLEMENTS"):
            await self.client.execute(
                """
                UNWIND $rows AS row
                MATCH (source:Class {fqn: row.from_fqn})
                MERGE (target:Interface {name: row.to_name})
                ON CREATE SET target.fqn = row.to_fqn, target.file_path = row.file_path
                MERGE (source)-[r:IMPLEMENTS]->(target)
                SET r.file_path = row.file_path,
                    r.line = row.line
                """,
                {"rows": rows},
            )
        if rows := rows_by_type.get("CONTAINS"):
            await self.client.execute(
                """
                UNWIND $rows AS row
                MATCH (source {fqn: row.from_fqn})
                MATCH (target {fqn: row.to_fqn})
                MERGE (source)-[r:CONTAINS]->(target)
                SET r.file_path = row.file_path,
                    r.line = row.line
                """,
                {"rows": rows},
            )
        return count

    async def build_git_data(self, repo_path: Path) -> None:
        """Extract and insert Git commits, developers, modifications, and ownership info."""
        import anyio

        from core.graph.queries.ownership import (
            create_developer_and_commit,
            relate_commit_to_file,
            set_file_ownership,
        )
        from core.parser.git_ingestor import GitIngestor

        repo_path = await anyio.to_thread.run_sync(lambda p: p.resolve(), repo_path)
        ingestor = GitIngestor(repo_path)
        if not ingestor.is_git_repo:
            return

        commits = ingestor.get_commits(limit=100)
        for commit in commits:
            await create_developer_and_commit(
                self.client,
                commit_hash=commit.hash,
                message=commit.message,
                timestamp_str=commit.timestamp.isoformat(),
                author_name=commit.author_name,
                author_email=commit.author_email,
            )
            for file_path in commit.files_modified:
                abs_path = await anyio.to_thread.run_sync(
                    lambda r, f: str((r / f).resolve()), repo_path, file_path
                )
                await relate_commit_to_file(self.client, commit.hash, abs_path)

        records = await self.client.execute("MATCH (f:File) RETURN f.path AS path")
        repo_str = str(repo_path)
        for record in records:
            path = record.get("path")
            if not path:
                continue
            path_obj = await anyio.to_thread.run_sync(
                lambda p: Path(p).resolve(), path
            )
            if not str(path_obj).startswith(repo_str):
                continue  # Not in current repo at all, skip everything
            try:
                await anyio.to_thread.run_sync(
                    lambda po, rp: po.relative_to(rp),
                    path_obj, repo_path
                )
            except ValueError:
                continue  # Not in current repo, skip

            ownership = ingestor.get_file_ownership(path)
            for owner in ownership:
                await set_file_ownership(
                    self.client,
                    file_path=path,
                    author_email=owner.developer_email,
                    author_name=owner.developer_name,
                    percentage=owner.percentage,
                    line_count=owner.line_count,
                )
