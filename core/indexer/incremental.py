"""Incremental indexing."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.graph.builder import GraphBuilder
from core.graph.client import Neo4jClient
from core.graph.schema import setup_schema
from core.parser.registry import LanguageParserRegistry, build_default_registry
from core.parser.traversal import FileTraversal
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

    builder = GraphBuilder(neo_client)

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
        delete_indexer = SearchIndexer(qdrant_client, None)

        # Perform deletions
        for rel_path in to_delete:
            delete_query = """
            MATCH (f:File)
            WHERE f.path = $rel_path OR f.path ENDS WITH $suffix
            OPTIONAL MATCH (f)-[:CONTAINS]->(e)
            DETACH DELETE f, e
            """
            suffix = "/" + rel_path.lstrip("/")
            await neo_client.execute(delete_query, {"rel_path": rel_path, "suffix": suffix})

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
            indexer = SearchIndexer(qdrant_client, embedder)
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
