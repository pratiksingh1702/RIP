"""Incremental indexing."""

from __future__ import annotations

import hashlib
import logging
import subprocess
import time
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.graph.builder import GraphBuilder
from core.graph.client import Neo4jClient
from core.graph.schema import setup_schema
from core.indexer.pipeline import SUPPORTED_EXTENSIONS, parse_files_streaming
from core.parser.registry import LanguageParserRegistry, build_default_registry
from core.parser.traversal import FileTraversal
from core.projects import ensure_project, project_ref_for_root
from core.search.client import QdrantClientWrapper
from core.search.embedder import EmbeddingPipeline, embedding_dimension
from core.search.indexer import SearchIndexer
from core.storage.models.file_hash import FileHash
from server.config import get_settings

logger = logging.getLogger(__name__)


def calculate_sha256(path: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
    except OSError:
        return ""
    return sha256.hexdigest()


async def _record_file_hash(
    db_session: AsyncSession,
    rel_path: str,
    hash_value: str,
) -> None:
    stmt_select = select(FileHash).where(FileHash.path == rel_path)
    res_sel = await db_session.execute(stmt_select)
    record = res_sel.scalar_one_or_none()
    if record:
        record.hash_value = hash_value
    else:
        db_session.add(FileHash(path=rel_path, hash_value=hash_value))


async def incremental_index(
    repo_path: Path,
    neo_client: Neo4jClient,
    db_session: AsyncSession,
    registry: LanguageParserRegistry | None = None,
) -> dict[str, int]:
    """Perform incremental indexing of the repository."""
    await setup_schema(neo_client)

    if registry is None:
        registry = build_default_registry()

    try:
        from core.storage.database import ensure_storage_schema

        await ensure_storage_schema()
        project = await ensure_project(db_session, repo_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Project metadata storage unavailable; using deterministic id: %s", exc)
        project = project_ref_for_root(repo_path)

    builder = GraphBuilder(neo_client, project_id=project.id)

    traversal = FileTraversal(registry)
    all_files = traversal.iter_source_files(repo_path)

    # 2. Get current hashes of filesystem
    current_hashes: dict[str, str] = {}
    for filepath in all_files:
        rel_path = filepath.relative_to(repo_path).as_posix()
        file_hash = calculate_sha256(filepath)
        if file_hash:
            current_hashes[rel_path] = file_hash

    # 3. Retrieve DB hashes
    stmt = select(FileHash)
    res = await db_session.execute(stmt)
    db_records = res.scalars().all()
    db_hashes = {record.path: record.hash_value for record in db_records}

    # Identify changes
    to_index: list[Path] = []
    to_delete: list[str] = []

    for rel_path, f_hash in current_hashes.items():
        if rel_path not in db_hashes or db_hashes[rel_path] != f_hash:
            to_index.append(repo_path / rel_path)

    for rel_path in db_hashes:
        if rel_path not in current_hashes:
            to_delete.append(rel_path)

    if not to_index and not to_delete:
        return {
            "updated": 0,
            "deleted": 0,
            "skipped": len(current_hashes),
        }

    deleted_count = 0
    updated_count = 0
    parsed_files = []
    delete_paths = []
    hash_only_paths: list[str] = []

    # Parse changed files before starting Qdrant/model work. Files with stable
    # syntax errors are hash-recorded so unchanged incremental runs can skip them.
    for filepath in to_index:
        rel_path = filepath.relative_to(repo_path).as_posix()
        try:
            content = filepath.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Skipping unreadable file %s: %s", filepath, exc)
            continue

        parser = registry.get_parser(filepath)
        if not parser:
            hash_only_paths.append(rel_path)
            continue

        try:
            parsed_file = parser.parse_file(filepath, content)
        except SyntaxError as exc:
            logger.warning("Skipping syntax-invalid file %s: %s", filepath, exc)
            hash_only_paths.append(rel_path)
            continue
        except Exception as exc:  # noqa: BLE001 - one bad file should not abort indexing
            logger.warning("Skipping unparsable file %s: %s", filepath, exc)
            hash_only_paths.append(rel_path)
            continue

        parsed_file.file_path = rel_path
        parsed_file.project_id = project.id
        for entity in parsed_file.entities:
            entity.project_id = project.id
        for relationship in parsed_file.relationships:
            relationship.project_id = project.id
        parsed_files.append(parsed_file)
        delete_paths.extend([rel_path, str(filepath.resolve())])

    if not parsed_files and not to_delete:
        for rel_path in hash_only_paths:
            await _record_file_hash(db_session, rel_path, current_hashes[rel_path])
        if hash_only_paths:
            await db_session.commit()
        return {
            "updated": 0,
            "deleted": 0,
            "skipped": len(current_hashes),
        }

    settings = get_settings()
    qdrant_client = QdrantClientWrapper(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        vector_size=embedding_dimension(settings.embedding_model),
    )
    await qdrant_client.init_collection()

    try:
        delete_indexer = SearchIndexer(qdrant_client, None, project_id=project.id)

        # Perform deletions
        for rel_path in to_delete:
            delete_query = """
            MATCH (f:File)
            WHERE f.project_id = $project_id
              AND (f.path = $rel_path OR f.path ENDS WITH $suffix)
            OPTIONAL MATCH (f)-[:CONTAINS]->(e)
            DETACH DELETE f, e
            """
            suffix = "/" + rel_path.lstrip("/")
            await neo_client.execute(
                delete_query,
                {"rel_path": rel_path, "suffix": suffix, "project_id": project.id},
            )

            await delete_indexer.delete_file_embeddings_many(
                [rel_path, str((repo_path / rel_path).resolve())]
            )
            logger.info("Incremental Qdrant delete requested for removed file: %s", rel_path)
            await db_session.execute(delete(FileHash).where(FileHash.path == rel_path))
            deleted_count += 1

        if parsed_files:
            await builder.build_from_files(parsed_files)
            qdrant_delete_batches = await delete_indexer.delete_file_embeddings_many(delete_paths)
            embedder = EmbeddingPipeline(model_name=settings.embedding_model)
            indexer = SearchIndexer(
                qdrant_client,
                embedder,
                project_id=project.id,
                project_name=project.name,
            )
            all_entities = [
                entity for parsed_file in parsed_files for entity in parsed_file.entities
            ]
            qdrant_vectors_stored = await indexer.index_entities_batched(all_entities)
            logger.info(
                "Incremental semantic index complete: parsed_files=%s embeddings_generated=%s "
                "qdrant_points_inserted=%s qdrant_delete_batches=%s",
                len(parsed_files),
                qdrant_vectors_stored,
                qdrant_vectors_stored,
                qdrant_delete_batches,
            )

            for parsed_file in parsed_files:
                rel_path = parsed_file.file_path
                await _record_file_hash(db_session, rel_path, current_hashes[rel_path])
                updated_count += 1

        for rel_path in hash_only_paths:
            await _record_file_hash(db_session, rel_path, current_hashes[rel_path])

        # Build git data
        if updated_count > 0 or deleted_count > 0:
            await builder.build_git_data(repo_path)
        await db_session.commit()
    finally:
        await qdrant_client.close()

    return {
        "updated": updated_count,
        "deleted": deleted_count,
        "skipped": len(current_hashes) - updated_count,
    }


def _git_lines(repo_path: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.debug("git %s failed: %s", " ".join(args), result.stderr.strip())
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _is_supported_source(path: str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def _smart_changed_files(repo_path: Path) -> tuple[list[Path], list[str]]:
    changed: set[str] = set()
    deleted: set[str] = set()

    for args in (
        ("diff", "--name-only", "--diff-filter=ACMR", "HEAD"),
        ("diff", "--name-only", "--cached", "--diff-filter=ACMR"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        changed.update(_git_lines(repo_path, *args))

    deleted.update(_git_lines(repo_path, "diff", "--name-only", "--diff-filter=D", "HEAD"))
    deleted.update(_git_lines(repo_path, "diff", "--name-only", "--cached", "--diff-filter=D"))

    if not changed and not deleted:
        changed.update(_git_lines(repo_path, "diff", "--name-only", "--diff-filter=ACMR", "HEAD~1"))
        deleted.update(_git_lines(repo_path, "diff", "--name-only", "--diff-filter=D", "HEAD~1"))

    changed_paths = [
        (repo_path / rel_path).resolve()
        for rel_path in sorted(changed)
        if _is_supported_source(rel_path) and (repo_path / rel_path).exists()
    ]
    deleted_paths = sorted(rel_path for rel_path in deleted if _is_supported_source(rel_path))
    return changed_paths, deleted_paths


async def smart_index(
    repo_path: Path,
    neo_client: Neo4jClient,
    db_session: AsyncSession,
    registry: LanguageParserRegistry | None = None,
) -> dict[str, int | float]:
    """Perform git-diff based indexing of changed, untracked, and deleted files."""
    start = time.perf_counter()
    await setup_schema(neo_client)

    if registry is None:
        registry = build_default_registry()

    try:
        from core.storage.database import ensure_storage_schema

        await ensure_storage_schema()
        project = await ensure_project(db_session, repo_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Project metadata storage unavailable; using deterministic id: %s", exc)
        project = project_ref_for_root(repo_path)

    changed_files, deleted_files = _smart_changed_files(repo_path)
    if not changed_files and not deleted_files:
        return {"updated": 0, "deleted": 0, "skipped": 0, "entities": 0, "duration": 0.0}

    builder = GraphBuilder(neo_client, project_id=project.id)
    parsed_files = []
    async for parsed_file, warning in parse_files_streaming(changed_files, registry):
        if warning:
            logger.warning("Smart index skipped file: %s", warning)
            continue
        if parsed_file is None:
            continue
        parsed_path = Path(parsed_file.file_path).resolve()
        rel_path = parsed_path.relative_to(repo_path).as_posix()
        parsed_file.file_path = rel_path
        parsed_file.project_id = project.id
        for entity in parsed_file.entities:
            entity.file_path = rel_path
            entity.project_id = project.id
        for relationship in parsed_file.relationships:
            relationship.file_path = rel_path
            relationship.project_id = project.id
        parsed_files.append(parsed_file)

    settings = get_settings()
    qdrant_client = QdrantClientWrapper(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        vector_size=embedding_dimension(settings.embedding_model),
    )
    await qdrant_client.init_collection()

    updated_count = 0
    deleted_count = 0
    entity_count = 0
    try:
        delete_indexer = SearchIndexer(qdrant_client, None, project_id=project.id)
        for rel_path in deleted_files:
            suffix = "/" + rel_path.lstrip("/")
            await neo_client.execute(
                """
                MATCH (f:File)
                WHERE f.project_id = $project_id
                  AND (f.path = $rel_path OR replace(f.path, "\\\\", "/") ENDS WITH $suffix)
                OPTIONAL MATCH (f)-[:CONTAINS]->(e)
                OPTIONAL MATCH (m:Module)-[:REPRESENTS]->(f)
                DETACH DELETE f, e, m
                """,
                {"rel_path": rel_path, "suffix": suffix, "project_id": project.id},
            )
            await delete_indexer.delete_file_embeddings_many(
                [rel_path, str((repo_path / rel_path).resolve())]
            )
            await db_session.execute(delete(FileHash).where(FileHash.path == rel_path))
            deleted_count += 1

        if parsed_files:
            delete_paths = []
            for parsed_file in parsed_files:
                rel_path = parsed_file.file_path
                delete_paths.extend([rel_path, str((repo_path / rel_path).resolve())])
                await builder.delete_file_entities(rel_path, project_id=project.id)
                await _record_file_hash(
                    db_session,
                    rel_path,
                    calculate_sha256(repo_path / rel_path),
                )

            await builder.build_from_files(parsed_files)
            await delete_indexer.delete_file_embeddings_many(delete_paths)
            embedder = EmbeddingPipeline(model_name=settings.embedding_model)
            indexer = SearchIndexer(
                qdrant_client,
                embedder,
                project_id=project.id,
                project_name=project.name,
            )
            entities = [entity for parsed_file in parsed_files for entity in parsed_file.entities]
            entity_count = len(entities)
            await indexer.index_entities_batched(entities)
            updated_count = len(parsed_files)

        if updated_count > 0 or deleted_count > 0:
            await builder.build_git_data(repo_path)
        await db_session.commit()
    finally:
        await qdrant_client.close()

    return {
        "updated": updated_count,
        "deleted": deleted_count,
        "skipped": 0,
        "entities": entity_count,
        "duration": time.perf_counter() - start,
    }
