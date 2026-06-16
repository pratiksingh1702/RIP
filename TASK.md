# RIP Build Tasks

## Phase 0 - Infrastructure & Skeleton
- [x] Create TASK.md tracker
- [x] Create root project files
- [x] Add pyproject.toml dependencies and tool config
- [x] Add Docker Compose services
- [x] Add environment templates
- [x] Add Makefile
- [x] Create full Python package skeleton
- [x] Create VS Code extension skeleton
- [x] Create docs and scripts skeleton
- [x] Create sample fixture repos
- [x] Add Phase 0 smoke tests
- [x] Run Phase 0 gate checks

## Phase 1 - Parser Layer
- [x] Add parser contracts
- [x] Add parser registry
- [x] Add file traversal
- [x] Add Python parser
- [x] Add parser extractor helpers
- [x] Add parser tests
- [x] Run Phase 1 gate checks

## Phase 2 - Graph Layer
- [x] Add Neo4j async client
- [x] Add graph schema setup
- [x] Add graph models
- [x] Add graph builder
- [x] Add trace query
- [x] Add impact query
- [x] Add graph integration tests
- [x] Run Phase 2 gate checks

## Phase 3 - CLI and FastAPI
- [x] Add FastAPI app factory
- [x] Add server config
- [x] Add middleware
- [x] Add request and response schemas
- [x] Add index, trace, and impact routers
- [x] Add Typer CLI root
- [x] Add init command
- [x] Add index command
- [x] Add trace command
- [x] Add impact command
- [x] Add stubs for remaining commands
- [x] Add CLI formatters
- [x] Run Phase 3 gate checks

Checkpoint after Phase 3: Infrastructure through CLI/API wiring is complete. Phase 1 added parser contracts, registry, traversal, Python AST parsing, extractor helpers, and parser tests. Phase 2 added the Neo4j client/schema, graph models, graph builder, trace and impact Cypher queries, and Neo4j integration coverage. Phase 3 wired real `repo init`, `repo index`, `repo trace`, and `repo impact`, plus FastAPI `/index`, `/index/status`, `/trace/{symbol}`, and `/impact/{symbol}` with response envelopes; future commands still return clear not-implemented stubs. A new agent should read `AGENT_BUILD_PROMPT.md` first for build rules, then `REPO_INTELLIGENCE_PLATFORM.md` for architecture/contracts, then `IMPLEMENTATION_PHASES.md` for phase order. Treat this `TASK.md` as the live progress ledger: before starting work, find the first unchecked phase item; after each completed task, immediately change its checkbox to `[x]`. Resume at Phase 4 Vector Search by implementing Qdrant client, embeddings, search indexing/searching/reranking, wiring search into indexing and CLI/API, then run the Phase 4 gate checks. Current verification baseline: `uv run pytest tests/unit/test_phase0_smoke.py tests/unit/test_parser_python.py tests/integration/test_graph_builder.py` and `uv run ruff check cli server core tests/unit/test_parser_python.py tests/integration/test_graph_builder.py` passed.

## Phase 4 - Vector Search
- [x] Add Qdrant client
- [x] Add embedding pipeline
- [x] Add search indexer
- [x] Add hybrid searcher
- [x] Add reranker
- [x] Wire embeddings into index pipeline
- [x] Add search CLI command
- [x] Add search API router
- [x] Run Phase 4 gate checks

## Phase 5 - Analysis Engines
- [x] Add analysis base class
- [x] Add dead code detector
- [x] Add coupling analyser
- [x] Add risk scorer
- [x] Add git ingestor
- [x] Add onboard engine
- [x] Add architecture generator
- [x] Add analysis API routes
- [x] Wire remaining CLI commands
- [x] Run Phase 5 gate checks

## Phase 6 - LLM Explanation Layer
- [x] Add LLM models
- [x] Add LiteLLM client
- [x] Add context assembler
- [x] Add prompt templates
- [x] Add explain command
- [x] Add explain API router
- [x] Wire trace explain flag
- [x] Run Phase 6 gate checks

## Phase 7 - Incremental Indexing, Caching, Error Handling
- [x] Add SQLAlchemy database setup
- [x] Add storage ORM models
- [x] Add Alembic migrations
- [x] Add Redis cache wrapper
- [x] Add full index pipeline
- [x] Add incremental indexer
- [x] Add background worker
- [x] Wire watch mode
- [x] Add graceful degradation paths
- [x] Run Phase 7 gate checks

## Phase 8 - VS Code Extension
- [x] Add extension package config
- [x] Add extension activation
- [x] Add API client
- [x] Add server manager
- [x] Add file save watcher
- [x] Add providers
- [x] Add webview panels
- [x] Add D3 webview assets
- [x] Run Phase 8 gate checks

## Phase 9 - Additional Language Parsers
- [x] Add TypeScript parser
- [x] Add Java parser
- [x] Add Go parser
- [x] Add Rust parser
- [x] Add API route extraction
- [x] Add database model extraction
- [x] Add language fixtures
- [x] Add language parser tests
- [x] Run Phase 9 gate checks

## Final Integration
- [x] Run full quick-start sequence
- [x] Run full pytest suite
- [x] Run ruff check

## Indexing Optimization - Faster Index Without Feature Changes
- [x] Add optimization checkpoint
- [x] Fix incremental traversal and hash comparison
- [x] Add batch graph write helpers
- [x] Add batch search delete/upsert helpers
- [x] Add parallel parsing for index pipeline
- [x] Refactor full index to batch embeddings once per run
- [x] Add indexing progress counters
- [x] Add focused optimization tests
- [x] Run optimization validation

Checkpoint for optimization: This phase must preserve current RIP behavior and commands. Do not add new indexing modes, do not delay embeddings to a background-only path, do not change the default embedding model, and do not remove Neo4j/Qdrant/search/impact behavior. The goal is only to make the existing `repo index`, `repo index --incremental`, and `repo index --watch` paths faster and more visible by skipping unchanged files, parsing safely in parallel, batching Neo4j/Qdrant writes, embedding entities in larger batches with one model instance per run, and reporting progress. Continue using `TASK.md` as the live ledger: mark each checkbox immediately after the code and validation for that item is complete.

## Persistent Service Runtime
- [x] Add persistent FastAPI runtime for shared clients and models
- [x] Add `repo serve` command
- [x] Reuse runtime in search API
- [x] Reuse runtime in index API
- [x] Add runtime health/status endpoint
- [x] Run persistent service validation

Checkpoint for persistent runtime: Keep existing CLI commands and API response shapes intact. Add `repo serve` as the long-running path for agents and local tools so FastAPI can keep Neo4j/Qdrant clients plus embedding/reranker model objects alive across requests. Do not change the default embedding model, search behavior, graph behavior, or index semantics in this phase.

## Continue Prompt - Intelligence Layer Completion
- [x] Fix trace engine for class/function/module symbols
- [x] Extract Python inheritance relationships
- [x] Write complete graph relationships
- [x] Fix explain semantic fallback
- [x] Fix architecture output
- [x] Implement git intelligence metrics
- [x] Align Qdrant version
- [x] Switch default embedding model to smaller dev model
- [x] Build MCP stdio server
- [x] Run continue prompt validation

## UX & Performance Improvements
- [x] Implement real-time index progress display with Rich Live/Progress
- [x] Add ETA calculation to progress display
- [x] Implement repo status command
- [x] Improve watch mode display
- [x] Implement phased index UX (structural first, then semantic)

Checkpoint for continue prompt: The implementation pass has landed the main intelligence-layer repairs from `CONTINUE_PROMPT.md`: multi-strategy trace lookup, Python `EXTENDS` extraction, typed graph relationship writes for `CALLS`, `IMPORTS`, `DEPENDS_ON`, `EXTENDS`, `IMPLEMENTS`, and class-method `CONTAINS`, explain semantic fallback, robust architecture output, corrected metrics/coupling query direction, Qdrant client pinning to `1.10.1`, smaller default embedding model `all-MiniLM-L6-v2`, and a basic MCP stdio server in `mcp/server.py`. `uv sync` completed successfully and `uv run ruff check .` plus focused parser/index/graph tests passed after these changes. The repo-wide validation is NOT complete: the last attempted `uv run repo index .` was intentionally interrupted by the user, so the next agent should resume at `Run continue prompt validation` by running `uv run repo index .` first, then verify `repo trace PythonParser`, `repo trace BaseParser`, `repo architecture`, `repo metrics`, `repo explain "parser"`, `repo impact PythonParser`, `repo search "parser"`, `repo onboard`, MCP `tools/list`, `uv run pytest tests/ -v`, and `uv run ruff check .`. If the model switch recreates the Qdrant collection, re-index before judging search quality.

## Qdrant Integration Debugging
- [x] Trace parser to entities to embeddings to Qdrant upsert
- [x] Trace search flow and confirm it uses Qdrant semantic search plus Neo4j enrichment
- [x] Add debug logs for embeddings generated, Qdrant inserts/deletes, and search backend/result counts
- [x] Fix index CLI success-panel crash that made completed semantic indexing look failed
- [x] Fix git ownership Cypher syntax error surfaced during full index validation

Checkpoint for Qdrant debugging: Live inspection showed `repo_entities` was green but empty before a fresh full index (`points=0`, `indexed_vectors_count=0`, vector size 384). The code path does call Qdrant: `core/indexer/pipeline.py` builds `all_entities`, deletes prior file embeddings, calls `SearchIndexer.index_entities_batched()`, which generates embeddings and calls `QdrantClientWrapper.upsert()`. Search uses `Searcher.hybrid_search()`, which embeds the query, calls Qdrant `query_points()`, and only then enriches Qdrant hits from Neo4j. The contradiction came from stale Neo4j data left by an earlier structural or partial run while the semantic phase had not completed after the model/collection reset; after `uv run repo index .`, Qdrant populated to 318 points. Added logging now exposes empty batches, swallowed Qdrant failures, delete requests, insertion counts, and backend/result counts.

## Architecture Audit and Reliability Review
- [x] Verify search index batching slices real batches instead of duplicating all entities
- [x] Verify incremental hashing stores hashes by relative path
- [x] Diagnose explain fallback and log the real LiteLLM/Ollama failure
- [x] Fix Windows-safe raw-context printing for explain fallback
- [x] Verify search uses Qdrant semantic search before Neo4j enrichment
- [x] Add in-process embedder and reranker model caches for persistent/runtime reuse
- [x] Make Qdrant delete counters report matched points instead of delete request count
- [x] Remove trace and architecture Neo4j warning noise for absent optional schema elements
- [x] Expand MCP tools to include architecture and metrics
- [x] Restore full RIP index after focused search integration test resets Qdrant
- [x] Run architecture audit validation

## RIP LLM Architecture Audit and Multi-Provider Upgrade
- [x] Update Settings model in server/config.py to support multi-provider config
- [x] Update load_toml_settings in server/config.py to load new config fields
- [x] Update default_config_toml in server/config.py to include new config
- [x] Rewrite core/llm/client.py to support multiple providers with fallback
- [x] Run validation checks (ruff, pytest)

Checkpoint for multi-provider upgrade: Updated the LLM architecture to support multiple providers with fallback. The new config includes:
- `primary_provider` and `primary_model`: Main provider to use first
- `fallback_providers`: List of providers to try if the primary fails
- `timeout`, `max_tokens`, `temperature`, `retry_count`, `stream`: Common LLM settings
- Support for Ollama, OpenAI, OpenRouter, Anthropic, Google, Groq, and Azure OpenAI
- Each provider has its own API key and base URL config options
- The query_llm function now tries providers in order, with retries per provider, and falls back to raw context if all fail

Checkpoint for architecture audit: `issues.md` was audited evidence-first. The suspected `index_entities_batched()` and incremental hash bugs were false positives in current code: batching uses `entities[start : start + batch_size]`, and incremental indexing uses `current_hashes[rel_path] = file_hash`. Real issues fixed: explain fallback could crash on Windows when raw context contained non-CP1252 characters; Rich markup could visually hide bracketed code slices; LiteLLM errors were not logged; Qdrant delete counters counted filter requests instead of points; trace and architecture queried missing optional `IMPLEMENTS`/`Interface` schema elements and produced Neo4j warnings; MCP exposed search/trace/impact/explain/onboard but not architecture or metrics. Validation completed with `uv run repo index .`, `uv run repo explain "indexing pipeline"`, `uv run repo trace PythonParser`, `uv run repo architecture`, MCP `tools/list`, `uv run pytest tests/integration/test_search.py -q -rs`, and `uv run ruff check .`. Final Qdrant state after restoring the full RIP index: `points=322`, no duplicate entity ids. Ollama remained unavailable at `http://localhost:11434`, so explain correctly falls back to raw context and logs the connection refusal.

## Search, Trace, and Parsing Improvements (Audit Follow-Up)
- [x] Update all parsers (Python, TypeScript, Java, Go, Rust) to extract module-level ParsedEntity with entity_type="module"
- [x] Update GraphBuilder to map "module" to "Module" label in Neo4j
- [x] Improve trace engine to first try matching any node (by name or fqn) before falling back to function/class-specific strategies
- [x] Fix parallel parsing test failure by sorting parsed files by file path first
- [x] Run full validation suite (all tests passing)

Checkpoint for search/trace/parsing improvements: Addressed several concerns from the architecture audit: module-level entities are now indexed and can be found by search, trace now works for any node type (including modules), and all tests pass after the changes.

## Fix Indexing New Repositories
- [x] Update index pipeline to use build_default_registry() so all language parsers are available
- [x] Fix build_git_data to only process File nodes that are in the current repository
- [x] Fix ASYNC240 linter errors by using anyio.to_thread for pathlib operations in async functions
- [x] Fix line length lint errors
- [x] Update global install and test

Checkpoint for fixing new repo indexing: Fixed two key issues:
1. The indexer was only using PythonParser before, now it uses all registered parsers (Python, TypeScript, Java, Go, Rust)
2. When building git data for a new repo, it was trying to process all File nodes in Neo4j (including from previous repos), now it only processes files in the current repository
Also fixed linter errors and updated the global install!

## Explain Command Multi-Provider CLI and API Enhancements
- [x] Update core/llm/client.py to accept provider/model parameters
- [x] Add --provider and --model flags to repo explain CLI command
- [x] Improve CLI error messages with helpful formatting and tips
- [x] Update core/llm/models.py with provider/model fields for API requests
- [x] Update server/routers/explain.py to accept/forward provider/model parameters
- [x] Run ruff check and validate all changes

Checkpoint for explain command enhancements: Added --provider and --model CLI flags to repo explain, allowing users to switch between LLM providers and models on the fly. Enhanced error messages with beautiful formatting and helpful tips (like API key configuration). Updated the FastAPI /explain endpoint to accept optional provider and model parameters, which are forwarded to core/llm/client.py. All changes pass ruff check.

## Dart Parser Implementation
- [x] Add Dart parser with class/method/function extraction
- [x] Add Dart parser import extraction
- [x] Add Dart parser extends relationships
- [x] Add Dart parser contains relationships
- [x] Test Dart parser on sample Flutter project
- [x] Add Dart to parser registry
- [x] Update core/parser/languages/__init__.py to use lazy imports for optional parsers
- [x] Update core/parser/registry.py to build_default_registry() to handle optional parser failures gracefully
- [x] Replace deprecated tree-sitter-languages with maintained tree-sitter-language-pack
- [x] Update all language parsers to import get_language from tree_sitter_language_pack
- [x] Update pyproject.toml dependencies to use tree-sitter-language-pack
- [x] Fix build_git_data to only process current repo files
- [x] Allow Python 3.13 in pyproject.toml

Checkpoint for Dart parser: Implemented complete Dart parser with tree-sitter using tree-sitter-language-pack, extracted classes, methods, functions, imports, and relationships (CONTAINS, EXTENDS, IMPORTS). Implemented lazy imports and error handling for optional parsers in the registry. Fixed build_git_data to ignore foreign repo files. All validations pass!

## Flutter/Dart Intelligence Priority
- [x] Verify and complete Dart AST extraction for Flutter projects
- [x] Create Function/Class/Widget nodes from Dart source
- [x] Extract Dart IMPORTS and CALLS relationships
- [x] Remove full raw_code from Qdrant payload
- [x] Make repo explain graph-aware instead of raw-code summarization
- [x] Run Flutter/Dart intelligence validation

Checkpoint for Flutter/Dart priority: Completed the Flutter/Dart intelligence pass. `DartParser` now recognizes Flutter widget classes (`StatelessWidget`, `StatefulWidget`, `Widget`) as `entity_type="widget"`, extracts top-level functions, methods, imports, `EXTENDS`, class-method `CONTAINS`, and Dart invocation-based `CALLS` relationships. `GraphBuilder` maps widget entities to `Widget` nodes. Qdrant payloads no longer store full `raw_code`; they store metadata plus `code_preview`, `line_start`, and `line_end`, while search hydrates compact snippets from Neo4j when needed. `repo explain` context assembly is now graph-first: relationships, callers/callees, churn/owners/coupling, and only compact snippets as supporting evidence. Added focused tests for Dart extraction and Qdrant payload shape. Validation passed with `uv run pytest tests/unit/test_parser_dart.py tests/unit/test_search_indexer_payload.py tests/unit/test_parser_python.py tests/unit/test_index_optimization.py -q`, full `uv run pytest tests/ -q` (`13 passed`), and `uv run ruff check .`.
