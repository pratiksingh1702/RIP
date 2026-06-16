Good topic. Let me think through this properly.

---

## The Core Problem

Right now when someone runs `repo index .` one of two things happens. Either it finishes quickly and they wonder if it actually did anything, or it takes 2 minutes and they think it crashed. Both feel bad. Production grade indexing solves both problems simultaneously — it is fast AND it constantly communicates what it is doing.

---

## The Display Problem First

Before touching performance, the display is the most important fix because it changes how the user perceives the speed even before you make it faster.

Look at how `cargo build` works in Rust. It shows a progress bar, names the current file being compiled, shows a count like `[47/203]`, and updates in real time. The user always knows exactly where they are. Even if it takes 3 minutes it never feels hung because something is visibly happening every second.

For RIP, the indexing output should look something like this while running:

```
Indexing repository: /Users/john/myproject

Discovering files...
  Found 847 files (Python: 312, TypeScript: 201, Go: 334)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 
Parsing  [████████████████░░░░░░░░░░░░░░░░░░]  47%  [156/312]
         Currently: core/parser/languages/python.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 
Graph    [██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░]  18%  [28/156]
         Writing nodes and edges to Neo4j...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Embedding [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]   0%  Queued

  Elapsed: 00:00:23     ETA: ~00:01:45
```

Rich library supports exactly this with `Progress`, `Live`, and `Panel` components. The key insight is that parsing, graph building, and embedding can all show progress simultaneously because they run in a pipeline — while file 100 is being embedded, file 200 is being parsed. Show all three bars at once.

The ETA calculation matters a lot psychologically. Even a rough estimate completely eliminates the "is this hung" anxiety. You can calculate it by measuring the average time per file for the first 10 files and extrapolating.

---

## The Performance Problem

There are four stages in indexing and each has a different bottleneck.

**File discovery** is already fast. Walking a directory tree is IO bound and modern SSDs handle it in milliseconds for most repos. Not worth optimizing.

**Parsing with Tree-sitter** is CPU bound and embarrassingly parallel — each file is completely independent. Right now you are probably parsing files one by one in a loop. The fix is `asyncio.gather` with a semaphore to limit concurrency, or even better a `ProcessPoolExecutor` since Tree-sitter releases the GIL. On an 8-core machine you could parse 8 files simultaneously. That alone gives you roughly 5 to 7× speedup on the parsing stage for large repos.

The sweet spot for concurrency is typically `min(cpu_count, 8)` workers. Above 8 the overhead of coordination starts eating into the gains. Below 4 you are leaving performance on the table.

**Graph building** is IO bound — you are waiting for Neo4j to acknowledge writes. The biggest win here is batching. Instead of writing one node at a time and waiting for confirmation, collect 500 nodes and write them all in one Cypher transaction. Neo4j handles batched writes dramatically faster than individual writes. The difference between writing 10,000 nodes one at a time versus in batches of 500 is roughly 10× in real world performance.

Also use `MERGE` instead of `CREATE` on nodes but use `CREATE` on relationships after confirming nodes exist. `MERGE` on relationships is expensive because it has to check for existence first.

**Embedding generation** is the hardest to speed up because it is GPU or CPU bound on the model itself. Three approaches here.

First, batching. Most embedding models including MiniLM run dramatically faster when you pass 32 or 64 texts at once instead of one at a time. The model processes a batch in almost the same time as a single item due to matrix operations. This alone is often a 20 to 30× speedup.

Second, skip unchanged files. This is the most impactful optimization overall and it already exists in the incremental indexer but should also apply to the first index run. Store a hash of each file's content in PostgreSQL. On subsequent runs, compare hashes before doing any work. If the hash matches, skip parsing, skip graph rebuild, skip embedding. Only process files that actually changed. For a developer who indexes daily, this means most runs complete in seconds because 95% of files have not changed.

Third, consider running embedding asynchronously from parsing and graph building. You do not need embeddings to answer `repo trace` or `repo impact`. You only need them for `repo search`. So the index command could return to the user as "ready for structural queries" after parsing and graph building complete, then continue embedding in the background. The user can immediately run `repo trace` while embedding finishes. A status command shows whether semantic search is ready yet.

---

## The Incremental Indexing UX

For the common case — a developer who has already indexed and just saved a file — the output should be nearly invisible:

```
[RIP] Detected change: core/parser/python.py
[RIP] Re-indexed in 0.8s — 3 entities updated
```

This appears in the corner of VS Code or as a brief terminal message and disappears. It communicates that the system is alive and responsive without demanding attention.

The current incremental indexer runs on file save via the VS Code extension. Make sure it has a debounce — if someone saves 5 files in 2 seconds during a refactor, wait 800ms after the last save before indexing rather than firing 5 separate index jobs.

---

## Specific Numbers to Aim For

For a production grade feel these are the targets:

A 50,000 LOC repo should complete full first index in under 45 seconds on a typical developer laptop. Right now it probably takes 2 to 4 minutes.

A 200,000 LOC repo should complete in under 3 minutes. Right now it probably takes 8 to 15 minutes.

Incremental updates on a single file change should complete in under 2 seconds. This is achievable with the current architecture.

The gap between current and target is almost entirely explained by three things: single-threaded parsing, one-at-a-time graph writes, and embedding one chunk at a time. Fix those three and you hit the targets.

---

## The Phases Approach for UX

There is a clever UX pattern where you split indexing into phases and give the user access to features as each phase completes rather than making them wait for everything.

Phase 1 is file discovery and parsing — takes 5 to 20 seconds. When this completes you have all entities and relationships. `repo trace`, `repo impact`, `repo architecture`, `repo dead-code` all become available immediately. Show a message: "Structural analysis ready. Semantic search building..."

Phase 2 is embedding and vector storage — takes the remaining time. When this completes `repo search` and `repo explain` become available. Show: "Semantic search ready. Full index complete."

Phase 3 is git history ingestion — can run entirely in the background. When complete: "Git intelligence ready. `repo metrics` and `repo risk` now available."

This way a developer gets value from the tool in 20 seconds even on a large repo, rather than waiting 3 minutes for everything before they can do anything.

---

## The Status Command

Add `repo status` that shows the current state of the index at any time:

```
Repository: /Users/john/myproject
Last indexed: 2 minutes ago

Index health:
  Files:     847  (12 modified since last index)
  Entities:  2,847
  Relations: 8,234

Features available:
  ✓ Structural analysis (trace, impact, dead-code)
  ✓ Semantic search
  ✓ Architecture
  ⟳ Git intelligence (updating in background...)

Run 'repo index .' to sync 12 modified files
```

This tells the user everything they need to know in one glance. They know the index is not stale. They know what is available. They know if anything is still processing.

---

## The Watch Mode Display

`repo index --watch` should show a clean persistent display:

```
Watching: /Users/john/myproject
Last update: 3 seconds ago

  Modified → core/parser/python.py         0.8s ✓
  Modified → core/graph/builder.py         1.1s ✓
  Modified → tests/unit/test_parser.py     0.6s ✓

Press Ctrl+C to stop watching
```

New lines appear at the top as files change. Old lines fade or scroll. The user always sees the three or four most recent updates and knows the watcher is alive and responsive.

---

## What to Implement First

If you had to pick the single highest impact change for user experience, it is the real-time progress display with ETA. Even before you make indexing faster, showing a progress bar with estimated time remaining completely eliminates the "is this hung" perception.

Second highest impact is file batching in the graph builder. This is a code change of maybe 30 lines and gives you 10× faster graph writes.

Third is parallel parsing with a process pool. This is more complex but gives you 5 to 7× faster parse times.

Fourth is the phased approach — letting users run structural commands while embedding continues in the background. This changes the perceived wait time from 3 minutes to 20 seconds even if the total work takes the same amount of time.

The embedding model switch from BGE-M3 to MiniLM is also worth doing for first-time setup experience — 90MB download instead of 2GB is a night and day difference for someone trying the tool for the first time.