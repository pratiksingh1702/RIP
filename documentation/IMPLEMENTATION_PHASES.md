# Repository Intelligence Platform — Implementation Phases

> Companion file to `REPO_INTELLIGENCE_PLATFORM.md`. That document is the
> **spec** (architecture, schemas, stack rationale, file structure). This
> file is the **execution plan** — broken into phases with checkboxes, each
> ending in a testable artifact before the next phase starts.
>
> AI agent instructions: work top-to-bottom. Do not start a phase until all
> checkboxes in the previous phase are checked AND its "Phase Gate Test"
> passes. Reference section numbers from `REPO_INTELLIGENCE_PLATFORM.md`
> (e.g. "§9 Database Schemas") for exact schemas/contracts when implementing
> a task.

---

## Phase 0 — Infrastructure & Project Skeleton
*Spec refs: §5 Tech Stack, §7 File Structure, §16 Step 1*

### 0.1 — Understand the Complete File Structure First

Before writing any code, the agent must read **§7 Complete File Structure**
in `REPO_INTELLIGENCE_PLATFORM.md` in full and create the entire directory
skeleton up front (even though most files will be empty stubs until later
phases). This avoids structural drift later — every later phase only fills
in files that already exist in the right place.

The target structure is:

```
repo-intelligence/
├── README.md
├── REPO_INTELLIGENCE_PLATFORM.md      ← spec (already provided)
├── IMPLEMENTATION_PHASES.md           ← this file
├── pyproject.toml
├── uv.lock
├── .env.example
├── .env
├── docker-compose.yml                 ← Neo4j + Qdrant + PostgreSQL + Redis
├── Makefile
│
├── cli/                               ← Typer CLI entry point
│   ├── main.py
│   ├── commands/
│   │   ├── init.py
│   │   ├── index.py
│   │   ├── trace.py
│   │   ├── impact.py
│   │   ├── explain.py
│   │   ├── search.py
│   │   ├── dead_code.py
│   │   ├── onboard.py
│   │   ├── architecture.py
│   │   └── metrics.py
│   └── output/
│       ├── formatters.py
│       └── themes.py
│
├── server/                            ← FastAPI application
│   ├── app.py
│   ├── config.py
│   ├── middleware/
│   │   ├── logging.py
│   │   └── errors.py
│   ├── routers/
│   │   ├── index.py
│   │   ├── trace.py
│   │   ├── impact.py
│   │   ├── search.py
│   │   ├── explain.py
│   │   ├── graph.py
│   │   ├── analysis.py
│   │   ├── onboard.py
│   │   └── architecture.py
│   └── schemas/
│       ├── requests.py
│       └── responses.py
│
├── core/                              ← pure engine, no HTTP/CLI concerns
│   ├── parser/                        ← Layer 1: source parsing
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── traversal.py
│   │   ├── languages/
│   │   │   ├── python.py
│   │   │   ├── java.py
│   │   │   ├── typescript.py
│   │   │   ├── go.py
│   │   │   └── rust.py
│   │   ├── extractors/
│   │   │   ├── entities.py
│   │   │   ├── imports.py
│   │   │   ├── apis.py
│   │   │   └── databases.py
│   │   └── git_ingestor.py
│   │
│   ├── graph/                         ← Layer 2: Neo4j
│   │   ├── client.py
│   │   ├── schema.py
│   │   ├── builder.py
│   │   ├── queries/
│   │   │   ├── trace.py
│   │   │   ├── impact.py
│   │   │   ├── dead_code.py
│   │   │   ├── coupling.py
│   │   │   ├── architecture.py
│   │   │   └── ownership.py
│   │   └── models.py
│   │
│   ├── search/                        ← Layer 3: Qdrant vector search
│   │   ├── client.py
│   │   ├── embedder.py
│   │   ├── indexer.py
│   │   ├── searcher.py
│   │   └── reranker.py
│   │
│   ├── storage/                       ← Layer 4: PostgreSQL + Redis
│   │   ├── database.py
│   │   ├── cache.py
│   │   ├── models/
│   │   │   ├── index_state.py
│   │   │   ├── file_hash.py
│   │   │   └── analysis_job.py
│   │   └── migrations/
│   │       └── versions/
│   │
│   ├── analysis/                      ← Layer 5: analysis engines
│   │   ├── base.py
│   │   ├── flow_tracer.py
│   │   ├── impact_analyser.py
│   │   ├── dead_code_detector.py
│   │   ├── coupling_analyser.py
│   │   ├── risk_scorer.py
│   │   ├── onboard_engine.py
│   │   └── architecture_generator.py
│   │
│   ├── llm/                           ← Layer 6: LLM explanation engine
│   │   ├── client.py
│   │   ├── context_assembler.py
│   │   ├── prompts/
│   │   │   ├── explain.py
│   │   │   ├── trace.py
│   │   │   ├── onboard.py
│   │   │   └── architecture.py
│   │   └── models.py
│   │
│   └── indexer/                       ← orchestration
│       ├── pipeline.py
│       ├── incremental.py
│       └── worker.py
│
├── vscode-extension/                  ← VS Code extension (TypeScript)
│   ├── package.json
│   ├── tsconfig.json
│   ├── .vscodeignore
│   ├── src/
│   │   ├── extension.ts
│   │   ├── client/
│   │   │   ├── apiClient.ts
│   │   │   └── serverManager.ts
│   │   ├── providers/
│   │   │   ├── hoverProvider.ts
│   │   │   ├── codeActionProvider.ts
│   │   │   └── definitionProvider.ts
│   │   ├── panels/
│   │   │   ├── dependencyGraphPanel.ts
│   │   │   ├── impactPanel.ts
│   │   │   ├── tracePanel.ts
│   │   │   └── architecturePanel.ts
│   │   ├── watchers/
│   │   │   └── fileSaveWatcher.ts
│   │   └── utils/
│   │       ├── lspHelper.ts
│   │       └── themeHelper.ts
│   └── webviews/
│       ├── graph/
│       │   ├── index.html
│       │   ├── graph.js
│       │   └── graph.css
│       ├── impact/
│       │   ├── index.html
│       │   └── impact.js
│       └── trace/
│           ├── index.html
│           └── trace.js
│
└── tests/
    ├── fixtures/
    │   └── sample_repos/
    │       └── python_simple/
    ├── test_parser_python.py
    ├── test_graph_builder.py
    └── ... (one test file per module added in later phases)
```

**Layer rule (from §3 Water Principle):** `core/` has zero knowledge of
`cli/` or `server/`. `cli/` and `server/` are thin clients calling into
`core/`. Every later phase must respect this — no shortcuts that import
`cli`/`server` modules into `core`.

### 0.2 — Setup Tasks

- [ ] Initialize project with `uv init repo-intelligence`
- [ ] Add core deps: `fastapi uvicorn typer rich pydantic pydantic-settings`
- [ ] Add parsing deps: `tree-sitter tree-sitter-languages gitpython watchdog`
- [ ] Add graph/search deps: `neo4j qdrant-client sentence-transformers`
- [ ] Add storage deps: `sqlalchemy alembic asyncpg redis`
- [ ] Add LLM deps: `litellm`
- [ ] Add dev deps: `pytest pytest-asyncio ruff`
- [ ] Create full directory skeleton per §7 (empty `__init__.py` files for cli/, server/, core/parser, core/graph, core/search, core/storage, core/analysis, core/llm, core/indexer, tests/)
- [ ] Write `docker-compose.yml` (Neo4j + Qdrant + PostgreSQL + Redis)
- [ ] Write `.env.example` and `pyproject.toml` settings
- [ ] Write `config.toml` template per §15

**Phase Gate Test:**
- [ ] `docker-compose up -d` brings up all 4 services healthy
- [ ] `uv run python -c "import fastapi, typer, neo4j, qdrant_client"` succeeds with no import errors
- [ ] Directory tree matches §7 structure (spot check 5 key paths)

---

## Phase 1 — Parser Layer (Python only first)
*Spec refs: §7 core/parser/, §16 Step 2*

- [ ] `core/parser/base.py` — define `ParsedEntity`, `ParsedRelationship`, `ParsedFile`, `BaseParser` (Pydantic models)
- [ ] `core/parser/languages/python.py` — `PythonParser(BaseParser)` using tree-sitter-python; extract classes, functions, methods, imports
- [ ] `core/parser/registry.py` — `LanguageParserRegistry` mapping file extension → parser class
- [ ] `core/parser/traversal.py` — `FileTraversal`: walks repo respecting `.gitignore` and `exclude` config
- [ ] `core/parser/extractors/entities.py` — extract classes/functions/interfaces as `ParsedEntity`
- [ ] `core/parser/extractors/imports.py` — extract + resolve import relationships
- [ ] Create `tests/fixtures/sample_repos/python_simple/` (small multi-file Python project with imports, classes, calls)
- [ ] `tests/test_parser_python.py` — unit tests for entity/relationship extraction
- [ ] Standalone script `parse_test.py` that prints all extracted entities for a given path

**Phase Gate Test:**
- [ ] `python parse_test.py ./tests/fixtures/sample_repos/python_simple` prints correct entities + relationships
- [ ] `pytest tests/test_parser_python.py` passes
- [ ] Parser does not crash on a file with syntax errors (graceful skip)

---

## Phase 2 — Graph Layer (Neo4j)
*Spec refs: §9 Database Schemas, §7 core/graph/, §16 Step 3*

- [ ] `core/graph/client.py` — `Neo4jClient` async connection pool
- [ ] `core/graph/schema.py` — node labels, relationship types, constraints/index setup (per §9)
- [ ] `core/graph/models.py` — Pydantic models for graph nodes/edges
- [ ] `core/graph/builder.py` — `GraphBuilder`: takes `ParsedFile` → writes nodes/edges to Neo4j
- [ ] `core/graph/queries/trace.py` — Cypher: full call chain from entry point
- [ ] `core/graph/queries/impact.py` — Cypher: reverse traversal (what depends on X)
- [ ] `tests/test_graph_builder.py` — integration test against dockerized Neo4j

**Phase Gate Test:**
- [ ] Run schema setup against fresh Neo4j instance without error
- [ ] Index `python_simple` fixture → `MATCH (f:Function) RETURN f LIMIT 10` returns expected functions in Neo4j Browser
- [ ] `trace.py` query returns a non-empty call chain for a known entry point in the fixture
- [ ] `impact.py` query returns correct reverse dependents for a known symbol

---

## Phase 3 — CLI Skeleton + FastAPI Server (real index/trace/impact)
*Spec refs: §10 CLI Commands, §11 API Contracts, §7 cli/ + server/, §16 Step 4*

- [ ] `server/app.py` — FastAPI app factory
- [ ] `server/config.py` — settings via pydantic-settings (reads `config.toml`)
- [ ] `server/middleware/logging.py`, `server/middleware/errors.py`
- [ ] `server/schemas/requests.py`, `server/schemas/responses.py` — Pydantic contracts per §11
- [ ] `server/routers/index.py` — `POST /index`, `GET /index/status`
- [ ] `server/routers/trace.py` — `GET /trace/{symbol}`
- [ ] `server/routers/impact.py` — `GET /impact/{symbol}`
- [ ] `cli/main.py` — root Typer app, registers command groups
- [ ] `cli/commands/init.py` — `repo init` (writes `.repo-intel/config.toml`)
- [ ] `cli/commands/index.py` — `repo index [path] [--watch] [--incremental]` (real, calls parser + graph builder)
- [ ] `cli/commands/trace.py` — `repo trace <entry_point>` (real)
- [ ] `cli/commands/impact.py` — `repo impact <symbol>` (real)
- [ ] Stub all remaining commands (`explain`, `search`, `dead-code`, `onboard`, `architecture`, `metrics`) returning "not yet implemented"
- [ ] `cli/output/formatters.py` — plain/json/markdown/rich-table output

**Phase Gate Test:**
- [ ] `repo init ./sample_repo` creates valid config
- [ ] `repo index ./sample_repo` populates Neo4j
- [ ] `repo trace UserService` produces real, correctly-formatted output
- [ ] `repo impact PaymentService` produces real output
- [ ] FastAPI server starts; `/docs` (OpenAPI) loads; `/index`, `/trace/{symbol}`, `/impact/{symbol}` return 200 with correct schema
- [ ] Stub commands return clear "not implemented" message without crashing

---

## Phase 4 — Vector Search (Qdrant + Embeddings)
*Spec refs: §7 core/search/, §16 Step 5*

- [ ] `core/search/client.py` — Qdrant client wrapper
- [ ] `core/search/embedder.py` — `EmbeddingPipeline` using BGE-M3 (sentence-transformers), chunks code
- [ ] `core/search/indexer.py` — takes parsed entities, embeds, stores in Qdrant during index phase
- [ ] `core/search/searcher.py` — hybrid search (vector + metadata filters)
- [ ] `core/search/reranker.py` — cross-encoder reranker for top-k results
- [ ] Wire embedding step into `repo index` pipeline
- [ ] `cli/commands/search.py` — `repo search <query>` (real)
- [ ] `server/routers/search.py` — `GET /search?q=...`

**Phase Gate Test:**
- [ ] `repo index ./sample_repo` populates Qdrant collection with embeddings
- [ ] `repo search "database connection pooling"` returns semantically relevant functions (manually verify top-3 results make sense)
- [ ] `/search?q=...` API endpoint returns same results as CLI
- [ ] Re-running `repo index` does not duplicate embeddings

---

## Phase 5 — Analysis Engines
*Spec refs: §7 core/analysis/, §16 Step 6*

- [ ] `core/analysis/base.py` — `BaseAnalyser` abstract class
- [ ] `core/analysis/dead_code_detector.py` + `cli/commands/dead_code.py` (`repo dead-code`)
- [ ] `core/graph/queries/dead_code.py` — Cypher for nodes with no incoming edges
- [ ] `core/analysis/coupling_analyser.py` + `core/graph/queries/coupling.py` + `cli/commands/metrics.py` (`repo metrics`)
- [ ] `core/analysis/risk_scorer.py` — centrality × churn × coverage (uses `core/parser/git_ingestor.py`)
- [ ] `core/parser/git_ingestor.py` — GitPython: commits, blame, ownership, churn
- [ ] `core/graph/queries/ownership.py` — Cypher for file/module ownership from git data
- [ ] `core/analysis/onboard_engine.py` + `cli/commands/onboard.py` (`repo onboard --output ONBOARDING.md`)
- [ ] `core/analysis/architecture_generator.py` + `core/graph/queries/architecture.py` + `cli/commands/architecture.py` (`repo architecture --format=mermaid`)
- [ ] Add corresponding `server/routers/analysis.py`, `onboard.py`, `architecture.py` endpoints

**Phase Gate Test:**
- [ ] `repo dead-code` on fixture correctly identifies unused functions
- [ ] `repo metrics --module=X` returns coupling numbers
- [ ] `repo onboard --output ONBOARDING.md` generates a readable markdown file
- [ ] `repo architecture --format=mermaid` outputs valid Mermaid diagram syntax
- [ ] All CLI commands from §10 now work end-to-end (no remaining stubs) on a real (non-fixture) test repo

---

## Phase 6 — LLM Explanation Layer
*Spec refs: §4 Phase 2 Query flow, §7 core/llm/, §16 Step 7*

- [ ] `core/llm/models.py` — `LLMConfig`, `ModelProvider` enum
- [ ] `core/llm/client.py` — `LiteLLMClient` (Ollama default, Claude/OpenAI/Gemini optional)
- [ ] `core/llm/context_assembler.py` — merges graph + search results into a 3,000–8,000 token prompt context
- [ ] `core/llm/prompts/explain.py`, `trace.py`, `onboard.py`, `architecture.py` — prompt templates
- [ ] `cli/commands/explain.py` — `repo explain <topic>` (real)
- [ ] Wire `--explain` flag into `repo trace`
- [ ] `server/routers/explain.py` — `POST /explain`

**Phase Gate Test:**
- [ ] `repo explain "authentication flow" --explain` returns a coherent natural-language description grounded in actual graph/search context
- [ ] `repo trace UserService --explain` adds narration without breaking plain trace output
- [ ] Verify context sent to LLM stays within `max_context_tokens` (config) — log/print token count for confirmation
- [ ] System works with `explain_by_default = false` (LLM not called unless flag passed)

---

## Phase 7 — Incremental Indexing, Caching, Error Handling
*Spec refs: §13 Data Flow, §15 Configuration, §16 Step 9*

- [ ] `core/storage/database.py` — SQLAlchemy async engine + session factory
- [ ] `core/storage/models/index_state.py`, `file_hash.py`, `analysis_job.py` — ORM models
- [ ] Alembic migrations for the above (`core/storage/migrations/`)
- [ ] `core/storage/cache.py` — Redis client wrapper with TTL helpers
- [ ] `core/indexer/pipeline.py` — `IndexPipeline` full orchestration (parser → graph → search → storage)
- [ ] `core/indexer/incremental.py` — `IncrementalIndexer`: diff-based re-index using file hashes (per §13 pseudocode)
- [ ] `core/indexer/worker.py` — background worker for async indexing
- [ ] Wire `--incremental` and `--watch` flags in `repo index` (uses `watchdog`)
- [ ] Add Redis caching to hot graph queries (trace, impact, search)
- [ ] Add graceful-degradation error handling across parser/graph/search (per §3 Water Principle — never crash on unknown input)

**Phase Gate Test:**
- [ ] Modify one file in `sample_repo`, run `repo index --incremental` → only that file's nodes/embeddings are updated (verify via Neo4j/Qdrant counts)
- [ ] `repo index --watch` auto-reindexes on file save
- [ ] Repeated `trace`/`impact` queries hit Redis cache (verify latency drop or cache hit log)
- [ ] Feed an unsupported file type / corrupted file into indexing → system logs and skips, does not crash

---

## Phase 8 — VS Code Extension
*Spec refs: §12 VS Code Extension Architecture, §7 vscode-extension/, §16 Step 8*

- [ ] `vscode-extension/` project scaffold (`package.json`, `tsconfig.json`, `.vscodeignore`)
- [ ] `src/extension.ts` — `activate()`, registers commands + providers
- [ ] `src/client/serverManager.ts` — auto-start Python FastAPI server (respects `auto_start` config)
- [ ] `src/client/apiClient.ts` — HTTP client for FastAPI endpoints
- [ ] `src/watchers/fileSaveWatcher.ts` — `onDidSaveTextDocument` → trigger incremental re-index
- [ ] `src/providers/codeActionProvider.ts` — right-click context menu (trace/impact/explain)
- [ ] `src/providers/hoverProvider.ts` — inline hover explanations
- [ ] `src/providers/definitionProvider.ts` — graph-based go-to-definition with LSP fallback
- [ ] `src/panels/dependencyGraphPanel.ts` + `webviews/graph/` — D3 force-directed graph
- [ ] `src/panels/impactPanel.ts` + `webviews/impact/`
- [ ] `src/panels/tracePanel.ts` + `webviews/trace/`
- [ ] `src/panels/architecturePanel.ts`

**Phase Gate Test:**
- [ ] Install extension in VS Code dev host (`F5`)
- [ ] Extension auto-starts Python server on activation
- [ ] Right-click a class → "Show Dependency Graph" opens D3 webview with correct nodes
- [ ] Saving a file triggers incremental re-index (check server logs)
- [ ] Impact and Trace panels render real data for a selected symbol

---

## Phase 9 — Additional Language Parsers (Ongoing/Parallel)
*Spec refs: §5 Parsing layer, §16 Step 10*

- [ ] `core/parser/languages/typescript.py` — `TypeScriptParser(BaseParser)` (tree-sitter-typescript)
- [ ] `core/parser/languages/java.py` — `JavaParser(BaseParser)` (tree-sitter-java)
- [ ] `core/parser/languages/go.py` — `GoParser(BaseParser)` (tree-sitter-go)
- [ ] `core/parser/languages/rust.py` — `RustParser(BaseParser)` (tree-sitter-rust)
- [ ] `core/parser/extractors/apis.py` — detect REST/GraphQL/gRPC routes (per-language)
- [ ] `core/parser/extractors/databases.py` — detect ORM models/DB entities
- [ ] Register each new parser in `LanguageParserRegistry` — zero changes to existing code
- [ ] Add fixture repo + tests per new language under `tests/fixtures/sample_repos/`

**Phase Gate Test (per language, repeat):**
- [ ] `repo index` on the new-language fixture populates graph/search with correct entities
- [ ] `repo trace` / `repo impact` work across files of that language
- [ ] No regression in existing Python fixture tests (`pytest` full suite green)

---

## Final Integration — End-to-End Verification
*Spec refs: §16 Quick Start*

- [ ] Run full Quick Start sequence on a real multi-language repo:
  - [ ] `repo init` → `repo index`
  - [ ] `repo architecture`
  - [ ] `repo trace <entry_point>`
  - [ ] `repo impact <symbol>`
  - [ ] `repo search "<query>"`
  - [ ] `repo explain "<topic>"`
  - [ ] `repo dead-code`
  - [ ] `repo onboard --output ONBOARDING.md`
- [ ] All 4 infra services + FastAPI + VS Code extension run together without manual intervention
- [ ] Full `pytest` suite green
- [ ] `ruff check` clean
