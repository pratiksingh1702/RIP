"""Full indexing pipeline."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from core.graph.builder import GraphBuilder
from core.graph.client import Neo4jClient
from core.graph.schema import setup_schema
from core.parser.base import ParsedFile
from core.parser.registry import LanguageParserRegistry, build_default_registry
from core.parser.traversal import FileTraversal
from core.projects import ProjectRef, ensure_project, project_ref_for_root
from core.search.client import QdrantClientWrapper
from core.search.embedder import EmbeddingPipeline, embedding_dimension
from core.search.indexer import SearchIndexer
from server.config import get_settings

logger = logging.getLogger(__name__)
_WORKER_PARSERS: dict[str, object] = {}


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
    current_stage: str = "Starting"
    status_message: str = "Warming up the indexer."
    structural_ready: bool = False
    parse_time: float = 0.0
    neo4j_time: float = 0.0
    embedding_time: float = 0.0
    qdrant_time: float = 0.0
    git_time: float = 0.0
    total_time: float = 0.0

    def timing_summary(self) -> dict[str, float]:
        total = self.total_time or (
            self.parse_time
            + self.neo4j_time
            + self.embedding_time
            + self.qdrant_time
            + self.git_time
        )
        return {
            "Parsing": self.parse_time,
            "Neo4j": self.neo4j_time,
            "Embeddings": self.embedding_time,
            "Qdrant": self.qdrant_time,
            "Git": self.git_time,
            "Total": total,
        }


@dataclass
class IndexResult:
    phase: str
    files_indexed: int
    semantic_indexing: str
    progress: IndexProgress


@dataclass
class IndexSummary:
    repo_path: str
    indexed_files: int
    total_entities: int
    progress: IndexProgress = field(default_factory=IndexProgress)


def _build_registry() -> LanguageParserRegistry:
    return build_default_registry()


def _get_worker_parser(file_path: Path):
    suffix = file_path.suffix.lower()
    if suffix in _WORKER_PARSERS:
        return _WORKER_PARSERS[suffix]

    if suffix == ".dart":
        from core.parser.languages.dart import DartParser

        parser = DartParser()
    elif suffix == ".py":
        from core.parser.languages.python import PythonParser

        parser = PythonParser()
    elif suffix in {".ts", ".tsx", ".js", ".jsx"}:
        from core.parser.languages.typescript import TypeScriptParser

        parser = TypeScriptParser()
    elif suffix == ".java":
        from core.parser.languages.java import JavaParser

        parser = JavaParser()
    elif suffix == ".go":
        from core.parser.languages.go import GoParser

        parser = GoParser()
    elif suffix == ".rs":
        from core.parser.languages.rust import RustParser

        parser = RustParser()
    else:
        return None

    _WORKER_PARSERS[suffix] = parser
    return parser


def _parse_file_worker(file_path_text: str) -> ParsedFile | str | None:
    file_path = Path(file_path_text)
    parser = _get_worker_parser(file_path)
    if not parser:
        return None
    try:
        content = file_path.read_text(encoding="utf-8")
        return parser.parse_file(file_path, content)
    except SyntaxError as exc:
        return f"syntax:{file_path}:{exc}"
    except Exception as exc:  # noqa: BLE001 - worker errors are reported, not fatal
        return f"error:{file_path}:{exc}"


def _stamp_project(parsed_files: list[ParsedFile], project_id: str) -> None:
    logger.debug("Stamping parsed files with project_id=%s count=%s", project_id, len(parsed_files))
    for parsed_file in parsed_files:
        parsed_file.project_id = project_id
        for entity in parsed_file.entities:
            entity.project_id = project_id
        for relationship in parsed_file.relationships:
            relationship.project_id = project_id


async def _resolve_index_project(repo_path: Path) -> ProjectRef:
    from core.storage.database import async_session_factory, ensure_storage_schema

    ref = project_ref_for_root(repo_path)
    try:
        await ensure_storage_schema()
        async with async_session_factory() as session:
            project = await ensure_project(session, repo_path)
            logger.info(
                "Resolved project metadata: id=%s name=%s root=%s",
                project.id,
                project.name,
                project.root,
            )
            return project
    except Exception as exc:  # noqa: BLE001 - graph/search isolation can still use deterministic id
        logger.warning(
            "Project metadata storage unavailable; using deterministic project id: %s",
            exc,
        )
        return ref


async def parse_files_parallel(
    files: list[Path],
    max_workers: int | None = None,
    progress: IndexProgress | None = None,
    rich_progress = None,
    rich_task = None,
) -> tuple[list[ParsedFile], list[str]]:
    if not files:
        logger.info("No files passed to parser.")
        return [], []

    worker_count = max_workers or min(os.cpu_count() or 1, len(files))
    parsed: list[ParsedFile] = []
    warnings: list[str] = []
    suffixes = {file_path.suffix.lower() for file_path in files}
    logger.info(
        "Parse stage starting: files=%s worker_count=%s suffixes=%s",
        len(files),
        worker_count,
        sorted(suffixes),
    )

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

    logger.info("Parse stage complete: parsed_files=%s warnings=%s", len(parsed), len(warnings))
    return parsed, warnings


class IndexPipeline:
    def __init__(self):
        self._status_callbacks = []

    async def _set_status(self, status: str, data: dict):
        for callback in self._status_callbacks:
            try:
                await callback(status, data)
            except Exception as e:
                logger.error(f"Status callback failed: {e}")

    async def _phase1_parse_and_graph(
        self,
        repo_path: Path,
        client: Neo4jClient,
        progress: IndexProgress,
        project: ProjectRef,
        rich_progress,
        rich_task,
    ) -> tuple[list[ParsedFile], list[str]]:
        if rich_progress and rich_task:
            rich_progress.update(rich_task, description="Preparing graph schema...", total=None)
        progress.current_stage = "Preparing graph"
        progress.status_message = "Checking Neo4j constraints and indexes before writing."
        logger.info("Index stage: preparing Neo4j schema")
        neo4j_start = time.perf_counter()
        await setup_schema(client, progress=progress)
        registry = _build_registry()
        if rich_progress and rich_task:
            rich_progress.update(rich_task, description="Discovering files...", total=None)
        progress.current_stage = "Discovering files"
        progress.status_message = "Scanning the repository and filtering unsupported files."
        logger.info("Index stage: discovering files under %s", repo_path)
        traversal = FileTraversal(registry)
        files = traversal.iter_source_files(repo_path)
        parseable_files = [file_path for file_path in files if registry.get_parser(file_path)]
        progress.files_scanned = len(files)
        progress.files_skipped = len(files) - len(parseable_files)
        logger.info(
            "File discovery complete: scanned=%s parseable=%s skipped=%s",
            progress.files_scanned,
            len(parseable_files),
            progress.files_skipped,
        )
        if rich_progress and rich_task:
            rich_progress.update(
                rich_task,
                description="Parsing files...",
                total=len(parseable_files),
                completed=0,
            )
        progress.current_stage = "Parsing"
        progress.status_message = (
            f"Parsing {len(parseable_files)} source files and extracting entities."
        )

        parse_start = time.perf_counter()
        parsed_files, warnings = await parse_files_parallel(
            parseable_files,
            progress=progress,
            rich_progress=rich_progress,
            rich_task=rich_task,
        )
        progress.parse_time += time.perf_counter() - parse_start
        logger.info("Index timing: parse_time=%.2fs", progress.parse_time)
        _stamp_project(parsed_files, project.id)
        progress.warnings.extend(warnings)

        builder = GraphBuilder(client, project_id=project.id)
        if rich_progress and rich_task:
            rich_progress.update(
                rich_task,
                description="Building graph...",
                total=len(parsed_files),
                completed=0,
            )
        progress.current_stage = "Writing graph"
        progress.status_message = (
            f"Writing {progress.entities_extracted} entities and "
            f"{progress.relationships_extracted} relationships to Neo4j."
        )
        logger.info(
            "Index stage: writing graph files=%s entities=%s relationships=%s",
            len(parsed_files),
            progress.entities_extracted,
            progress.relationships_extracted,
        )
        graph_stats = await builder.build_from_files(parsed_files, progress=progress)
        progress.neo4j_time += time.perf_counter() - neo4j_start
        logger.info("Index timing: neo4j_time=%.2fs", progress.neo4j_time)
        logger.info("Graph write complete: %s", graph_stats)
        progress.neo4j_files_written = graph_stats["files"]
        progress.neo4j_entities_written = graph_stats["entities"]
        progress.neo4j_relationships_written = graph_stats["relationships"]
        progress.structural_ready = True

        return parsed_files, warnings

    async def _phase2_embed_and_store(
        self,
        repo_path: Path,
        neo4j_client: Neo4jClient,
        parsed_files: list[ParsedFile],
        project: ProjectRef,
        qdrant_client: QdrantClientWrapper | None = None,
        embedder: EmbeddingPipeline | None = None,
        progress: IndexProgress | None = None,
        rich_progress = None,
        rich_task = None,
    ):
        from core.storage.database import async_session_factory

        owns_qdrant_client = qdrant_client is None
        if qdrant_client is None:
            settings = get_settings()
            qdrant_client = QdrantClientWrapper(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                vector_size=embedding_dimension(settings.embedding_model),
            )
        try:
            qdrant_start = time.perf_counter()
            await qdrant_client.init_collection()
            if progress:
                progress.qdrant_time += time.perf_counter() - qdrant_start
            logger.info(
                "Qdrant collection initialized: host=%s port=%s",
                qdrant_client.host,
                qdrant_client.port,
            )
            if embedder is None:
                settings = get_settings()
                embedder = EmbeddingPipeline(model_name=settings.embedding_model)
            indexer = SearchIndexer(
                qdrant_client,
                embedder,
                async_session_factory,
                project_id=project.id,
                project_name=project.name,
            )
            file_paths = [parsed_file.file_path for parsed_file in parsed_files]
            all_entities = [
                entity
                for parsed_file in parsed_files
                for entity in parsed_file.entities
            ]
            logger.info(
                "Semantic index stage: parsed_files=%s entities=%s collection_host=%s:%s",
                len(parsed_files),
                len(all_entities),
                qdrant_client.host,
                qdrant_client.port,
            )

            # Check if collection is empty to skip pre-delete
            qdrant_start = time.perf_counter()
            points_count = await qdrant_client.get_points_count()
            if progress:
                progress.qdrant_time += time.perf_counter() - qdrant_start
            if points_count == 0:
                logger.info("Skipping pre-delete — collection is empty.")
                if progress:
                    progress.current_stage = "Embedding"
                    progress.status_message = (
                        f"Generating semantic vectors for {len(all_entities)} entities."
                    )
            else:
                if rich_progress and rich_task:
                    rich_progress.update(
                        rich_task,
                        description="Deleting stale embeddings...",
                        total=len(file_paths),
                        completed=0,
                    )
                if progress:
                    progress.current_stage = "Deleting stale embeddings"
                    progress.status_message = (
                        f"Deleting stale embeddings for {len(file_paths)} files."
                    )
                    logger.info("Deleting stale Qdrant embeddings for %s files", len(file_paths))
                    qdrant_start = time.perf_counter()
                    progress.qdrant_points_deleted = (
                        await indexer.delete_file_embeddings_many(
                            file_paths,
                            progress=progress,
                            rich_progress=rich_progress,
                            rich_task=rich_task
                        )
                    )
                    progress.qdrant_time += time.perf_counter() - qdrant_start

            if rich_progress and rich_task:
                rich_progress.update(
                    rich_task,
                    description="Generating embeddings...",
                    total=len(all_entities),
                    completed=0,
                )
            if progress:
                progress.current_stage = "Embedding"
                progress.status_message = (
                    f"Generating semantic vectors for {len(all_entities)} entities."
                )
                logger.info("Indexing %s entities into Qdrant", len(all_entities))
                progress.qdrant_vectors_stored = (
                    await indexer.index_entities_batched(
                        all_entities,
                        progress=progress,
                        rich_progress=rich_progress,
                        rich_task=rich_task,
                    )
                )
                progress.embeddings_generated = progress.qdrant_vectors_stored
                progress.current_stage = "Git intelligence"
                progress.status_message = "Embedding complete; adding git ownership and churn data."
                logger.info(
                    "Semantic index complete: embeddings_generated=%s qdrant_points_inserted=%s "
                    "qdrant_points_deleted=%s",
                    progress.embeddings_generated,
                    progress.qdrant_vectors_stored,
                    progress.qdrant_points_deleted,
                )

            # Build git data
            builder = GraphBuilder(neo4j_client, project_id=project.id)
            logger.info("Index stage: building git intelligence")
            git_start = time.perf_counter()
            await builder.build_git_data(repo_path)
            if progress:
                progress.git_time += time.perf_counter() - git_start
                logger.info("Index timing: git_time=%.2fs", progress.git_time)
        finally:
            if owns_qdrant_client:
                await qdrant_client.close()

    async def run(
        self,
        repo_path: Path,
        client: Neo4jClient,
        background: bool = True,
        structural_only: bool = False,
        qdrant_client: QdrantClientWrapper | None = None,
        embedder: EmbeddingPipeline | None = None,
        progress: IndexProgress | None = None,
        rich_progress = None,
        rich_task = None,
    ) -> IndexResult:
        if progress is None:
            progress = IndexProgress()
        total_start = time.perf_counter()
        project = await _resolve_index_project(repo_path)

        phase1_start = time.time()
        parsed_files, warnings = await self._phase1_parse_and_graph(
            repo_path, client, progress, project, rich_progress, rich_task
        )
        phase1_duration = time.time() - phase1_start

        await self._set_status("structural_ready", {
            "files": len(parsed_files),
            "duration_seconds": phase1_duration
        })

        if structural_only:
            progress.total_time = time.perf_counter() - total_start
            logger.info("Index timing summary: %s", progress.timing_summary())
            return IndexResult(
                phase="structural_only",
                files_indexed=len(parsed_files),
                semantic_indexing="skipped",
                progress=progress
            )

        if background:
            # Run phase2 in background
            asyncio.create_task(
                self._phase2_embed_and_store(
                    repo_path,
                    client,
                    parsed_files,
                    project,
                    qdrant_client,
                    embedder,
                    progress,
                    rich_progress,
                    rich_task,
                )
            )
            return IndexResult(
                phase="structural_complete",
                files_indexed=len(parsed_files),
                semantic_indexing="background",
                progress=progress
            )
        else:
            # Wait for full completion
            await self._phase2_embed_and_store(
                repo_path,
                client,
                parsed_files,
                project,
                qdrant_client,
                embedder,
                progress,
                rich_progress,
                rich_task,
            )
            progress.total_time = time.perf_counter() - total_start
            logger.info("Index timing summary: %s", progress.timing_summary())
            return IndexResult(
                phase="complete",
                files_indexed=len(parsed_files),
                semantic_indexing="complete",
                progress=progress
            )


# Keep the old functions for backward compatibility
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
    from core.storage.database import async_session_factory

    if progress is None:
        progress = IndexProgress()
    total_start = time.perf_counter()
    project = await _resolve_index_project(repo_path)
    if rich_progress and rich_task:
        rich_progress.update(rich_task, description="Preparing graph schema...", total=None)
    progress.current_stage = "Preparing graph"
    progress.status_message = "Checking Neo4j constraints and indexes before writing."
    logger.info("Index stage: preparing Neo4j schema")
    neo4j_start = time.perf_counter()
    await setup_schema(client, progress=progress)
    registry = _build_registry()
    if rich_progress and rich_task:
        rich_progress.update(rich_task, description="Discovering files...", total=None)
    progress.current_stage = "Discovering files"
    progress.status_message = "Scanning the repository and filtering unsupported files."
    logger.info("Index stage: discovering files under %s", repo_path)
    traversal = FileTraversal(registry)
    files = traversal.iter_source_files(repo_path)
    parseable_files = [file_path for file_path in files if registry.get_parser(file_path)]
    progress.files_scanned = len(files)
    progress.files_skipped = len(files) - len(parseable_files)
    logger.info(
        "File discovery complete: scanned=%s parseable=%s skipped=%s",
        progress.files_scanned,
        len(parseable_files),
        progress.files_skipped,
    )
    if rich_progress and rich_task:
        rich_progress.update(
            rich_task,
            description="Parsing files...",
            total=len(parseable_files),
            completed=0,
        )
    progress.current_stage = "Parsing"
    progress.status_message = (
        f"Parsing {len(parseable_files)} source files and extracting entities."
    )

    parse_start = time.perf_counter()
    parsed_files, warnings = await parse_files_parallel(
        parseable_files,
        progress=progress,
        rich_progress=rich_progress,
        rich_task=rich_task,
    )
    progress.parse_time += time.perf_counter() - parse_start
    logger.info("Index timing: parse_time=%.2fs", progress.parse_time)
    _stamp_project(parsed_files, project.id)
    progress.warnings.extend(warnings)

    builder = GraphBuilder(client, project_id=project.id)
    if rich_progress and rich_task:
        rich_progress.update(
            rich_task,
            description="Building graph...",
            total=len(parsed_files),
            completed=0,
        )
    progress.current_stage = "Writing graph"
    progress.status_message = (
        f"Writing {progress.entities_extracted} entities and "
        f"{progress.relationships_extracted} relationships to Neo4j."
    )
    logger.info(
        "Index stage: writing graph files=%s entities=%s relationships=%s",
        len(parsed_files),
        progress.entities_extracted,
        progress.relationships_extracted,
    )
    graph_stats = await builder.build_from_files(parsed_files, progress=progress)
    progress.neo4j_time += time.perf_counter() - neo4j_start
    logger.info("Index timing: neo4j_time=%.2fs", progress.neo4j_time)
    logger.info("Graph write complete: %s", graph_stats)
    progress.neo4j_files_written = graph_stats["files"]
    progress.neo4j_entities_written = graph_stats["entities"]
    progress.neo4j_relationships_written = graph_stats["relationships"]

    # Structural phase complete
    if rich_progress and rich_task:
        rich_progress.update(
            rich_task,
            description="[yellow]Structural analysis complete![/yellow] Generating embeddings...",
            total=None,
            visible=True,
        )
    progress.current_stage = "Preparing semantic search"
    progress.status_message = "Structural graph is ready; preparing embeddings and Qdrant writes."

    owns_qdrant_client = qdrant_client is None
    if qdrant_client is None:
        settings = get_settings()
        qdrant_client = QdrantClientWrapper(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            vector_size=embedding_dimension(settings.embedding_model),
        )
    try:
        qdrant_start = time.perf_counter()
        await qdrant_client.init_collection()
        progress.qdrant_time += time.perf_counter() - qdrant_start
        logger.info(
            "Qdrant collection initialized: host=%s port=%s",
            qdrant_client.host,
            qdrant_client.port,
        )
        if embedder is None:
            settings = get_settings()
            embedder = EmbeddingPipeline(model_name=settings.embedding_model)
        indexer = SearchIndexer(
            qdrant_client,
            embedder,
            async_session_factory,
            project_id=project.id,
            project_name=project.name,
        )
        file_paths = [parsed_file.file_path for parsed_file in parsed_files]
        all_entities = [entity for parsed_file in parsed_files for entity in parsed_file.entities]
        logger.info(
            "Semantic index stage: parsed_files=%s entities=%s collection_host=%s:%s",
            len(parsed_files),
            len(all_entities),
            qdrant_client.host,
            qdrant_client.port,
        )

        # Check if collection is empty to skip pre-delete
        qdrant_start = time.perf_counter()
        points_count = await qdrant_client.get_points_count()
        progress.qdrant_time += time.perf_counter() - qdrant_start
        if points_count == 0:
            logger.info("Skipping pre-delete — collection is empty.")
            progress.current_stage = "Embedding"
            progress.status_message = (
                f"Generating semantic vectors for {len(all_entities)} entities."
            )
        else:
            if rich_progress and rich_task:
                rich_progress.update(
                    rich_task,
                    description="Deleting stale embeddings...",
                    total=len(file_paths),
                    completed=0,
                )
            progress.current_stage = "Deleting stale embeddings"
            progress.status_message = (
                f"Deleting stale embeddings for {len(file_paths)} files."
            )
            logger.info("Deleting stale Qdrant embeddings for %s files", len(file_paths))
            qdrant_start = time.perf_counter()
            progress.qdrant_points_deleted = (
                await indexer.delete_file_embeddings_many(
                    file_paths,
                    progress=progress,
                    rich_progress=rich_progress,
                    rich_task=rich_task
                )
            )
            progress.qdrant_time += time.perf_counter() - qdrant_start

        if rich_progress and rich_task:
            rich_progress.update(
                rich_task,
                description="Generating embeddings...",
                total=len(all_entities),
                completed=0,
            )
        progress.current_stage = "Embedding"
        progress.status_message = (
            f"Generating semantic vectors for {len(all_entities)} entities."
        )
        logger.info("Indexing %s entities into Qdrant", len(all_entities))
        progress.qdrant_vectors_stored = await indexer.index_entities_batched(
            all_entities,
            progress=progress,
            rich_progress=rich_progress,
            rich_task=rich_task,
        )
        progress.embeddings_generated = progress.qdrant_vectors_stored
        progress.current_stage = "Git intelligence"
        progress.status_message = "Embedding complete; adding git ownership and churn data."
        logger.info(
            "Semantic index complete: embeddings_generated=%s qdrant_points_inserted=%s "
            "qdrant_points_deleted=%s",
            progress.embeddings_generated,
            progress.qdrant_vectors_stored,
            progress.qdrant_points_deleted,
        )

        logger.info("Index stage: building git intelligence")
        git_start = time.perf_counter()
        await builder.build_git_data(repo_path)
        progress.git_time += time.perf_counter() - git_start
        logger.info("Index timing: git_time=%.2fs", progress.git_time)
    finally:
        if owns_qdrant_client:
            await qdrant_client.close()

    for warning in warnings:
        logger.warning("Index parse warning: %s", warning)
    progress.current_stage = "Complete"
    progress.status_message = "Index completed successfully."
    progress.total_time = time.perf_counter() - total_start
    logger.info("Index timing summary: %s", progress.timing_summary())

    return IndexSummary(
        repo_path=str(repo_path),
        indexed_files=len(parsed_files),
        total_entities=progress.entities_extracted,
        progress=progress
    )
