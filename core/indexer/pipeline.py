"""Full indexing pipeline - optimized for speed, accuracy, and detailed logging."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import AsyncGenerator
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from core.graph.builder import GraphBuilder
from core.graph.client import Neo4jClient
from core.graph.schema import setup_schema
from core.parser.base import ParsedFile
from core.parser.registry import build_default_registry
from core.projects import ProjectRef, ensure_project, project_ref_for_root
from core.search.client import QdrantClientWrapper
from core.search.embedder import EmbeddingPipeline, embedding_dimension
from core.search.indexer import SearchIndexer
from server.config import get_settings

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================
MEMORY_THRESHOLD = 0.85
MAX_PARALLEL_WORKERS = min(os.cpu_count() or 4, 8)  # Cap at 8 to avoid thrashing
MIN_FILE_SIZE_FOR_PARALLEL = 256
GRAPH_WRITE_BATCH = 200
EMBEDDING_BATCH = 200  # Smaller batches for better parallelism
PARSE_TIMEOUT = 30  # 30s per file
FIRST_BATCH_TIMEOUT = 90  # 90s for first batch (ProcessPool startup)
LOG_PROGRESS_INTERVAL = 50
FLUSH_TIMEOUT = 15
MAX_STUCK_BEFORE_SKIP = 3  # 3 timeouts = 90s before force-skipping all

SKIP_DIRS = frozenset({
    '.git', 'node_modules', '__pycache__', '.venv', 'venv',
    '.repo-intel', '.idea', '.vscode', 'dist', 'build',
    '.next', '.nuxt', 'target', 'bin', 'obj', '.tox',
    'eggs', '.eggs', '.mypy_cache', '.pytest_cache',
    '.ruff_cache', 'htmlcov', '.coverage', 'site-packages',
    'bower_components', 'jspm_packages', '.yarn', '.turbo',
    '.cache', 'coverage', 'out', 'output',
})

SUPPORTED_EXTENSIONS = frozenset({
    '.py', '.ts', '.tsx', '.js', '.jsx', '.java', '.go', '.rs', '.dart'
})

# ============================================================================
# SKIP FUNCTIONALITY
# ============================================================================

class SkipFileException(Exception):
    pass

_skip_requested = False

def request_skip():
    global _skip_requested
    _skip_requested = True

def check_skip():
    global _skip_requested
    if _skip_requested:
        _skip_requested = False
        raise SkipFileException("File skipped by user")

def reset_skip():
    global _skip_requested
    _skip_requested = False

# ============================================================================
# PARSER CACHE - with error handling
# ============================================================================

@lru_cache(maxsize=16)
def _get_worker_parser_cached(suffix: str):
    """Cached parser factory - returns None if parser unavailable."""
    try:
        if suffix == ".dart":
            from core.parser.languages.dart import DartParser
            return DartParser()
        elif suffix == ".py":
            from core.parser.languages.python import PythonParser
            return PythonParser()
        elif suffix in {".ts", ".tsx", ".js", ".jsx"}:
            from core.parser.languages.typescript import TypeScriptParser
            return TypeScriptParser()
        elif suffix == ".java":
            from core.parser.languages.java import JavaParser
            return JavaParser()
        elif suffix == ".go":
            from core.parser.languages.go import GoParser
            return GoParser()
        elif suffix == ".rs":
            from core.parser.languages.rust import RustParser
            return RustParser()
    except Exception as e:
        logger.debug("Parser unavailable for %s: %s", suffix, str(e)[:80])
    return None

# ============================================================================
# DATA CLASSES
# ============================================================================

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
    current_file_size: int = 0
    current_file_entities: int = 0
    current_file_duration: float = 0.0
    skipped_files: list[str] = field(default_factory=list)
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
    memory_mb: float = 0.0
    batches_completed: int = 0
    stage_start_time: float = 0.0
    discovery_time: float = 0.0

    def timing_summary(self) -> dict[str, float]:
        total = self.total_time or (self.parse_time + self.neo4j_time + self.embedding_time + self.qdrant_time + self.git_time + self.discovery_time)
        return {"Discovery": self.discovery_time, "Parsing": self.parse_time, "Neo4j": self.neo4j_time, "Embeddings": self.embedding_time, "Qdrant": self.qdrant_time, "Git": self.git_time, "Total": total}

    def get_stage_elapsed(self) -> float:
        return time.perf_counter() - self.stage_start_time if self.stage_start_time else 0.0

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
    languages_detected: list[str] = field(default_factory=list)

# ============================================================================
# WORKER - with detailed diagnostics
# ============================================================================

def _parse_file_worker_optimized(args: tuple) -> tuple:
    """Parse a single file. Returns (path, result_or_error, time, size, skipped)."""
    file_path_str, registry_suffix = args
    file_path = Path(file_path_str)
    start = time.perf_counter()

    parser = _get_worker_parser_cached(registry_suffix)
    if not parser:
        return (file_path_str, None, time.perf_counter() - start, 0, True)

    try:
        file_size = file_path.stat().st_size
        content = file_path.read_text(encoding="utf-8", errors="replace")
        result = parser.parse_file(file_path, content)
        elapsed = time.perf_counter() - start
        if elapsed > 5:
            logger.warning("🐌 Slow file: %s took %.1fs (%d bytes)", file_path.name, elapsed, file_size)
        return (file_path_str, result, elapsed, file_size, False)
    except Exception as exc:
        elapsed = time.perf_counter() - start
        logger.error("❌ Worker failed %s (%.1fs): %s", file_path.name, elapsed, str(exc)[:150])
        return (file_path_str, f"error:{file_path}:{exc}", elapsed, 0, False)

# ============================================================================
# FAST FILE DISCOVERY
# ============================================================================

def _scan_directory_fast(root: Path) -> tuple[list[Path], int, int]:
    parseable, scanned, skipped = [], 0, 0
    dirs = [str(root)]
    while dirs:
        d = dirs.pop()
        try:
            with os.scandir(d) as it:
                for entry in it:
                    scanned += 1
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name.startswith('.') or entry.name in SKIP_DIRS:
                            skipped += 1
                            continue
                        dirs.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        if os.path.splitext(entry.name)[1].lower() in SUPPORTED_EXTENSIONS:
                            parseable.append(Path(entry.path))
                        else:
                            skipped += 1
        except (PermissionError, OSError):
            pass
    return parseable, scanned, skipped

async def _discover_files_fast(repo_path: Path, registry, progress: IndexProgress) -> list[Path]:
    progress.current_stage = "Discovering files"
    progress.status_message = "Scanning repository..."
    progress.stage_start_time = time.perf_counter()
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=8) as pool:
        parseable, scanned, skipped = await loop.run_in_executor(pool, _scan_directory_fast, repo_path)
    progress.files_scanned = scanned
    progress.files_skipped = skipped
    progress.discovery_time = time.perf_counter() - progress.stage_start_time
    logger.info("📁 Discovery: %d scanned → %d parseable, %d skipped in %.2fs", scanned, len(parseable), skipped, progress.discovery_time)
    return parseable

# ============================================================================
# STREAMING PARSE - FIXED WITH PROPER TIMEOUT HANDLING
# ============================================================================

async def parse_files_streaming(
    files: list[Path], registry, max_workers: int | None = None,
    progress: IndexProgress | None = None,
) -> AsyncGenerator[tuple[ParsedFile | None, str | None], None]:
    if not files:
        return

    worker_count = max_workers or min(MAX_PARALLEL_WORKERS, len(files))
    total_files = len(files)
    completed = 0
    total_entities = 0
    total_relationships = 0
    skipped_count = 0
    parse_start = time.perf_counter()
    reset_skip()

    logger.info("🚀 Parsing %d files with %d workers", total_files, worker_count)

    # Split by size
    small_files, large_files = [], []
    for fp in files:
        try:
            if fp.stat().st_size < MIN_FILE_SIZE_FOR_PARALLEL:
                small_files.append(fp)
            else:
                large_files.append(fp)
        except OSError:
            small_files.append(fp)

    # Skip generated files
    small_files = [f for f in small_files if not f.name.endswith(('.g.dart', '.freezed.dart', '.g.'))]
    large_files = [f for f in large_files if not f.name.endswith(('.g.dart', '.freezed.dart', '.g.'))]

    logger.info("📄 %d small, 📦 %d large", len(small_files), len(large_files))

    # ========================================================================
    # Process small files sequentially
    # ========================================================================
    for file_path in small_files:
        file_name = file_path.name
        if progress:
            progress.current_parsing_file = str(file_path)
            progress.status_message = f"{completed + 1}/{total_files}: {file_name}"
            progress.current_file_entities = 0
            progress.current_file_duration = 0.0

        try:
            check_skip()
            _, result, ptime, fsize, skipped = _parse_file_worker_optimized(
                (str(file_path), file_path.suffix.lower())
            )

            if skipped:
                skipped_count += 1
                if progress: progress.skipped_files.append(str(file_path))
                yield (None, f"skipped:{file_path}")
            elif isinstance(result, ParsedFile):
                ecount = len(result.entities); rcount = len(result.relationships)
                total_entities += ecount; total_relationships += rcount
                if progress:
                    progress.current_file_entities = ecount; progress.current_file_duration = ptime
                    progress.current_file_size = fsize; progress.files_parsed += 1
                    progress.entities_extracted += ecount; progress.relationships_extracted += rcount
                logger.debug("✅ %s: %d entities, %d rels, %.0fms", file_name, ecount, rcount, ptime * 1000)
                yield (result, None)
            elif isinstance(result, str):
                if progress: progress.parse_errors += 1
                logger.warning("❌ %s: %s", file_name, result.split(":", 2)[-1][:100] if ":" in result else result[:100])
                yield (None, result)
        except SkipFileException:
            skipped_count += 1
            if progress: progress.skipped_files.append(str(file_path))
            yield (None, f"skipped:{file_path}")

        completed += 1
        if completed % LOG_PROGRESS_INTERVAL == 0:
            elapsed = time.perf_counter() - parse_start
            logger.info("📊 Parse: %d/%d (%.0f%%) %.0f f/s | %d entities | %d skipped",
                       completed, total_files, completed/total_files*100,
                       completed/elapsed if elapsed > 0 else 0, total_entities, skipped_count)

    # ========================================================================
    # Process large files in parallel
    # ========================================================================
    if large_files:
        loop = asyncio.get_running_loop()
        worker_args = [(str(fp), fp.suffix.lower()) for fp in large_files]

        logger.info("⚡ Starting ProcessPoolExecutor with %d workers for %d files", worker_count, len(large_files))
        
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            future_to_file = {}
            for arg, fp in zip(worker_args, large_files):
                future = loop.run_in_executor(executor, _parse_file_worker_optimized, arg)
                future_to_file[future] = fp

            pending = set(future_to_file.keys())
            stuck_count = 0
            is_first_batch = True
            
            while pending:
                # Use longer timeout for first batch (ProcessPool startup overhead)
                timeout = FIRST_BATCH_TIMEOUT if is_first_batch else PARSE_TIMEOUT
                
                try:
                    done, pending = await asyncio.wait(pending, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
                except Exception as e:
                    logger.error("asyncio.wait error: %s - cancelling all", e)
                    for f in pending: f.cancel()
                    break
                
                is_first_batch = False  # After first batch, use normal timeout
                
                if not done:
                    stuck_count += 1
                    logger.warning("⏰ Stuck #%d - %d files remaining (timeout=%ds)", stuck_count, len(pending), timeout)
                    
                    if stuck_count >= MAX_STUCK_BEFORE_SKIP:
                        logger.error("🚫 Force-skipping all %d stuck files after %d timeouts", len(pending), stuck_count)
                        for f in list(pending):
                            fp = future_to_file.get(f, Path("unknown"))
                            f.cancel()
                            pending.discard(f)
                            if progress: progress.skipped_files.append(str(fp))
                            yield (None, f"timeout:{fp}")
                            completed += 1
                        break
                    
                    # Cancel ONE stuck future
                    stuck = list(pending)[0]
                    sp = future_to_file.get(stuck, Path("unknown"))
                    stuck.cancel()
                    pending.discard(stuck)
                    logger.warning("⏭ Cancelled stuck file: %s", sp)
                    if progress: progress.skipped_files.append(str(sp))
                    yield (None, f"timeout:{sp}")
                    completed += 1
                    continue
                
                stuck_count = 0  # Reset on success
                
                for future in done:
                    file_path = future_to_file[future]
                    file_name = file_path.name
                    if progress:
                        progress.current_parsing_file = str(file_path)
                        progress.status_message = f"{completed + 1}/{total_files}: {file_name}"

                    try:
                        _, result, ptime, fsize, skipped = future.result()

                        if skipped:
                            if progress: progress.skipped_files.append(str(file_path))
                            yield (None, f"skipped:{file_path}")
                        elif isinstance(result, ParsedFile):
                            ecount = len(result.entities); rcount = len(result.relationships)
                            total_entities += ecount; total_relationships += rcount
                            if progress:
                                progress.current_file_entities = ecount; progress.current_file_duration = ptime
                                progress.current_file_size = fsize; progress.files_parsed += 1
                                progress.entities_extracted += ecount; progress.relationships_extracted += rcount
                            yield (result, None)
                        elif isinstance(result, str):
                            if progress: progress.parse_errors += 1
                            yield (None, result)
                    except SkipFileException:
                        if progress: progress.skipped_files.append(str(file_path))
                        if not future.done(): future.cancel()
                        yield (None, f"skipped:{file_path}")
                    except Exception as exc:
                        logger.error("Worker error for %s: %s", file_name, exc)
                        if progress: progress.parse_errors += 1
                        yield (None, f"error:{file_path}:{exc}")

                    completed += 1
                    if completed % LOG_PROGRESS_INTERVAL == 0:
                        elapsed = time.perf_counter() - parse_start
                        logger.info("📊 Parse: %d/%d (%.0f%%) %.0f f/s | %d entities | %d skipped",
                                   completed, total_files, completed/total_files*100,
                                   completed/elapsed if elapsed > 0 else 0, total_entities, skipped_count)

    elapsed = time.perf_counter() - parse_start
    logger.info("✅ Parse: %d files in %.1fs (%.0f f/s) | %d entities, %d rels, %d skipped",
                completed, elapsed, completed/elapsed if elapsed > 0 else 0,
                total_entities, total_relationships, skipped_count)

# ============================================================================
# FAST GRAPH WRITE - WITH TIMED FLUSH
# ============================================================================

async def _write_graph_streaming_fast(
    builder: GraphBuilder, parsed_stream: AsyncGenerator,
    progress: IndexProgress | None = None,
) -> dict:
    batch = []
    total_files = 0; total_entities = 0; total_relationships = 0; batches_done = 0
    last_flush = time.perf_counter()

    logger.info("🔗 Graph write (batch: %d, flush: %ds)", GRAPH_WRITE_BATCH, FLUSH_TIMEOUT)
    graph_start = time.perf_counter()

    async for parsed_file, warning in parsed_stream:
        if warning and progress:
            if not warning.startswith(("skipped:", "timeout:")):
                progress.warnings.append(warning)
        if parsed_file:
            batch.append(parsed_file)
            
            if len(batch) >= GRAPH_WRITE_BATCH or (batch and time.perf_counter() - last_flush > FLUSH_TIMEOUT):
                stats = await builder.build_from_files(batch)
                total_files += stats.get("files", 0)
                total_entities += stats.get("entities", 0)
                total_relationships += stats.get("relationships", 0)
                batches_done += 1
                if progress:
                    progress.neo4j_files_written = total_files
                    progress.neo4j_entities_written = total_entities
                    progress.neo4j_relationships_written = total_relationships
                    progress.batches_completed = batches_done
                logger.info("📝 Batch %d: %d files, %d entities, %d rels", batches_done, len(batch),
                           stats.get("entities", 0), stats.get("relationships", 0))
                batch.clear()
                last_flush = time.perf_counter()
                await asyncio.sleep(0)

    if batch:
        stats = await builder.build_from_files(batch)
        total_files += stats.get("files", 0); total_entities += stats.get("entities", 0)
        total_relationships += stats.get("relationships", 0)
        batch.clear()

    elapsed = time.perf_counter() - graph_start
    logger.info("✅ Graph: %d entities, %d rels in %.1fs (%.0f e/s, %d batches)",
                total_entities, total_relationships, elapsed,
                total_entities/elapsed if elapsed > 0 else 0, batches_done)
    return {"files": total_files, "entities": total_entities, "relationships": total_relationships}

# ============================================================================
# FAST EMBEDDINGS
# ============================================================================

async def _index_entities_streaming_fast(
    indexer: SearchIndexer, parsed_stream: AsyncGenerator,
    progress: IndexProgress | None = None,
) -> int:
    entity_batch = []
    total_indexed = 0
    batches_done = 0
    logger.info("🧬 Embeddings (batch: %d)", EMBEDDING_BATCH)
    embed_start = time.perf_counter()
    
    MAX_CONCURRENT_EMBEDS = min(os.cpu_count() or 4, 4)  # One per CPU core, max 4
    embed_semaphore = asyncio.Semaphore(MAX_CONCURRENT_EMBEDS)
    
    async def embed_batch(batch):
        async with embed_semaphore:
            return await indexer.index_entities_batched(batch)

    async for parsed_file, warning in parsed_stream:
        if warning and progress:
            if not warning.startswith(("skipped:", "timeout:")):
                progress.warnings.append(warning)
        if parsed_file and parsed_file.entities:
            entity_batch.extend(parsed_file.entities)
            if len(entity_batch) >= EMBEDDING_BATCH:
                # Split into sub-batches for parallel processing
                sub_batches = []
                for i in range(0, len(entity_batch), 100):  # 100 entities per sub-batch
                    sub_batches.append(entity_batch[i:i+100])
                
                batch_start = time.perf_counter()
                
                # Process sub-batches in parallel
                results = await asyncio.gather(*[
                    embed_batch(sub_batch) for sub_batch in sub_batches
                ])
                indexed = sum(results)
                total_indexed += indexed
                batches_done += 1
                
                batch_time = time.perf_counter() - batch_start
                logger.info("🧬 Batch %d: %d entities in %.1fs (%.0f e/s)",
                           batches_done, len(entity_batch), batch_time,
                           len(entity_batch)/batch_time if batch_time > 0 else 0)
                
                if progress:
                    progress.embeddings_generated = total_indexed
                    progress.batches_completed = batches_done
                entity_batch.clear()
                await asyncio.sleep(0)

    if entity_batch:
        sub_batches = []
        for i in range(0, len(entity_batch), 100):
            sub_batches.append(entity_batch[i:i+100])
        results = await asyncio.gather(*[embed_batch(b) for b in sub_batches])
        total_indexed += sum(results)
        batches_done +=1

    elapsed = time.perf_counter() - embed_start
    logger.info("✅ Embeddings: %d vectors in %.1fs (%.0f e/s)", total_indexed, elapsed,
                total_indexed/elapsed if elapsed > 0 else 0)
    return total_indexed

# ============================================================================
# INDEX PIPELINE
# ============================================================================

class IndexPipeline:
    def __init__(self):
        self._status_callbacks = []
        self._registry = None

    async def _set_status(self, status: str, data: dict):
        for cb in self._status_callbacks:
            try: await cb(status, data)
            except Exception as e: logger.error("Status callback error: %s", e)

    def _get_registry(self):
        if self._registry is None: self._registry = build_default_registry()
        return self._registry

    async def _phase1_parse_and_graph_streaming(
        self, repo_path: Path, client: Neo4jClient,
        progress: IndexProgress, project: ProjectRef,
    ) -> AsyncGenerator:
        logger.info("=" * 70)
        logger.info("📅 PHASE 1: Structural Analysis")
        logger.info("   Repo: %s | Project: %s", repo_path, project.id)
        logger.info("=" * 70)

        progress.current_stage = "Preparing graph"
        progress.status_message = "Setting up Neo4j schema..."
        progress.stage_start_time = time.perf_counter()
        neo4j_start = time.perf_counter()
        await setup_schema(client, progress=progress)
        logger.info("🔧 Schema ready in %.2fs", time.perf_counter() - neo4j_start)

        registry = self._get_registry()
        parseable_files = await _discover_files_fast(repo_path, registry, progress)
        if not parseable_files:
            logger.warning("⚠️ No parseable files found")
            return

        progress.current_stage = "Parsing"
        progress.status_message = f"Parsing {len(parseable_files)} files..."
        progress.stage_start_time = time.perf_counter()
        parse_start = time.perf_counter()

        parsed_stream = parse_files_streaming(parseable_files, registry, progress=progress)
        files_processed = 0
        async for parsed_file, warning in parsed_stream:
            if parsed_file:
                parsed_file.project_id = project.id
                for e in parsed_file.entities: e.project_id = project.id
                for r in parsed_file.relationships: r.project_id = project.id
                files_processed += 1
                yield parsed_file, warning
            elif warning:
                yield None, warning

        progress.parse_time = time.perf_counter() - parse_start
        progress.neo4j_time = time.perf_counter() - neo4j_start
        progress.structural_ready = True
        logger.info("✅ Phase 1: %d files in %.1fs (%.0f f/s)",
                    files_processed, progress.parse_time,
                    files_processed/progress.parse_time if progress.parse_time > 0 else 0)

    async def _phase2_embed_and_store(
        self, repo_path: Path, neo4j_client: Neo4jClient,
        parsed_stream: AsyncGenerator, project: ProjectRef,
        qdrant_client=None, embedder=None, progress=None,
    ):
        from core.storage.database import async_session_factory
        logger.info("=" * 70)
        logger.info("📅 PHASE 2: Semantic Analysis")
        logger.info("=" * 70)

        owns_qdrant = qdrant_client is None
        if qdrant_client is None:
            settings = get_settings()
            qdrant_client = QdrantClientWrapper(
                host=settings.qdrant_host, port=settings.qdrant_port,
                vector_size=embedding_dimension(settings.embedding_model))

        try:
            if progress:
                progress.current_stage = "Initializing Qdrant"
                progress.status_message = "Connecting to vector database..."
                progress.stage_start_time = time.perf_counter()
            qs = time.perf_counter()
            await qdrant_client.init_collection()
            if progress: progress.qdrant_time += time.perf_counter() - qs
            logger.info("🔌 Qdrant ready in %.2fs", time.perf_counter() - qs)

            if embedder is None:
                settings = get_settings()
                embedder = EmbeddingPipeline(model_name=settings.embedding_model)

            indexer = SearchIndexer(qdrant_client, embedder, async_session_factory,
                                    project_id=project.id, project_name=project.name)

            if progress:
                progress.current_stage = "Embedding"
                progress.status_message = "Generating embeddings..."
                progress.stage_start_time = time.perf_counter()
            es = time.perf_counter()
            total_indexed = await _index_entities_streaming_fast(indexer, parsed_stream, progress)
            if progress:
                progress.qdrant_vectors_stored = total_indexed
                progress.embeddings_generated = total_indexed
                progress.embedding_time = time.perf_counter() - es

            if progress:
                progress.current_stage = "Git intelligence"
                progress.status_message = "Adding git metadata..."
                progress.stage_start_time = time.perf_counter()
            gs = time.perf_counter()
            builder = GraphBuilder(neo4j_client, project_id=project.id)
            await builder.build_git_data(repo_path)
            if progress: progress.git_time = time.perf_counter() - gs

            logger.info("✅ Phase 2: %d embeddings, git in %.1fs",
                       total_indexed, progress.git_time if progress else 0)
        finally:
            if owns_qdrant: await qdrant_client.close()

    async def run(
        self, repo_path: Path, client: Neo4jClient,
        background: bool = True, structural_only: bool = False,
        qdrant_client=None, embedder=None,
        progress: IndexProgress | None = None,
        project_id: str | None = None, project_name: str | None = None,
    ) -> IndexResult:
        if progress is None: progress = IndexProgress()
        total_start = time.perf_counter()
        mode = "structural_only" if structural_only else ("background" if background else "full")
        logger.info("=" * 70)
        logger.info("🚀 INDEXING PIPELINE STARTED")
        logger.info("   Repo: %s | Mode: %s | Workers: %d", repo_path, mode, MAX_PARALLEL_WORKERS)
        logger.info("=" * 70)

        project = await _resolve_index_project(repo_path, project_id, project_name)
        parsed_stream = self._phase1_parse_and_graph_streaming(repo_path, client, progress, project)
        graph_stream, embed_stream = _tee_async_generator(parsed_stream, 2)

        builder = GraphBuilder(client, project_id=project.id)
        graph_stats = await _write_graph_streaming_fast(builder, graph_stream, progress)
        progress.neo4j_files_written = graph_stats["files"]
        progress.neo4j_entities_written = graph_stats["entities"]
        progress.neo4j_relationships_written = graph_stats["relationships"]

        await self._set_status("structural_ready", {
            "files": graph_stats["files"], "duration": progress.parse_time
        })

        if structural_only:
            progress.total_time = time.perf_counter() - total_start
            return IndexResult(phase="structural_only", files_indexed=graph_stats["files"],
                             semantic_indexing="skipped", progress=progress)

        if background:
            asyncio.create_task(self._phase2_embed_and_store(
                repo_path, client, embed_stream, project, qdrant_client, embedder, progress))
            return IndexResult(phase="structural_complete", files_indexed=graph_stats["files"],
                             semantic_indexing="background", progress=progress)
        else:
            await self._phase2_embed_and_store(
                repo_path, client, embed_stream, project, qdrant_client, embedder, progress)
            progress.total_time = time.perf_counter() - total_start
            logger.info("🏁 Full index complete: %.1fs", progress.total_time)
            return IndexResult(phase="complete", files_indexed=graph_stats["files"],
                             semantic_indexing="complete", progress=progress)

# ============================================================================
# UTILITIES
# ============================================================================

def _tee_async_generator(gen, n=2):
    queues = [asyncio.Queue(maxsize=2000) for _ in range(n)]
    async def feed():
        count = 0
        async for item in gen:
            for q in queues: await q.put(item)
            count += 1
        for q in queues: await q.put(None)
        logger.debug("Tee: %d items → %d queues", count, n)
    async def consumer(queue):
        while True:
            item = await queue.get()
            if item is None: break
            yield item
    asyncio.create_task(feed())
    return [consumer(q) for q in queues]

async def _resolve_index_project(repo_path: Path, project_id: str | None = None, project_name: str | None = None) -> ProjectRef:
    from core.storage.database import async_session_factory, ensure_storage_schema
    if project_id and project_name:
        # If we have both, create a ProjectRef directly
        return ProjectRef(
            id=project_id,
            name=project_name,
            root=str(repo_path)
        )
    ref = project_ref_for_root(repo_path)
    try:
        await ensure_storage_schema()
        async with async_session_factory() as session:
            project = await ensure_project(session, repo_path)
            logger.info("📋 Project: %s (%s)", project.name, project.id[:8])
            return project
    except Exception as exc:
        logger.warning("⚠️ Using deterministic id: %s", exc)
        return ref

# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================

async def index_repository_with_resources(
    repo_path: Path, client: Neo4jClient,
    qdrant_client=None, embedder=None, progress=None,
    rich_progress=None, rich_task=None,
) -> IndexSummary:
    pipeline = IndexPipeline()
    if progress is None: progress = IndexProgress()
    result = await pipeline.run(repo_path, client, background=False,
                                    qdrant_client=qdrant_client, embedder=embedder,
                                    progress=progress, project_id=project_id, project_name=project_name)
    
    # Detect languages from file extensions
    languages = set()
    for root, _, files in os.walk(repo_path):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                lang_map = {
                    '.py': 'Python',
                    '.ts': 'TypeScript',
                    '.tsx': 'TypeScript',
                    '.js': 'JavaScript',
                    '.jsx': 'JavaScript',
                    '.java': 'Java',
                    '.go': 'Go',
                    '.rs': 'Rust',
                    '.dart': 'Dart',
                }
                if ext in lang_map:
                    languages.add(lang_map[ext])
    
    return IndexSummary(
        repo_path=str(repo_path), 
        indexed_files=result.files_indexed,
        total_entities=result.progress.entities_extracted,
        progress=result.progress,
        languages_detected=list(languages)
    )

async def index_repository(repo_path: Path, client: Neo4jClient) -> IndexSummary:
    return await index_repository_with_resources(repo_path, client)