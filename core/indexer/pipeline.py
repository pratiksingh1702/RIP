"""Full indexing pipeline."""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from core.graph.builder import GraphBuilder
from core.graph.client import Neo4jClient
from core.graph.schema import setup_schema
from core.parser.base import ParsedFile
from core.parser.registry import LanguageParserRegistry, build_default_registry
from core.parser.traversal import FileTraversal
from core.search.client import QdrantClientWrapper
from core.search.embedder import EmbeddingPipeline, embedding_dimension
from core.search.indexer import SearchIndexer
from server.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class IndexProgress:
    files_scanned: int = 0
    files_skipped: int = 0
    files_parsed: int = 0
    parse_errors: int = 0
    entities_extracted: int = 0
    relationships_extracted: int = 0
    neo4j_files_written: int = 0
    neo4j_entities_written: int = 0
    neo4j_relationships_written: int = 0
    embeddings_generated: int = 0
    qdrant_points_deleted: int = 0
    qdrant_vectors_stored: int = 0
    warnings: list[str] = field(default_factory=list)
    current_parsing_file: str | None = None
    current_graph_file: str | None = None


@dataclass
class IndexSummary:
    repo_path: str
    indexed_files: int
    total_entities: int
    progress: IndexProgress = field(default_factory=IndexProgress)


def _build_registry() -> LanguageParserRegistry:
    return build_default_registry()


def _parse_file_worker(file_path_text: str) -> ParsedFile | str | None:
    file_path = Path(file_path_text)
    registry = build_default_registry()
    parser = registry.get_parser(file_path)
    if not parser:
        return None
    try:
        content = file_path.read_text(encoding="utf-8")
        return parser.parse_file(file_path, content)
    except SyntaxError as exc:
        return f"syntax:{file_path}:{exc}"
    except Exception as exc:  # noqa: BLE001 - worker errors are reported, not fatal
        return f"error:{file_path}:{exc}"


async def parse_files_parallel(
    files: list[Path],
    max_workers: int | None = None,
    progress: IndexProgress | None = None,
    rich_progress = None,
    rich_task = None,
) -> tuple[list[ParsedFile], list[str]]:
    if not files:
        return [], []

    worker_count = max_workers or min(os.cpu_count() or 1, len(files))
    parsed: list[ParsedFile] = []
    warnings: list[str] = []

    if worker_count <= 1 or len(files) == 1:
        for _i, file_path in enumerate(files):
            if progress:
                progress.current_parsing_file = str(file_path)
            result = _parse_file_worker(str(file_path))
            if isinstance(result, ParsedFile):
                parsed.append(result)
                if progress:
                    progress.files_parsed += 1
                    progress.entities_extracted += len(result.entities)
                    progress.relationships_extracted += len(result.relationships)
                if rich_progress and rich_task:
                    rich_progress.update(rich_task, advance=1)
            elif isinstance(result, str):
                warnings.append(result)
                if progress:
                    progress.parse_errors += 1
                if rich_progress and rich_task:
                    rich_progress.update(rich_task, advance=1)
    else:
        loop = asyncio.get_running_loop()
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            tasks = [
                loop.run_in_executor(executor, _parse_file_worker, str(file_path))
                for file_path in files
            ]
            for i, future in enumerate(asyncio.as_completed(tasks)):
                result = await future
                if progress:
                    progress.current_parsing_file = str(files[i])
                if isinstance(result, ParsedFile):
                    parsed.append(result)
                    if progress:
                        progress.files_parsed += 1
                        progress.entities_extracted += len(result.entities)
                        progress.relationships_extracted += len(result.relationships)
                    if rich_progress and rich_task:
                        rich_progress.update(rich_task, advance=1)
                elif isinstance(result, str):
                    warnings.append(result)
                    if progress:
                        progress.parse_errors += 1
                    if rich_progress and rich_task:
                        rich_progress.update(rich_task, advance=1)

    return parsed, warnings


async def index_repository(repo_path: Path, client: Neo4jClient) -> IndexSummary:
    return await index_repository_with_resources(repo_path, client)


async def index_repository_with_resources(
    repo_path: Path,
    client: Neo4jClient,
    qdrant_client: QdrantClientWrapper | None = None,
    embedder: EmbeddingPipeline | None = None,
    progress: IndexProgress | None = None,
    rich_progress = None,
    rich_task = None,
) -> IndexSummary:
    await setup_schema(client)
    if progress is None:
        progress = IndexProgress()
    registry = _build_registry()
    traversal = FileTraversal(registry)
    files = traversal.iter_source_files(repo_path)
    parseable_files = [file_path for file_path in files if registry.get_parser(file_path)]
    progress.files_scanned = len(files)
    progress.files_skipped = len(files) - len(parseable_files)
    if rich_progress and rich_task:
        rich_progress.update(rich_task, description="Parsing files...", total=len(parseable_files))

    parsed_files, warnings = await parse_files_parallel(
        parseable_files,
        progress=progress,
        rich_progress=rich_progress,
        rich_task=rich_task,
    )
    progress.warnings.extend(warnings)

    builder = GraphBuilder(client)
    if rich_progress and rich_task:
        rich_progress.update(
            rich_task,
            description="Building graph...",
            total=len(parsed_files),
        )
    graph_stats = await builder.build_from_files(parsed_files, progress=progress)
    progress.neo4j_files_written = graph_stats["files"]
    progress.neo4j_entities_written = graph_stats["entities"]
    progress.neo4j_relationships_written = graph_stats["relationships"]

    # Structural phase complete
    if rich_progress and rich_task:
        rich_progress.update(
            rich_task,
            description="[yellow]Structural analysis complete![/yellow] Generating embeddings...",
            visible=True,
        )

    owns_qdrant_client = qdrant_client is None
    if qdrant_client is None:
        settings = get_settings()
        qdrant_client = QdrantClientWrapper(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            vector_size=embedding_dimension(settings.embedding_model),
        )
    try:
        await qdrant_client.init_collection()
        if embedder is None:
            settings = get_settings()
            embedder = EmbeddingPipeline(model_name=settings.embedding_model)
        indexer = SearchIndexer(qdrant_client, embedder)
        file_paths = [parsed_file.file_path for parsed_file in parsed_files]
        all_entities = [entity for parsed_file in parsed_files for entity in parsed_file.entities]
        logger.info(
            "Semantic index stage: parsed_files=%s entities=%s collection_host=%s:%s",
            len(parsed_files),
            len(all_entities),
            qdrant_client.host,
            qdrant_client.port,
        )

        if rich_progress and rich_task:
            rich_progress.update(
                rich_task,
                description="Generating embeddings...",
                total=len(all_entities),
                completed=0,
            )
        progress.qdrant_points_deleted = await indexer.delete_file_embeddings_many(file_paths)
        progress.qdrant_vectors_stored = await indexer.index_entities_batched(
            all_entities,
            progress=progress,
            rich_progress=rich_progress,
            rich_task=rich_task,
        )
        progress.embeddings_generated = progress.qdrant_vectors_stored
        logger.info(
            "Semantic index complete: embeddings_generated=%s qdrant_points_inserted=%s "
            "qdrant_points_deleted=%s",
            progress.embeddings_generated,
            progress.qdrant_vectors_stored,
            progress.qdrant_points_deleted,
        )

        await builder.build_git_data(repo_path)
    finally:
        if owns_qdrant_client:
            await qdrant_client.close()

    for warning in warnings:
        logger.warning("Index parse warning: %s", warning)

    return IndexSummary(
        repo_path=str(repo_path),
        indexed_files=len(parsed_files),
        total_entities=progress.entities_extracted,
        progress=progress,
    )
