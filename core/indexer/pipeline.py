"""Full indexing pipeline - optimized for speed, accuracy, and detailed logging."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import AsyncGenerator, Optional
import gc

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from core.graph.builder import GraphBuilder
from core.graph.client import Neo4jClient
from core.graph.schema import setup_schema
from core.parser.base import ParsedFile
from core.parser.registry import LanguageParserRegistry, build_default_registry
from core.projects import ProjectRef, ensure_project, project_ref_for_root
from core.search.client import QdrantClientWrapper
from core.search.embedder import EmbeddingPipeline, embedding_dimension
from core.search.indexer import SearchIndexer
from server.config import get_settings

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION - Tuned for maximum speed
# ============================================================================
MEMORY_THRESHOLD = 0.85
MAX_PARALLEL_WORKERS = min(os.cpu_count() or 4, 16)
MIN_FILE_SIZE_FOR_PARALLEL = 512  # Smaller threshold = more parallel processing
GRAPH_WRITE_BATCH = 1000  # Large batches for Neo4j
EMBEDDING_BATCH = 1000  # Large batches for embeddings
PARSE_TIMEOUT = 15  # 15s timeout per file
LOG_PROGRESS_INTERVAL = 100  # Log every 100 files

# Directories to skip during file discovery
SKIP_DIRS = frozenset({
    '.git', 'node_modules', '__pycache__', '.venv', 'venv',
    '.repo-intel', '.idea', '.vscode', 'dist', 'build',
    '.next', '.nuxt', 'target', 'bin', 'obj', '.tox',
    'eggs', '.eggs', '*.egg-info', '.mypy_cache', '.pytest_cache',
    '.ruff_cache', 'htmlcov', '.coverage', 'site-packages',
    'bower_components', 'jspm_packages', '.yarn', '.turbo',
    '.cache', 'coverage', 'out', 'output',
})

# Supported file extensions
SUPPORTED_EXTENSIONS = frozenset({
    '.py', '.ts', '.tsx', '.js', '.jsx', '.java', '.go', '.rs', '.dart'
})

# ============================================================================
# SKIP FUNCTIONALITY
# ============================================================================

class SkipFileException(Exception):
    """Raised when user wants to skip current file."""
    pass

_skip_requested = False

def request_skip():
    """Request to skip the current file."""
    global _skip_requested
    _skip_requested = True

def check_skip():
    """Check if skip was requested and raise if so."""
    global _skip_requested
    if _skip_requested:
        _skip_requested = False
        raise SkipFileException("File skipped by user")

def reset_skip():
    """Reset skip flags."""
    global _skip_requested
    _skip_requested = False

# ============================================================================
# PARSER CACHE
# ============================================================================

@lru_cache(maxsize=16)
def _get_worker_parser_cached(suffix: str):
    """Cached parser factory."""
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
    return None

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class IndexProgress:
    """Detailed progress tracking."""
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
    total_batches: int = 0
    stage_start_time: float = 0.0
    discovery_time: float = 0.0

    def timing_summary(self) -> dict[str, float]:
        total = self.total_time or (
            self.parse_time + self.neo4j_time + self.embedding_time +
            self.qdrant_time + self.git_time + self.discovery_time
        )
        return {
            "Discovery": self.discovery_time,
            "Parsing": self.parse_time,
            "Neo4j": self.neo4j_time,
            "Embeddings": self.embedding_time,
            "Qdrant": self.qdrant_time,
            "Git": self.git_time,
            "Total": total,
        }

    def get_stage_elapsed(self) -> float:
        if self.stage_start_time:
            return time.perf_counter() - self.stage_start_time
        return 0.0

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

# ============================================================================
# MEMORY MANAGER
# ============================================================================

class MemoryManager:
    @staticmethod
    def get_memory_usage_mb() -> float:
        if not HAS_PSUTIL:
            return 0.0
        try:
            return psutil.Process().memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0

    @staticmethod
    def should_gc() -> bool:
        if not HAS_PSUTIL:
            return False
        try:
            return psutil.virtual_memory().percent / 100 > MEMORY_THRESHOLD
        except Exception:
            return False

# ============================================================================
# WORKER FUNCTIONS
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
        return (file_path_str, result, elapsed, file_size, False)
    except TypeError as exc:
        err = str(exc)
        logger.error("❌ %s: %s", file_path.name, err[:150])
        return (file_path_str, f"error:{file_path}:{exc}", time.perf_counter() - start, 0, False)
    except Exception as exc:
        logger.error("❌ %s: %s", file_path.name, str(exc)[:150])
        return (file_path_str, f"error:{file_path}:{exc}", time.perf_counter() - start, 0, False)
# ============================================================================
# FAST FILE DISCOVERY
# ============================================================================

def _scan_directory_fast(root: Path) -> tuple[list[Path], int, int]:
    """Ultra-fast directory scanning using os.scandir."""
    parseable = []
    scanned = 0
    skipped = 0
    dirs_to_scan = [str(root)]

    while dirs_to_scan:
        current_dir = dirs_to_scan.pop()
        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    scanned += 1
                    if entry.is_dir(follow_symlinks=False):
                        name = entry.name
                        if name.startswith('.') or name in SKIP_DIRS:
                            skipped += 1
                            continue
                        dirs_to_scan.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in SUPPORTED_EXTENSIONS:
                            parseable.append(Path(entry.path))
                        else:
                            skipped += 1
        except PermissionError:
            logger.debug("Permission denied: %s", current_dir)
        except OSError as e:
            logger.debug("OS error in %s: %s", current_dir, e)

    return parseable, scanned, skipped

async def _discover_files_fast(
    repo_path: Path,
    registry: LanguageParserRegistry,
    progress: IndexProgress
) -> list[Path]:
    """Async wrapper for fast file discovery."""
    progress.current_stage = "Discovering files"
    progress.status_message = "Scanning repository for source files..."
    progress.stage_start_time = time.perf_counter()

    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=4) as pool:
        parseable, scanned, skipped = await loop.run_in_executor(
            pool, _scan_directory_fast, repo_path
        )

    progress.files_scanned = scanned
    progress.files_skipped = skipped
    progress.discovery_time = time.perf_counter() - progress.stage_start_time

    logger.info(
        "📁 Discovery: %d scanned → %d parseable, %d skipped in %.2fs",
        scanned, len(parseable), skipped, progress.discovery_time
    )
    return parseable

# ============================================================================
# STREAMING PARSE
# ============================================================================

async def parse_files_streaming(
    files: list[Path],
    registry: LanguageParserRegistry,
    max_workers: int | None = None,
    progress: IndexProgress | None = None,
) -> AsyncGenerator[tuple[ParsedFile | None, str | None], None]:
    """Stream parse results with skip support and detailed logging."""
    if not files:
        logger.info("📭 No files to parse")
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

    # Split files by size for optimal processing
    small_files = []
    large_files = []
    for fp in files:
        try:
            if fp.stat().st_size < MIN_FILE_SIZE_FOR_PARALLEL:
                small_files.append(fp)
            else:
                large_files.append(fp)
        except OSError:
            small_files.append(fp)

    logger.info("📄 %d small files (sequential), 📦 %d large files (parallel)",
                len(small_files), len(large_files))

    # ========================================================================
    # Process small files sequentially (no process overhead)
    # ========================================================================
    for file_path in small_files:
        if file_path.name.endswith('.g.dart') or file_path.name.endswith('.freezed.dart'):
            if progress:
                progress.skipped_files.append(str(file_path))
                progress.files_skipped += 1
            logger.info("⏭ Skipping generated file: %s", file_path.name)
            completed += 1
            continue

        file_name = file_path.name
        if progress:
            progress.current_parsing_file = str(file_path)
            progress.status_message = f"{completed + 1}/{total_files}: {file_name}"
            progress.current_file_entities = 0
            progress.current_file_duration = 0.0

        file_start = time.perf_counter()
        try:
            check_skip()
            _, result, ptime, fsize, skipped = _parse_file_worker_optimized(
                (str(file_path), file_path.suffix.lower())
            )

            if skipped:
                skipped_count += 1
                if progress:
                    progress.skipped_files.append(str(file_path))
                logger.warning("⏭️  Skipped unsupported: %s", file_name)
                yield (None, f"skipped:{file_path}")
            elif isinstance(result, ParsedFile):
                ecount = len(result.entities)
                rcount = len(result.relationships)
                total_entities += ecount
                total_relationships += rcount
                if progress:
                    progress.current_file_entities = ecount
                    progress.current_file_duration = ptime
                    progress.current_file_size = fsize
                    progress.files_parsed += 1
                    progress.entities_extracted += ecount
                    progress.relationships_extracted += rcount
                logger.debug("✅ %s: %d entities, %d rels, %.0fms",
                           file_name, ecount, rcount, ptime * 1000)
                yield (result, None)
            elif isinstance(result, str):
                if progress:
                    progress.current_file_duration = ptime
                    progress.parse_errors += 1
                err_msg = result.split(":", 2)[-1][:100] if ":" in result else result[:100]
                logger.warning("❌ %s: %s", file_name, err_msg)
                yield (None, result)
        except SkipFileException:
            skipped_count += 1
            if progress:
                progress.skipped_files.append(str(file_path))
                progress.current_file_duration = time.perf_counter() - file_start
            logger.warning("⏭️  User skipped: %s (took %.1fs)", file_name, time.perf_counter() - file_start)
            yield (None, f"skipped:{file_path}")

        completed += 1
        if completed % LOG_PROGRESS_INTERVAL == 0:
            elapsed = time.perf_counter() - parse_start
            logger.info("📊 Parse: %d/%d (%.0f%%) %.0f f/s | %d entities | %d skipped",
                       completed, total_files, completed/total_files*100,
                       completed/elapsed if elapsed > 0 else 0,
                       total_entities, skipped_count)

    # ========================================================================
    # Process large files in parallel using asyncio.wait (no RuntimeWarning)
    # ========================================================================
        # Process large files in parallel
        # Process large files in parallel
    if large_files:
        loop = asyncio.get_running_loop()
        worker_args = [(str(fp), fp.suffix.lower()) for fp in large_files]

        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            future_to_file = {}
            for arg, fp in zip(worker_args, large_files):
                future = loop.run_in_executor(executor, _parse_file_worker_optimized, arg)
                future_to_file[future] = fp

            pending = set(future_to_file.keys())
            stuck_count = 0
            
            while pending:
                try:
                    done, pending = await asyncio.wait(
                        pending, 
                        timeout=PARSE_TIMEOUT,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                except Exception as e:
                    logger.error("asyncio.wait error: %s", e)
                    break
                
                if not done:
                    stuck_count += 1
                    logger.warning("⏰ No files completed in %ds (stuck #%d)", PARSE_TIMEOUT, stuck_count)
                    
                    # If stuck 3+ times, cancel all remaining
                    if stuck_count >= 3:
                        logger.error("🚫 Too many timeouts - cancelling %d remaining files", len(pending))
                        for f in pending:
                            f.cancel()
                        break
                    
                    # Cancel the future that's been pending longest
                    if pending:
                        stuck = list(pending)[0]
                        stuck_path = future_to_file.get(stuck, "unknown")
                        stuck.cancel()
                        pending.discard(stuck)
                        logger.warning("⏭ Cancelled stuck file: %s", stuck_path)
                        if progress:
                            progress.skipped_files.append(str(stuck_path))
                        yield (None, f"timeout:{stuck_path}")
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
                        file_path_str, result, ptime, fsize, skipped = future.result()

                        if skipped:
                            if progress:
                                progress.skipped_files.append(str(file_path))
                            yield (None, f"skipped:{file_path}")
                        elif isinstance(result, ParsedFile):
                            ecount = len(result.entities)
                            rcount = len(result.relationships)
                            total_entities += ecount
                            total_relationships += rcount
                            if progress:
                                progress.current_file_entities = ecount
                                progress.current_file_duration = ptime
                                progress.current_file_size = fsize
                                progress.files_parsed += 1
                                progress.entities_extracted += ecount
                                progress.relationships_extracted += rcount
                            yield (result, None)
                        elif isinstance(result, str):
                            if progress:
                                progress.parse_errors += 1
                            yield (None, result)

                    except SkipFileException:
                        if progress:
                            progress.skipped_files.append(str(file_path))
                        if not future.done():
                            future.cancel()
                        yield (None, f"skipped:{file_path}")
                    except Exception as exc:
                        logger.error("Worker error for %s: %s", file_name, exc)
                        if progress:
                            progress.parse_errors += 1
                        yield (None, f"error:{file_path}:{exc}")

                    completed += 1
                    
                    if completed % LOG_PROGRESS_INTERVAL == 0:
                        elapsed = time.perf_counter() - parse_start
                        logger.info(
                            "📊 Parse: %d/%d (%.0f%%) %.0f f/s | %d entities | %d skipped",
                            completed, total_files, completed/total_files*100,
                            completed/elapsed if elapsed > 0 else 0,
                            total_entities, skipped_count
                        )
        loop = asyncio.get_running_loop()
        worker_args = [(str(fp), fp.suffix.lower()) for fp in large_files]

        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            future_to_file = {}
            for arg, fp in zip(worker_args, large_files):
                future = loop.run_in_executor(executor, _parse_file_worker_optimized, arg)
                future_to_file[future] = fp

            pending = set(future_to_file.keys())
            stuck_count = 0
            
            while pending:
                try:
                    done, pending = await asyncio.wait(
                        pending, 
                        timeout=PARSE_TIMEOUT,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                except Exception as e:
                    logger.error("asyncio.wait error: %s", e)
                    break
                
                if not done:
                    stuck_count += 1
                    logger.warning("⏰ No files completed in %ds (stuck #%d)", PARSE_TIMEOUT, stuck_count)
                    
                    # If stuck 3+ times, cancel all remaining
                    if stuck_count >= 3:
                        logger.error("🚫 Too many timeouts - cancelling %d remaining files", len(pending))
                        for f in pending:
                            f.cancel()
                        break
                    
                    # Cancel the future that's been pending longest
                    if pending:
                        stuck = list(pending)[0]
                        stuck_path = future_to_file.get(stuck, "unknown")
                        stuck.cancel()
                        pending.discard(stuck)
                        logger.warning("⏭ Cancelled stuck file: %s", stuck_path)
                        if progress:
                            progress.skipped_files.append(str(stuck_path))
                        yield (None, f"timeout:{stuck_path}")
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
                        file_path_str, result, ptime, fsize, skipped = future.result()

                        if skipped:
                            if progress:
                                progress.skipped_files.append(str(file_path))
                            yield (None, f"skipped:{file_path}")
                        elif isinstance(result, ParsedFile):
                            ecount = len(result.entities)
                            rcount = len(result.relationships)
                            total_entities += ecount
                            total_relationships += rcount
                            if progress:
                                progress.current_file_entities = ecount
                                progress.current_file_duration = ptime
                                progress.current_file_size = fsize
                                progress.files_parsed += 1
                                progress.entities_extracted += ecount
                                progress.relationships_extracted += rcount
                            yield (result, None)
                        elif isinstance(result, str):
                            if progress:
                                progress.parse_errors += 1
                            yield (None, result)

                    except SkipFileException:
                        if progress:
                            progress.skipped_files.append(str(file_path))
                        if not future.done():
                            future.cancel()
                        yield (None, f"skipped:{file_path}")
                    except Exception as exc:
                        logger.error("Worker error for %s: %s", file_name, exc)
                        if progress:
                            progress.parse_errors += 1
                        yield (None, f"error:{file_path}:{exc}")

                    completed += 1
                    
                    if completed % LOG_PROGRESS_INTERVAL == 0:
                        elapsed = time.perf_counter() - parse_start
                        logger.info(
                            "📊 Parse: %d/%d (%.0f%%) %.0f f/s | %d entities | %d skipped",
                            completed, total_files, completed/total_files*100,
                            completed/elapsed if elapsed > 0 else 0,
                            total_entities, skipped_count
                        )
    # ========================================================================
    # Final summary
    # ========================================================================
    elapsed = time.perf_counter() - parse_start
    success_rate = (total_files - skipped_count) / total_files * 100 if total_files > 0 else 0
    
    logger.info(
        "✅ Parse complete: %d/%d files (%.1f%% success) in %.1fs (%.0f f/s) | "
        "%d entities, %d rels, %d skipped, %d errors",
        completed - skipped_count, total_files, success_rate,
        elapsed, completed/elapsed if elapsed > 0 else 0,
        total_entities, total_relationships, skipped_count,
        progress.parse_errors if progress else 0
    )
    
    # Log per-file-type stats
    if progress and progress.files_parsed > 0:
        avg_entities = total_entities / max(progress.files_parsed, 1)
        avg_rels = total_relationships / max(progress.files_parsed, 1)
        logger.info(
            "📊 Per-file avg: %.1f entities, %.1f relationships",
            avg_entities, avg_rels
        )
# ============================================================================
# FAST GRAPH WRITE
# ============================================================================

async def _write_graph_streaming_fast(
    builder: GraphBuilder,
    parsed_stream: AsyncGenerator,
    progress: IndexProgress | None = None,
) -> dict:
    """Ultra-fast Neo4j write with large batches."""
    batch = []
    total_files = 0
    total_entities = 0
    total_relationships = 0
    batches_done = 0

    logger.info("🔗 Starting graph write (batch size: %d)", GRAPH_WRITE_BATCH)
    graph_start = time.perf_counter()

    async for parsed_file, warning in parsed_stream:
        if warning and progress:
            if not warning.startswith("skipped:") and not warning.startswith("timeout:"):
                progress.warnings.append(warning)

        if parsed_file:
            batch.append(parsed_file)
            if len(batch) >= GRAPH_WRITE_BATCH:
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
                    if batch:
                        progress.current_graph_file = str(batch[-1].file_path)

                logger.debug("📝 Batch %d: %d files, %d entities, %d rels",
                           batches_done, len(batch),
                           stats.get("entities", 0), stats.get("relationships", 0))
                batch.clear()
                await asyncio.sleep(0)  # Yield to event loop

    if batch:
        stats = await builder.build_from_files(batch)
        total_files += stats.get("files", 0)
        total_entities += stats.get("entities", 0)
        total_relationships += stats.get("relationships", 0)
        batch.clear()

    elapsed = time.perf_counter() - graph_start
    logger.info("✅ Graph: %d entities, %d rels in %.1fs (%.0f e/s, %d batches)",
                total_entities, total_relationships, elapsed,
                total_entities/elapsed if elapsed > 0 else 0, batches_done)

    return {
        "files": total_files,
        "entities": total_entities,
        "relationships": total_relationships
    }

# ============================================================================
# FAST EMBEDDINGS
# ============================================================================

async def _index_entities_streaming_fast(
    indexer: SearchIndexer,
    parsed_stream: AsyncGenerator,
    progress: IndexProgress | None = None,
) -> int:
    """Fast entity indexing with large batches."""
    entity_batch = []
    total_indexed = 0
    batches_done = 0

    logger.info("🧬 Starting embeddings (batch size: %d)", EMBEDDING_BATCH)
    embed_start = time.perf_counter()

    async for parsed_file, warning in parsed_stream:
        if warning and progress:
            if not warning.startswith("skipped:") and not warning.startswith("timeout:"):
                progress.warnings.append(warning)

        if parsed_file and parsed_file.entities:
            entity_batch.extend(parsed_file.entities)
            if len(entity_batch) >= EMBEDDING_BATCH:
                indexed = await indexer.index_entities_batched(entity_batch)
                total_indexed += indexed
                batches_done += 1

                if progress:
                    progress.embeddings_generated = total_indexed
                    progress.batches_completed = batches_done

                logger.debug("🧬 Batch %d: %d entities", batches_done, indexed)
                entity_batch.clear()
                await asyncio.sleep(0)

    if entity_batch:
        indexed = await indexer.index_entities_batched(entity_batch)
        total_indexed += indexed
        entity_batch.clear()

    elapsed = time.perf_counter() - embed_start
    logger.info("✅ Embeddings: %d vectors in %.1fs (%.0f e/s, %d batches)",
                total_indexed, elapsed,
                total_indexed/elapsed if elapsed > 0 else 0, batches_done)

    return total_indexed

# ============================================================================
# INDEX PIPELINE
# ============================================================================

class IndexPipeline:
    """Optimized indexing pipeline."""

    def __init__(self):
        self._status_callbacks = []
        self._registry = None

    async def _set_status(self, status: str, data: dict):
        for cb in self._status_callbacks:
            try:
                await cb(status, data)
            except Exception as e:
                logger.error("Status callback error: %s", e)

    def _get_registry(self) -> LanguageParserRegistry:
        if self._registry is None:
            self._registry = build_default_registry()
        return self._registry

    async def _phase1_parse_and_graph_streaming(
        self, repo_path: Path, client: Neo4jClient,
        progress: IndexProgress, project: ProjectRef,
    ) -> AsyncGenerator:
        logger.info("=" * 70)
        logger.info("📅 PHASE 1: Structural Analysis")
        logger.info("   Repository: %s", repo_path)
        logger.info("   Project: %s", project.id)
        logger.info("=" * 70)

        # Setup schema
        progress.current_stage = "Preparing graph"
        progress.status_message = "Setting up Neo4j schema..."
        progress.stage_start_time = time.perf_counter()
        neo4j_start = time.perf_counter()

        await setup_schema(client, progress=progress)
        schema_time = time.perf_counter() - neo4j_start
        logger.info("🔧 Schema ready in %.2fs", schema_time)

        # Discover files
        registry = self._get_registry()
        parseable_files = await _discover_files_fast(repo_path, registry, progress)

        if not parseable_files:
            logger.warning("⚠️  No parseable files found")
            return

        # Parse
        progress.current_stage = "Parsing"
        progress.status_message = f"Parsing {len(parseable_files)} files..."
        progress.stage_start_time = time.perf_counter()
        parse_start = time.perf_counter()

        parsed_stream = parse_files_streaming(parseable_files, registry, progress=progress)

        files_processed = 0
        async for parsed_file, warning in parsed_stream:
            if parsed_file:
                parsed_file.project_id = project.id
                for e in parsed_file.entities:
                    e.project_id = project.id
                for r in parsed_file.relationships:
                    r.project_id = project.id
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
        qdrant_client: QdrantClientWrapper | None = None,
        embedder: EmbeddingPipeline | None = None,
        progress: IndexProgress | None = None,
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

            qdrant_start = time.perf_counter()
            await qdrant_client.init_collection()
            if progress:
                progress.qdrant_time += time.perf_counter() - qdrant_start
            logger.info("🔌 Qdrant ready in %.2fs", time.perf_counter() - qdrant_start)

            if embedder is None:
                settings = get_settings()
                embedder = EmbeddingPipeline(model_name=settings.embedding_model)

            indexer = SearchIndexer(
                qdrant_client, embedder, async_session_factory,
                project_id=project.id, project_name=project.name)

            if progress:
                progress.current_stage = "Embedding"
                progress.status_message = "Generating embeddings..."
                progress.stage_start_time = time.perf_counter()

            embed_start = time.perf_counter()
            total_indexed = await _index_entities_streaming_fast(indexer, parsed_stream, progress)

            if progress:
                progress.qdrant_vectors_stored = total_indexed
                progress.embeddings_generated = total_indexed
                progress.embedding_time = time.perf_counter() - embed_start

            # Git intelligence
            if progress:
                progress.current_stage = "Git intelligence"
                progress.status_message = "Adding git metadata..."
                progress.stage_start_time = time.perf_counter()

            git_start = time.perf_counter()
            builder = GraphBuilder(neo4j_client, project_id=project.id)
            await builder.build_git_data(repo_path)
            if progress:
                progress.git_time = time.perf_counter() - git_start

            logger.info("✅ Phase 2: %d embeddings, git in %.1fs",
                       total_indexed, progress.git_time if progress else 0)

        finally:
            if owns_qdrant:
                await qdrant_client.close()

    async def run(
        self, repo_path: Path, client: Neo4jClient,
        background: bool = True, structural_only: bool = False,
        qdrant_client: QdrantClientWrapper | None = None,
        embedder: EmbeddingPipeline | None = None,
        progress: IndexProgress | None = None,
    ) -> IndexResult:
        if progress is None:
            progress = IndexProgress()

        total_start = time.perf_counter()
        mode = "structural_only" if structural_only else ("background" if background else "full")

        logger.info("=" * 70)
        logger.info("🚀 INDEXING PIPELINE STARTED")
        logger.info("   Repo: %s | Mode: %s | Workers: %d", repo_path, mode, MAX_PARALLEL_WORKERS)
        logger.info("=" * 70)

        project = await _resolve_index_project(repo_path)

        # Phase 1
        parsed_stream = self._phase1_parse_and_graph_streaming(
            repo_path, client, progress, project)

        # Split stream
        graph_stream, embed_stream = _tee_async_generator(parsed_stream, 2)

        # Build graph
        builder = GraphBuilder(client, project_id=project.id)
        graph_stats = await _write_graph_streaming_fast(builder, graph_stream, progress)

        progress.neo4j_files_written = graph_stats["files"]
        progress.neo4j_entities_written = graph_stats["entities"]
        progress.neo4j_relationships_written = graph_stats["relationships"]

        await self._set_status("structural_ready", {
            "files": graph_stats["files"],
            "duration": progress.parse_time
        })

        if structural_only:
            progress.total_time = time.perf_counter() - total_start
            logger.info("🏁 Done (structural only): %.1fs", progress.total_time)
            return IndexResult(phase="structural_only", files_indexed=graph_stats["files"],
                             semantic_indexing="skipped", progress=progress)

        if background:
            asyncio.create_task(
                self._phase2_embed_and_store(repo_path, client, embed_stream, project,
                                            qdrant_client, embedder, progress))
            logger.info("🏁 Structural done (semantic in background)")
            return IndexResult(phase="structural_complete", files_indexed=graph_stats["files"],
                             semantic_indexing="background", progress=progress)
        else:
            await self._phase2_embed_and_store(repo_path, client, embed_stream, project,
                                              qdrant_client, embedder, progress)
            progress.total_time = time.perf_counter() - total_start
            logger.info("🏁 Full index complete: %.1fs", progress.total_time)
            logger.info("   Timing: %s", progress.timing_summary())
            return IndexResult(phase="complete", files_indexed=graph_stats["files"],
                             semantic_indexing="complete", progress=progress)

# ============================================================================
# UTILITIES
# ============================================================================

def _tee_async_generator(gen, n=2):
    queues = [asyncio.Queue(maxsize=500) for _ in range(n)]

    async def feed():
        count = 0
        async for item in gen:
            for q in queues:
                await q.put(item)
            count += 1
        for q in queues:
            await q.put(None)
        logger.debug("Tee fed %d items to %d queues", count, n)

    async def consumer(queue):
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    asyncio.create_task(feed())
    return [consumer(q) for q in queues]


async def _resolve_index_project(repo_path: Path) -> ProjectRef:
    from core.storage.database import async_session_factory, ensure_storage_schema

    ref = project_ref_for_root(repo_path)
    try:
        await ensure_storage_schema()
        async with async_session_factory() as session:
            project = await ensure_project(session, repo_path)
            logger.info("📋 Project: %s (%s)", project.name, project.id[:8])
            return project
    except Exception as exc:
        logger.warning("⚠️  Using deterministic id: %s", exc)
        return ref
    
# At the very end of pipeline.py, add:

async def index_repository_with_resources(
    repo_path: Path,
    client: Neo4jClient,
    qdrant_client: QdrantClientWrapper | None = None,
    embedder: EmbeddingPipeline | None = None,
    progress: IndexProgress | None = None,
    rich_progress=None,
    rich_task=None,
) -> IndexSummary:
    """Backward-compatible wrapper for API router and CLI."""
    pipeline = IndexPipeline()
    if progress is None:
        progress = IndexProgress()
    result = await pipeline.run(
        repo_path, client,
        background=False,
        qdrant_client=qdrant_client,
        embedder=embedder,
        progress=progress,
    )
    return IndexSummary(
        repo_path=str(repo_path),
        indexed_files=result.files_indexed,
        total_entities=result.progress.entities_extracted,
        progress=result.progress,
    )


async def index_repository(repo_path: Path, client: Neo4jClient) -> IndexSummary:
    """Legacy wrapper."""
    return await index_repository_with_resources(repo_path, client)