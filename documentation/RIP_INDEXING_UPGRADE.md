# RIP — Blazing Fast Indexing Upgrade
## Agent Instructions: Make Indexing Production-Grade Without Breaking Anything

---

## READ THIS BEFORE TOUCHING ANYTHING

You are upgrading the indexing pipeline of a working system. The existing commands — `repo index`, `repo trace`, `repo impact`, `repo search`, `repo explain`, `repo architecture`, `repo metrics`, `repo onboard` — all work right now. Your job is to make indexing dramatically faster and more visible without breaking any of these.

**The golden rule of this entire task:** At every step, run the verification commands. If any verification fails, fix it before moving forward. Never carry a broken state into the next improvement.

**What you must not change:**
- The output format of any existing CLI command
- The FastAPI response envelope shape
- Neo4j node labels or relationship types
- Qdrant collection schema or vector dimensions
- The MCP server tool names or response format
- Config file field names that already exist

**What you are allowed to change:**
- How fast things happen internally
- What gets displayed while indexing runs
- In what order internal pipeline stages execute
- Whether stages run sequentially or in parallel
- How many items are batched together
- What gets skipped when nothing changed

---

## THE CORE ARCHITECTURAL INSIGHT

Right now the indexing pipeline is a single sequential chain:

```
file1 → parse → write Neo4j → embed → write Qdrant
file2 → parse → write Neo4j → embed → write Qdrant
file3 → parse → write Neo4j → embed → write Qdrant
```

Every file blocks the next. Embedding — the slowest step — blocks everything behind it. A user running `repo trace` has to wait for ALL embeddings to finish before the command works even though trace only needs Neo4j.

The target architecture is a two-phase pipeline where structural intelligence (Neo4j) is available almost immediately and semantic intelligence (Qdrant) fills in progressively:

```
PHASE 1 — Structural (fast, parallel, blocks nothing)
All files → Parser Pool → Graph Builder → Neo4j
↓ DONE → repo trace, repo impact, repo architecture, repo dead-code all work NOW

PHASE 2 — Semantic (background, progressive)
All entities → Embedding Workers → Qdrant
↓ DONE → repo search, repo explain fully operational
```

This single architectural change makes RIP feel 5 to 10 times faster even before any other optimization because users get value in seconds instead of waiting for everything.

---

## IMPROVEMENT 1 — Two-Phase Pipeline Split

### What to change
**File:** `core/indexer/pipeline.py`

Split `IndexPipeline.run()` into two clearly separated phases. Phase 1 must complete and commit to Neo4j before Phase 2 begins. Phase 2 runs in the background and does not block the CLI from returning.

### How to implement it

```python
# core/indexer/pipeline.py

class IndexPipeline:
    
    async def run(self, repo_path: str, background: bool = True) -> IndexResult:
        
        # ── PHASE 1: Structural indexing ──────────────────────
        # Parse all files and build graph. Fast. Parallel.
        # After this completes, all structural commands work.
        
        phase1_start = time.time()
        
        all_parsed_files = await self._phase1_parse_and_graph(repo_path)
        
        phase1_duration = time.time() - phase1_start
        
        # Signal that structural queries are now available
        await self._set_status("structural_ready", {
            "files": len(all_parsed_files),
            "duration_seconds": phase1_duration
        })
        
        # ── PHASE 2: Semantic indexing ────────────────────────
        # Embed all entities and write to Qdrant.
        # Slower. Can run in background while user works.
        
        if background:
            # Return control to the user immediately
            # Phase 2 runs as a background task
            asyncio.create_task(
                self._phase2_embed_and_store(all_parsed_files, repo_path)
            )
            return IndexResult(
                phase="structural_complete",
                files_indexed=len(all_parsed_files),
                semantic_indexing="background"
            )
        else:
            # Wait for full completion (used for --full flag)
            await self._phase2_embed_and_store(all_parsed_files, repo_path)
            return IndexResult(
                phase="complete",
                files_indexed=len(all_parsed_files),
                semantic_indexing="complete"
            )
    
    async def _phase1_parse_and_graph(self, repo_path: str) -> List[ParsedFile]:
        """Parse all files in parallel and write to Neo4j in batches."""
        # See Improvement 2 for parallel parsing
        # See Improvement 3 for batch graph writes
        pass
    
    async def _phase2_embed_and_store(
        self, 
        parsed_files: List[ParsedFile],
        repo_path: str
    ) -> None:
        """Embed entities in large batches and write to Qdrant."""
        # See Improvement 4 for batch embeddings
        # See Improvement 5 for embedding cache
        pass
```

### Update the CLI display to reflect phases

```python
# cli/commands/index.py

# When Phase 1 completes:
console.print(Panel(
    f"[bold green]✓ Structural index ready[/bold green] in {phase1_duration:.1f}s\n"
    f"  [cyan]repo trace[/cyan], [cyan]repo impact[/cyan], [cyan]repo architecture[/cyan] are now available\n"
    f"  Semantic search building in background...",
    border_style="green"
))

# When Phase 2 completes (background):
console.print(
    f"  [dim]✓ Semantic index complete — [cyan]repo search[/cyan] fully operational[/dim]"
)
```

### Add a `--full` flag to wait for both phases

```bash
repo index .              # Returns after Phase 1, Phase 2 in background
repo index . --full       # Waits for both phases to complete
repo index . --structural # Only runs Phase 1, skips embeddings entirely
```

### Verification
```bash
uv run repo index .
# Should return after ~20-30 seconds for a medium repo
# Should show "Structural index ready" message
# Immediately after:
uv run repo trace PythonParser   # Must work
uv run repo impact BaseParser    # Must work
uv run repo architecture         # Must work
# Wait 60 more seconds then:
uv run repo search "parser"      # Must work
```

---

## IMPROVEMENT 2 — Parallel Parsing with Process Pool

### What to change
**File:** `core/indexer/pipeline.py` — the `_phase1_parse_and_graph` method

### The problem
Right now files are parsed one at a time. Tree-sitter is CPU-bound but Python's GIL prevents true parallelism with threads. You need a ProcessPoolExecutor to get real parallelism.

### How to implement it

```python
# core/indexer/pipeline.py

import asyncio
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import os

def _parse_file_worker(args: tuple) -> dict:
    """
    Module-level function (required for pickling with ProcessPoolExecutor).
    Parses a single file and returns serializable result.
    Cannot use async or reference unpicklable objects.
    """
    file_path, content, language = args
    
    try:
        # Import inside worker to avoid pickling issues
        from core.parser.registry import LanguageParserRegistry
        from core.parser.languages.python import PythonParser
        from core.parser.languages.typescript import TypeScriptParser
        from core.parser.languages.java import JavaParser
        from core.parser.languages.go import GoParser
        from core.parser.languages.rust import RustParser
        
        registry = LanguageParserRegistry()
        registry.register(PythonParser())
        registry.register(TypeScriptParser())
        registry.register(JavaParser())
        registry.register(GoParser())
        registry.register(RustParser())
        
        from pathlib import Path
        parser = registry.get_parser(Path(file_path))
        if parser is None:
            return {"status": "skipped", "file_path": file_path}
        
        result = parser.parse_file(Path(file_path), content)
        
        # Return as dict (must be picklable)
        return {
            "status": "success",
            "file_path": file_path,
            "entities": [
                {
                    "entity_type": e.entity_type,
                    "name": e.name,
                    "fqn": e.fqn,
                    "file_path": e.file_path,
                    "line_start": e.line_start,
                    "line_end": e.line_end,
                    "language": e.language,
                    "docstring": e.docstring,
                    "decorators": e.decorators,
                    "is_exported": e.is_exported,
                    "raw_code": e.raw_code,
                }
                for e in result.entities
            ],
            "relationships": [
                {
                    "from_fqn": r.from_fqn,
                    "to_fqn": r.to_fqn,
                    "relationship_type": r.relationship_type,
                    "file_path": r.file_path,
                    "line": r.line,
                }
                for r in result.relationships
            ],
            "imports": result.imports,
            "sha256_hash": result.sha256_hash,
        }
    except Exception as e:
        return {"status": "error", "file_path": file_path, "error": str(e)}


class IndexPipeline:
    
    # Optimal worker count: use CPU count but cap at 8
    # Above 8 the coordination overhead starts eating gains
    MAX_WORKERS = min(multiprocessing.cpu_count(), 8)
    
    async def _parse_files_parallel(
        self, 
        file_list: List[tuple]  # [(file_path, content, language), ...]
    ) -> List[dict]:
        """Parse all files in parallel using a process pool."""
        
        loop = asyncio.get_event_loop()
        results = []
        
        with ProcessPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            # Submit all files at once
            futures = [
                loop.run_in_executor(executor, _parse_file_worker, args)
                for args in file_list
            ]
            
            # Collect results as they complete
            for future in asyncio.as_completed(futures):
                try:
                    result = await future
                    results.append(result)
                    # Update progress display here
                    self._progress_callback("parsed", result.get("file_path", ""))
                except Exception as e:
                    logger.error(f"Parse worker failed: {e}")
        
        return results
```

### Important Windows compatibility note
On Windows, `ProcessPoolExecutor` requires the entry point to be protected with `if __name__ == '__main__':`. The module-level worker function approach above handles this correctly. Test specifically on Windows after implementing.

### Expected speedup
On a 4-core machine: 3 to 4× faster parsing.
On an 8-core machine: 5 to 7× faster parsing.
On a 16-core machine: 8 to 12× faster parsing.

### Verification
```bash
# Time the current indexing
time uv run repo index . --structural

# Should be noticeably faster than before
# Check all files were still parsed correctly:
uv run repo trace PythonParser
uv run repo architecture
```

---

## IMPROVEMENT 3 — Batch Graph Writes

### What to change
**File:** `core/graph/builder.py`

### The problem
Writing nodes and edges to Neo4j one at a time creates thousands of round trips. Each round trip has network overhead even on localhost. Batching 500 items into a single Cypher statement eliminates 499 round trips.

### How to implement it

```python
# core/graph/builder.py

BATCH_SIZE = 500  # Tune based on Neo4j memory — 500 is safe default

class GraphBuilder:
    
    async def build_from_parsed_files_batched(
        self, 
        parsed_files: List[dict]
    ) -> None:
        """Write all nodes and edges to Neo4j in large batches."""
        
        # Collect everything first
        all_nodes = []
        all_relationships = []
        
        for parsed_file in parsed_files:
            if parsed_file.get("status") != "success":
                continue
            
            # File node
            all_nodes.append({
                "label": "File",
                "properties": {
                    "path": parsed_file["file_path"],
                    "language": self._detect_language(parsed_file["file_path"]),
                    "sha256": parsed_file.get("sha256_hash", ""),
                }
            })
            
            # Entity nodes
            for entity in parsed_file.get("entities", []):
                label = self._entity_type_to_label(entity["entity_type"])
                all_nodes.append({
                    "label": label,
                    "properties": {
                        "name": entity["name"],
                        "fqn": entity["fqn"],
                        "file_path": entity["file_path"],
                        "line_start": entity["line_start"],
                        "line_end": entity["line_end"],
                        "language": entity["language"],
                    }
                })
                
                # CONTAINS relationship: File → Entity
                all_relationships.append({
                    "from_fqn": parsed_file["file_path"],
                    "to_fqn": entity["fqn"],
                    "type": "CONTAINS",
                })
            
            # All other relationships
            for rel in parsed_file.get("relationships", []):
                all_relationships.append({
                    "from_fqn": rel["from_fqn"],
                    "to_fqn": rel["to_fqn"],
                    "type": rel["relationship_type"],
                })
        
        # Write nodes in batches
        await self._write_nodes_batched(all_nodes)
        
        # Write relationships in batches (nodes must exist first)
        await self._write_relationships_batched(all_relationships)
    
    async def _write_nodes_batched(self, nodes: List[dict]) -> None:
        """Write nodes to Neo4j in batches of BATCH_SIZE."""
        
        for i in range(0, len(nodes), BATCH_SIZE):
            batch = nodes[i : i + BATCH_SIZE]
            
            # Group by label for efficient Cypher
            by_label = {}
            for node in batch:
                label = node["label"]
                if label not in by_label:
                    by_label[label] = []
                by_label[label].append(node["properties"])
            
            async with self.client.session() as session:
                for label, props_list in by_label.items():
                    # UNWIND is the key — one query writes many nodes
                    cypher = f"""
                    UNWIND $props AS props
                    MERGE (n:{label} {{fqn: props.fqn}})
                    SET n += props
                    """
                    await session.run(cypher, props=props_list)
    
    async def _write_relationships_batched(
        self, 
        relationships: List[dict]
    ) -> None:
        """Write relationships in batches using UNWIND."""
        
        # Group by relationship type
        by_type = {}
        for rel in relationships:
            rel_type = rel["type"]
            if rel_type not in by_type:
                by_type[rel_type] = []
            by_type[rel_type].append({
                "from_fqn": rel["from_fqn"],
                "to_fqn": rel["to_fqn"],
            })
        
        async with self.client.session() as session:
            for rel_type, rels in by_type.items():
                for i in range(0, len(rels), BATCH_SIZE):
                    batch = rels[i : i + BATCH_SIZE]
                    
                    cypher = f"""
                    UNWIND $rels AS rel
                    MATCH (a {{fqn: rel.from_fqn}})
                    MATCH (b {{fqn: rel.to_fqn}})
                    MERGE (a)-[:{rel_type}]->(b)
                    """
                    await session.run(cypher, rels=batch)
```

### Expected speedup
10,000 nodes written one at a time: ~20 seconds.
10,000 nodes written in batches of 500: ~2 seconds.
That is a 10× speedup on the graph write phase.

### Verification
```bash
# In Neo4j browser after re-indexing:
MATCH (n) RETURN count(n) as total_nodes
MATCH ()-[r]->() RETURN count(r) as total_relationships

# Counts should match previous run — same data, faster write
```

---

## IMPROVEMENT 4 — Batch Embeddings with Single Model Instance

### What to change
**File:** `core/search/embedder.py`

### The problem
The embedding model is heavy. Loading it once and processing 256 items at a time is far more efficient than loading per request or embedding one item at a time. The model's batch processing is optimised at the matrix level — 256 items in one call takes roughly the same time as 8 items.

### How to implement it

```python
# core/search/embedder.py

EMBEDDING_BATCH_SIZE = 256  # Sweet spot for CPU — increase to 512+ with GPU

class EmbeddingPipeline:
    
    _instance = None  # Singleton model instance
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
    
    def get_model(self):
        """Lazy-load model once, reuse forever."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded and cached")
        return self._model
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of texts in one model call.
        Always use this instead of calling embed() in a loop.
        """
        if not texts:
            return []
        
        model = self.get_model()
        
        # Process in chunks of EMBEDDING_BATCH_SIZE
        all_embeddings = []
        for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            chunk = texts[i : i + EMBEDDING_BATCH_SIZE]
            embeddings = model.encode(
                chunk,
                batch_size=EMBEDDING_BATCH_SIZE,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            all_embeddings.extend(embeddings.tolist())
        
        return all_embeddings
    
    def embed_entities(self, entities: List[dict]) -> List[dict]:
        """
        Embed all entities in one pass.
        Returns entities with 'embedding' field added.
        """
        # Build text representations for embedding
        texts = []
        for entity in entities:
            text = self._entity_to_text(entity)
            texts.append(text)
        
        # Single model call for ALL entities
        embeddings = self.embed_batch(texts)
        
        # Attach embeddings to entities
        for entity, embedding in zip(entities, embeddings):
            entity["embedding"] = embedding
        
        return entities
    
    def _entity_to_text(self, entity: dict) -> str:
        """Convert entity to text for embedding. Include context."""
        parts = []
        
        name = entity.get("name", "")
        entity_type = entity.get("entity_type", "")
        docstring = entity.get("docstring", "") or ""
        raw_code = entity.get("raw_code", "") or ""
        
        parts.append(f"{entity_type}: {name}")
        if docstring:
            parts.append(docstring[:200])
        if raw_code:
            # Only embed first 300 chars of code
            # Full code is retrieved from file when needed
            parts.append(raw_code[:300])
        
        return " ".join(parts)
```

### What NOT to embed
Do not embed every variable, every getter, every setter. This wastes vectors on noise. Only embed entities with `entity_type` in this list:

```python
EMBEDDABLE_TYPES = {
    "class",
    "function", 
    "module",
    "interface",
    "api_route",
    "db_model",
}

# In the indexer, filter before embedding:
entities_to_embed = [
    e for e in all_entities 
    if e.get("entity_type") in EMBEDDABLE_TYPES
    and len(e.get("name", "")) > 2  # Skip single-char names
    and not e.get("name", "").startswith("_")  # Skip private helpers
]
```

This alone typically reduces vector count by 40 to 60% with minimal impact on search quality. On a 50,000 entity codebase you go from 50,000 vectors to ~20,000 vectors. Search is faster. Storage is smaller. Quality is the same or better because noise is removed.

### Expected speedup
Embedding 5,000 entities one at a time: ~4 minutes.
Embedding 5,000 entities in batches of 256: ~25 seconds.
That is a 10× speedup on the embedding phase.

### Verification
```bash
# After re-indexing with batched embeddings:
uv run repo search "parser"
uv run repo search "error handling"
uv run repo search "database connection"
# All should still return relevant results
```

---

## IMPROVEMENT 5 — Embedding Cache by Content Hash

### What to change
**File:** `core/search/embedder.py` and `core/storage/models/file_hash.py`

### The problem
If a file has not changed since the last index, its entities have not changed, which means their embeddings have not changed. There is no reason to re-embed them. Storing the hash-to-embedding mapping eliminates most embedding work on re-indexing.

### How to implement it

Add a cache table to PostgreSQL:

```python
# core/storage/models/embedding_cache.py

from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from core.storage.database import Base

class EmbeddingCache(Base):
    __tablename__ = "embedding_cache"
    
    # Key: SHA256 of the entity's raw_code
    content_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    
    # The entity identifier
    fqn: Mapped[str] = mapped_column(String(1024), index=True)
    
    # Serialized embedding vector (JSON array)
    embedding_json: Mapped[str] = mapped_column(Text)
    
    # Model that produced this embedding
    # If model changes, cache is invalidated automatically
    model_name: Mapped[str] = mapped_column(String(256))
    
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

Use the cache in the embedding pipeline:

```python
# core/search/embedder.py

import hashlib
import json

class EmbeddingPipeline:
    
    async def embed_entities_with_cache(
        self, 
        entities: List[dict],
        storage_client,
    ) -> List[dict]:
        """
        Embed entities, using cached embeddings where available.
        Only calls the model for entities whose content has changed.
        """
        
        cache_hits = 0
        to_embed = []
        cached_results = {}
        
        # Check cache for each entity
        for entity in entities:
            content = entity.get("raw_code", "") or entity.get("name", "")
            content_hash = hashlib.sha256(
                content.encode("utf-8", errors="replace")
            ).hexdigest()
            entity["_content_hash"] = content_hash
            
            # Check if we have a cached embedding for this content
            cached = await storage_client.get_embedding_cache(
                content_hash, 
                self.model_name
            )
            
            if cached:
                cached_results[content_hash] = cached
                cache_hits += 1
            else:
                to_embed.append(entity)
        
        logger.info(
            f"Embedding cache: {cache_hits} hits, "
            f"{len(to_embed)} need embedding"
        )
        
        # Embed only the uncached entities
        if to_embed:
            newly_embedded = self.embed_entities(to_embed)
            
            # Store new embeddings in cache
            for entity in newly_embedded:
                await storage_client.set_embedding_cache(
                    entity["_content_hash"],
                    entity["fqn"],
                    entity["embedding"],
                    self.model_name
                )
        
        # Attach correct embeddings to all entities
        for entity in entities:
            content_hash = entity["_content_hash"]
            if content_hash in cached_results:
                entity["embedding"] = cached_results[content_hash]
        
        return entities
```

### Expected speedup on re-indexing
First index: no cache benefit (all entities are new).
Second index after minor changes: 80 to 95% cache hit rate. Embedding phase goes from 2 minutes to under 10 seconds.
This is the single biggest improvement for daily developer workflow where re-indexing happens constantly.

### Alembic migration
```bash
uv run alembic revision --autogenerate -m "add embedding cache table"
uv run alembic upgrade head
```

### Verification
```bash
# First index (no cache)
time uv run repo index . --full

# Second index, no changes
time uv run repo index . --full
# Should be dramatically faster

# Make one small change to a file
# Third index
time uv run repo index . --full
# Only changed file should re-embed
```

---

## IMPROVEMENT 6 — Smart Incremental Indexing

### What to change
**File:** `core/indexer/incremental.py`

### The current problem
Incremental indexing exists but needs to be smarter. It should skip not just unchanged files but also handle the case where dependencies of a file changed even if the file itself did not.

### How to implement it

```python
# core/indexer/incremental.py

class IncrementalIndexer:
    
    async def get_changed_files(
        self, 
        repo_path: str,
        all_files: List[Path]
    ) -> tuple[List[Path], List[Path]]:
        """
        Returns (changed_files, unchanged_files).
        
        A file is considered changed if:
        1. Its SHA256 hash differs from stored hash
        2. It is new (no stored hash)
        
        A file is considered unchanged if:
        1. Hash matches AND
        2. Its entry exists in Neo4j (graph was not corrupted)
        """
        
        changed = []
        unchanged = []
        
        # Get all stored hashes in one query (not one per file)
        stored_hashes = await self.storage.get_all_file_hashes(repo_path)
        
        # Get all files that have nodes in Neo4j
        indexed_files = await self.graph.get_indexed_files(repo_path)
        indexed_set = set(indexed_files)
        
        for file_path in all_files:
            rel_path = str(file_path.relative_to(repo_path))
            
            try:
                content = file_path.read_bytes()
                current_hash = hashlib.sha256(content).hexdigest()
            except (PermissionError, OSError):
                logger.warning(f"Cannot read {rel_path}, skipping")
                continue
            
            stored_hash = stored_hashes.get(rel_path)
            is_in_graph = rel_path in indexed_set
            
            if stored_hash == current_hash and is_in_graph:
                unchanged.append(file_path)
            else:
                changed.append(file_path)
        
        logger.info(
            f"Incremental analysis: {len(changed)} changed, "
            f"{len(unchanged)} unchanged"
        )
        
        return changed, unchanged
    
    async def get_all_file_hashes_bulk(self, repo_path: str) -> dict:
        """
        Get all stored hashes in ONE database query.
        Never query one file at a time in a loop.
        """
        async with self.storage.session() as session:
            result = await session.execute(
                "SELECT file_path, sha256 FROM file_hashes "
                "WHERE repo_path = :repo_path",
                {"repo_path": repo_path}
            )
            return {row.file_path: row.sha256 for row in result.fetchall()}
```

### Verification
```bash
# Index once
uv run repo index .

# Touch one file
echo "# comment" >> core/parser/base.py

# Re-index — should be very fast
time uv run repo index .
# Look for "X changed, Y unchanged" in output
# Y should be large, X should be 1
```

---

## IMPROVEMENT 7 — Rich Live Progress Display

### What to change
**File:** `cli/commands/index.py`

### How to implement it

```python
# cli/commands/index.py

from rich.progress import (
    Progress, SpinnerColumn, BarColumn, 
    TextColumn, TimeElapsedColumn, TimeRemainingColumn,
    TaskProgressColumn
)
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.console import Console
from rich import box
import time

console = Console()

def display_index_progress(repo_path: str, pipeline: IndexPipeline):
    """
    Beautiful real-time progress display.
    Shows three parallel stages with ETAs.
    """
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=35),
        TaskProgressColumn(),
        TextColumn("({task.completed}/{task.total})"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,  # Keep output after completion
    ) as progress:
        
        # Three tasks shown simultaneously
        discover_task = progress.add_task(
            "Discovering files", total=None
        )
        parse_task = progress.add_task(
            "Parsing + Graph   ", total=100, start=False
        )
        embed_task = progress.add_task(
            "Embedding (bkgnd) ", total=100, start=False
        )
        
        # File discovery
        files = pipeline.discover_files(repo_path)
        progress.update(
            discover_task, 
            completed=len(files),
            total=len(files),
            description=f"Found {len(files)} files      "
        )
        
        # Phase 1: Parse + Graph
        progress.start_task(parse_task)
        progress.update(parse_task, total=len(files))
        
        for i, result in enumerate(pipeline.parse_files_streaming(files)):
            progress.update(parse_task, advance=1)
            # Show current file being parsed
            filename = os.path.basename(result.get("file_path", ""))
            progress.update(
                parse_task, 
                description=f"Parsing: {filename[:25]:<25}"
            )
        
        progress.update(
            parse_task,
            description="[green]✓ Structural ready  "
        )
        
        # Phase 2: Embed (can show as starting)
        progress.start_task(embed_task)
        # Embedding runs in background — update periodically
        # via callback from the background task
```

### What the output looks like

```
Indexing: /Users/john/my-project

Found 847 files

Parsing: core/parser/python.py           ████████████░░░░░░░  62%  (524/847)  0:00:08  ETA 0:00:05
✓ Structural ready                       ████████████████████ 100% (847/847)  0:00:14
Embedding (background)                   ████░░░░░░░░░░░░░░░░  18%  (152/847)  0:00:03  ETA 0:00:14

─────────────────────────────────────────────────────────────
✓ Structural index ready in 14.2s

  You can now run:
  → repo trace <symbol>
  → repo impact <symbol>  
  → repo architecture
  → repo dead-code

  Semantic search (repo search) will be ready in ~14s
─────────────────────────────────────────────────────────────
```

### Verification
```bash
uv run repo index .
# Visually verify the progress bars appear
# Verify Phase 1 completion message shows before embeddings finish
# Verify structural commands work immediately after Phase 1 message
```

---

## IMPROVEMENT 8 — `repo status` Command

### What to build
**New file:** `cli/commands/status.py`

This command tells the user the current state of the index at any time.

```python
# cli/commands/status.py

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

def status_command(
    repo_path: str = typer.Argument(".", help="Repository path")
):
    """Show the current state of the RIP index."""
    
    # Query all status information
    index_state = get_index_state(repo_path)
    neo4j_stats = get_neo4j_stats()
    qdrant_stats = get_qdrant_stats()
    git_stats = get_git_stats(repo_path)
    
    # Build display
    console.print()
    
    # Repository info
    console.print(Panel(
        f"[bold]Repository:[/bold] {repo_path}\n"
        f"[bold]Last indexed:[/bold] {index_state.last_indexed_at or 'Never'}\n"
        f"[bold]Status:[/bold] {index_state.status}",
        title="RIP Status",
        border_style="blue"
    ))
    
    # Index stats table
    table = Table(box=box.SIMPLE, show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    table.add_column("State", style="green")
    
    table.add_row("Files indexed", str(index_state.indexed_files), "✓")
    table.add_row("Entities", str(neo4j_stats.node_count), "✓")
    table.add_row("Relationships", str(neo4j_stats.rel_count), "✓")
    table.add_row("Vectors (Qdrant)", str(qdrant_stats.point_count), "✓")
    table.add_row("Developers (git)", str(git_stats.developer_count), 
                  "✓" if git_stats.developer_count > 0 else "⚠ run repo index")
    
    console.print(table)
    
    # Feature availability
    console.print("\n[bold]Features available:[/bold]")
    features = [
        ("repo trace", neo4j_stats.node_count > 0),
        ("repo impact", neo4j_stats.rel_count > 0),
        ("repo architecture", neo4j_stats.node_count > 0),
        ("repo dead-code", neo4j_stats.node_count > 0),
        ("repo search", qdrant_stats.point_count > 0),
        ("repo explain", qdrant_stats.point_count > 0),
        ("repo metrics", git_stats.developer_count > 0),
        ("repo onboard", neo4j_stats.node_count > 0),
    ]
    
    for cmd, available in features:
        icon = "[green]✓[/green]" if available else "[yellow]⟳[/yellow]"
        console.print(f"  {icon} {cmd}")
    
    # Modified files
    if index_state.modified_since_index > 0:
        console.print(
            f"\n[yellow]⚠ {index_state.modified_since_index} files modified "
            f"since last index. Run [bold]repo index .[/bold] to sync.[/yellow]"
        )
    
    console.print()
```

### Verification
```bash
uv run repo status
uv run repo status .
uv run repo status /path/to/another/project
# Should show meaningful numbers matching what is actually in the databases
```

---

## IMPROVEMENT 9 — `repo index --watch` Improved Display

### What to change
**File:** `cli/commands/index.py` — the watch mode section

### How to implement it

```python
# Watch mode display

from collections import deque
from datetime import datetime

class WatchDisplay:
    """Clean persistent display for watch mode."""
    
    def __init__(self, max_history: int = 5):
        self.history = deque(maxlen=max_history)
        self.console = Console()
    
    def record_update(
        self, 
        file_path: str, 
        duration_ms: int, 
        success: bool
    ):
        self.history.appendleft({
            "file": os.path.basename(file_path),
            "duration": duration_ms,
            "success": success,
            "time": datetime.now().strftime("%H:%M:%S"),
        })
        self._redraw()
    
    def _redraw(self):
        self.console.clear()
        self.console.print(
            Panel(
                "[bold blue]RIP Watch Mode[/bold blue] — "
                "monitoring for file changes\n"
                "[dim]Press Ctrl+C to stop[/dim]",
                border_style="blue"
            )
        )
        
        if not self.history:
            self.console.print("[dim]  Waiting for file changes...[/dim]")
            return
        
        self.console.print()
        for event in self.history:
            icon = "[green]✓[/green]" if event["success"] else "[red]✗[/red]"
            self.console.print(
                f"  {icon} [dim]{event['time']}[/dim]  "
                f"[cyan]{event['file']:<35}[/cyan]  "
                f"[dim]{event['duration']}ms[/dim]"
            )
```

The watch mode display should look like:

```
┌─ RIP Watch Mode — monitoring for file changes ──────────┐
│ Press Ctrl+C to stop                                     │
└──────────────────────────────────────────────────────────┘

  ✓ 14:23:45  core/parser/python.py              0.8s
  ✓ 14:22:12  core/graph/builder.py              1.1s
  ✓ 14:21:03  tests/unit/test_parser.py          0.6s
  ✓ 14:19:45  cli/commands/index.py              0.9s
```

---

## FINAL VERIFICATION — Run Everything

After all improvements are implemented, run this full sequence. Every single command must work.

```bash
# Clean state — delete existing index data
docker-compose restart neo4j qdrant postgres redis
sleep 20

# Run alembic migrations for new embedding cache table
uv run alembic upgrade head

# Full index with new pipeline
time uv run repo index .

# Immediately after (before background embedding finishes):
uv run repo trace PythonParser        # MUST work — Phase 1 complete
uv run repo impact BaseParser         # MUST work — Phase 1 complete
uv run repo architecture              # MUST work — Phase 1 complete

# Wait for background embedding to complete, then:
uv run repo search "parser"           # MUST work
uv run repo search "error handling"   # MUST work

# Status check
uv run repo status

# Full test suite
uv run pytest tests/ -v

# Linter
uv run ruff check .

# Re-index to verify incremental is fast
time uv run repo index .
# Second run should be dramatically faster than first
```

---

## PERFORMANCE TARGETS

After all improvements, these are the targets to hit:

| Repository size | Target time (first index) | Target time (re-index, no changes) |
|---|---|---|
| 50 files | Under 5 seconds | Under 1 second |
| 200 files | Under 15 seconds | Under 2 seconds |
| 1,000 files | Under 45 seconds | Under 5 seconds |
| 5,000 files | Under 3 minutes | Under 15 seconds |
| 20,000 files | Under 10 minutes | Under 30 seconds |

The key metric for re-indexing is "time to structural ready" not total time. Users should see "Structural index ready" within the first 30% of total index time for any size repo. Semantic indexing runs behind that and does not block them.

---

## WHAT NOT TO DO

Do not add GPU-specific code paths in this phase. GPU acceleration is valuable but adds hardware dependency and complexity. The improvements above work on any developer machine.

Do not implement distributed workers (RabbitMQ, Redis Streams) in this phase. Those are for multi-machine deployments and add significant operational complexity. The parallel process pool approach handles single-machine scaling well up to 1M LOC.

Do not change the default embedding model from `all-MiniLM-L6-v2`. It was chosen for the right reasons — small, fast, good quality. Changing it now requires re-indexing all existing data and invalidates the embedding cache.

Do not implement ONNX conversion in this phase. It is valuable but complex and the batch size improvements give most of the same speedup with much less risk.

Do not change any existing command output formats. Users and the MCP server depend on consistent output shapes.
