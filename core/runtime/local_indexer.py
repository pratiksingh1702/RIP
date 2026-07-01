"""Provider-aware local indexing path."""

from __future__ import annotations

import time
from pathlib import Path

from core.indexer.pipeline import (
    IndexProgress,
    IndexResult,
    _discover_files_fast,
    parse_files_streaming,
)
from core.parser.base import ParsedFile
from core.parser.registry import build_default_registry
from core.projects import project_ref_for_root
from core.runtime.environment import RuntimeEnvironment


async def index_local(
    repo_path: Path,
    env: RuntimeEnvironment,
    progress: IndexProgress | None = None,
) -> IndexResult:
    progress = progress or IndexProgress()
    total_start = time.perf_counter()
    repo_path = Path(str(repo_path))
    ref = project_ref_for_root(repo_path)

    registry = build_default_registry()
    files = await _discover_files_fast(repo_path, registry, progress)
    parsed_files: list[ParsedFile] = []
    languages: set[str] = set()

    progress.current_stage = "Parsing"
    progress.status_message = f"Parsing {len(files)} files for local runtime..."
    progress.stage_start_time = time.perf_counter()
    parse_start = time.perf_counter()
    async for parsed, warning in parse_files_streaming(files, registry, progress=progress):
        if warning and not warning.startswith(("skipped:", "timeout:")):
            progress.warnings.append(warning)
        if parsed is None:
            continue
        parsed.project_id = ref.id
        for entity in parsed.entities:
            entity.project_id = ref.id
        for rel in parsed.relationships:
            rel.project_id = ref.id
        parsed_files.append(parsed)
        languages.add(parsed.language)
    progress.parse_time = time.perf_counter() - parse_start

    progress.current_stage = "Writing local graph"
    progress.status_message = "Persisting graph under .repo-intel/local..."
    graph_start = time.perf_counter()
    graph_stats = await env.graph.batch_upsert_files(parsed_files, ref.id)
    progress.neo4j_time = time.perf_counter() - graph_start
    progress.neo4j_files_written = graph_stats.get("files", 0)
    progress.neo4j_entities_written = graph_stats.get("entities", 0)
    progress.neo4j_relationships_written = graph_stats.get("relationships", 0)

    progress.current_stage = "Writing local vectors"
    progress.status_message = "Persisting local search payloads..."
    vector_start = time.perf_counter()
    entities = [entity for parsed in parsed_files for entity in parsed.entities]
    stored = await env.vector.upsert_entities(entities, ref.id, ref.name)
    progress.embedding_time = time.perf_counter() - vector_start
    progress.embeddings_generated = stored
    progress.qdrant_vectors_stored = stored

    for parsed in parsed_files:
        await env.metadata.save_file_hash(ref.id, parsed.file_path, parsed.sha256_hash)
    await env.metadata.save_project(
        repo_path,
        project_id=ref.id,
        project_name=ref.name,
        files_count=len(parsed_files),
        entities_count=len(entities),
        languages=sorted(languages),
    )

    progress.current_stage = "Complete"
    progress.status_message = "Local index complete."
    progress.total_time = time.perf_counter() - total_start
    return IndexResult(
        phase="local_complete",
        files_indexed=len(parsed_files),
        semantic_indexing="local",
        progress=progress,
    )
