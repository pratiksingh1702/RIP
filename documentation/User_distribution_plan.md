# RIP User Distribution Plan

## Purpose

This plan combines the non-breaking migration plan, the review-adjusted final architecture, and the local-mode deployment brief into one implementation roadmap for this repository.

The goal is to make RIP usable in two user distribution modes without breaking the current full-stack product:

- Server mode: current Neo4j, Qdrant, PostgreSQL, Redis, FastAPI, Gateway, Flutter, MCP, and VS Code stack.
- Local mode: zero Docker and zero server configuration for CLI, MCP, and VS Code subprocess workflows, using in-process/local providers.

The migration must preserve the existing user surface. Commands such as `repo index .`, `repo search`, `repo explain`, `repo trace`, `repo impact`, `repo architecture`, `repo metrics`, `repo onboard`, `repo serve`, and MCP tools must keep their current names and response intent.

## Current Codebase Fit

The current checkout is server-first:

- `cli/main.py` exposes the stable Typer command surface.
- `cli/commands/index.py` still connects directly to `Neo4jClient` before running `IndexPipeline`.
- `core/indexer/pipeline.py` parses source files, writes graph data through `GraphBuilder`, and writes semantic vectors through `SearchIndexer` and `QdrantClientWrapper`.
- `core/graph/` contains the current Neo4j client, schema, graph builder, and Cypher query modules.
- `core/search/` contains Qdrant client, embedding pipeline, search indexing, hybrid search, and reranking.
- `core/storage/` already exists for PostgreSQL database setup, ORM models, Alembic migrations, Redis cache wrapper, and project metadata. New storage abstractions must live under this existing package without replacing its current role.
- `server/runtime.py` owns long-lived server resources for `repo serve`, but it currently assumes Neo4j and Qdrant.
- `server/routers/` and `cli/commands/` directly call current graph/search/analysis code paths.
- `mcp/server.py`, `vscode-extension/`, and `rip_app/` already exist as distribution surfaces. Flutter requires REST API/server mode; CLI, MCP, and VS Code subprocess workflows can support local mode first.
- `pyproject.toml` currently includes `numpy`, `scipy`, SQLAlchemy, Neo4j, Qdrant, Redis, and ML dependencies, but it does not yet declare `networkx` or `faiss-cpu`.

The safest migration is additive: introduce runtime/provider interfaces beside the existing implementation, wrap current clients as providers, then gradually route CLI and server entry points through the runtime environment.

## Architecture Decision

Use the review-adjusted naming:

- Use `core/runtime/`, not `core/distribution/`.
- Use `Capability` sets, not one-off feature-gate methods.
- Use `core/engine/` as a thin orchestrator that delegates to domain services.
- Use `core/services/` for business workflows such as search, explain, trace, impact, architecture, metrics, onboard, dependencies, and dead-code.
- Use `core/storage/interfaces/` plus `core/storage/providers/` and `core/storage/registry.py` for storage abstraction.

Target structure:

```text
core/
  runtime/
    __init__.py
    capabilities.py
    environment.py
    resolver.py
    doctor.py
  engine/
    __init__.py
    orchestrator.py
    intent.py
  services/
    __init__.py
    search_service.py
    explain_service.py
    trace_service.py
    impact_service.py
    architecture_service.py
    metrics_service.py
    onboard_service.py
    dependencies_service.py
    dead_code_service.py
  storage/
    interfaces/
      __init__.py
      graph_store.py
      vector_store.py
      metadata_store.py
    providers/
      __init__.py
      neo4j_provider.py
      networkx_provider.py
      qdrant_provider.py
      local_vector_provider.py
      postgres_provider.py
      sqlite_provider.py
    registry.py
```

Existing packages stay in place:

- `core/graph/` remains the current Neo4j implementation.
- `core/search/` remains the current Qdrant, embedding, search, and reranker implementation.
- `core/storage/database.py`, `core/storage/models/`, and migrations remain the PostgreSQL metadata implementation.
- `core/indexer/` remains the parser/indexing pipeline until provider-aware indexing is added.
- `server/`, `cli/`, `mcp/`, `gateway/`, `vscode-extension/`, and `rip_app/` keep their public entry points.

## Capabilities

Capabilities describe what the active runtime can do. They should be computed from active providers and used consistently by CLI, server, MCP, Gateway, VS Code, and Flutter-facing checks.

Initial capability enum:

```text
GRAPH_TRAVERSAL
VECTOR_SEARCH
METADATA_STORAGE
PERSISTENT_STORAGE
MULTI_PROJECT
INCREMENTAL_INDEX
REST_API
WEBSOCKET
CONCURRENT_USERS
SHARED_INDEXES
CONTEXT_GATEWAY
REMOTE_INDEXING
FLUTTER_CLIENT
```

Recommended provider capabilities:

| Provider | Capabilities |
| --- | --- |
| Neo4jProvider | GRAPH_TRAVERSAL, PERSISTENT_STORAGE, MULTI_PROJECT, CONCURRENT_USERS, SHARED_INDEXES |
| NetworkXProvider | GRAPH_TRAVERSAL |
| QdrantProvider | VECTOR_SEARCH, PERSISTENT_STORAGE, MULTI_PROJECT |
| LocalVectorProvider | VECTOR_SEARCH, optional PERSISTENT_STORAGE when disk index is enabled |
| PostgresProvider | METADATA_STORAGE, PERSISTENT_STORAGE, MULTI_PROJECT, INCREMENTAL_INDEX, CONCURRENT_USERS |
| SQLiteProvider | METADATA_STORAGE, PERSISTENT_STORAGE, INCREMENTAL_INDEX |
| Server runtime bundle | REST_API, WEBSOCKET, FLUTTER_CLIENT when server-grade graph/vector/metadata providers are active |
| Gateway runtime bundle | CONTEXT_GATEWAY when REST_API, Redis, and Gateway dependencies are active |
| Remote Git bundle | REMOTE_INDEXING when REST_API and persistent metadata are active |

Local mode should not pretend to support Flutter or Gateway. It should provide a clear message that those require server mode.

## Runtime Resolution

`core/runtime/resolver.py` should resolve an explicit or automatic mode:

- `auto`: prefer server providers when healthy; fall back to local providers per storage category.
- `server`: require server providers and fail with clear diagnostics if Neo4j, Qdrant, or PostgreSQL are unavailable.
- `local`: use local providers even if Docker services are running.

The CLI should add `--mode auto|server|local` where it is useful, with `auto` as the default. The first integration target is `repo index`; query commands can follow once provider-backed services exist.

Resolution should be fast and non-destructive:

- Probe Neo4j on configured URI/port.
- Probe Qdrant on configured host/port.
- Probe PostgreSQL through SQLAlchemy connection or the current storage helper.
- Avoid migrations or data writes during probing.
- Keep probe timeouts short and report what was selected.

`repo doctor` should print:

- Python version and root environment location.
- Whether the current command is running inside the root `.venv`.
- Detected graph, vector, and metadata providers.
- Active capabilities.
- Missing capabilities and exact upgrade path, such as `docker compose up -d` for server mode.
- Local index paths under `.repo-intel/`.

## Storage Interfaces

The interfaces should expose domain methods, not backend-specific query languages.

`GraphStore` should cover:

- `setup_schema`
- `batch_upsert_files`
- `batch_upsert_entities`
- `batch_upsert_relationships`
- `trace_callers`
- `trace_callees`
- `trace_workflow`
- `find_dependencies`
- `find_dependents`
- `find_imports`
- `find_imported_by`
- `get_architecture`
- `get_modules`
- `get_entry_points`
- `analyze_impact`
- `find_unused`
- `delete_project`

`VectorStore` should cover:

- `init`
- `upsert_entities`
- `delete_file_embeddings`
- `delete_project`
- `search_similar`
- `count`
- `close`

`MetadataStore` should cover:

- `ensure_schema`
- `save_project`
- `get_project`
- `list_projects`
- `resolve_project`
- `save_file_hash`
- `get_file_hash`
- `delete_project`
- embedding cache read/write methods if the cache remains metadata-backed.

Provider wrappers should translate these domain methods to current clients first. The existing clients should not be rewritten during the first phases.

## Local Mode Provider Notes

Graph:

- Use NetworkX `MultiDiGraph` or `DiGraph` depending on whether duplicate typed edges need to be preserved.
- Store parsed entities as nodes keyed by `project_id:fqn`.
- Store relationships as typed edges with file path, line, and project metadata.
- Persist graph data only after the in-memory version is stable; first implementation can rebuild graph on each `repo index`.

Vector:

- Prefer a local vector provider abstraction rather than hard-coding FAISS throughout the app.
- If `faiss-cpu` is available and works on the target platform, use it.
- Provide a NumPy or SciPy cosine-similarity fallback so Windows installs are not blocked by FAISS packaging.
- Store vectors and payloads under `.repo-intel/local/` once disk persistence is added.

Metadata:

- Use SQLite through SQLAlchemy under `.repo-intel/local/rip.sqlite3`.
- Reuse compatible ORM models where practical, but do not force PostgreSQL-only migrations into SQLite if they create complexity.
- Preserve project isolation using `project_id`.

## Command Behavior

`repo index .`:

- Default stays `auto`.
- In server mode, the current Neo4j/Qdrant/PostgreSQL indexing path should behave as it does today.
- In local mode, parsing should remain shared, then graph/vector/metadata writes should target local providers.
- Output should say which runtime is active.

`repo search`, `repo explain`, `repo trace`, `repo impact`, `repo architecture`, `repo metrics`, `repo onboard`, `repo dependencies`, `repo dead-code`:

- Route through `ContextEngine` and service classes after provider implementations are ready.
- Preserve current flags and output shape.
- Prefer graph/vector results from the active runtime.

`repo serve`:

- Should require server-mode capabilities.
- If local mode is active, return a clear message instead of attempting to start a server runtime that assumes Neo4j/Qdrant.

`repo doctor`:

- New command.
- Should be safe to run anywhere and should not require Docker.

MCP:

- Should use the same runtime resolver and services as the CLI.
- Local mode should be supported where MCP imports core modules directly.

VS Code:

- Subprocess/CLI actions can work in local mode.
- API-backed features should show server-mode guidance if REST is unavailable.

Flutter:

- Requires REST API/server mode.
- Should display a server-mode requirement message when connected to a local-only runtime or when `/health` reports missing server capabilities.

Gateway:

- Requires server mode plus Redis.
- Keep root runtime launchers using the existing root `.venv` and `gateway/.venv`. Do not move Gateway into local mode.

## Root Environment Rule

Use the existing RIP root `uv` environment and root `.venv`.

Implementation and validation commands should prefer:

```powershell
uv run pytest ...
uv run ruff check ...
uv run python -m py_compile ...
```

Runtime launchers should continue to use:

```text
.venv\Scripts\repo.exe
gateway\.venv\Scripts\gateway.exe
```

Do not add implementation steps that reinstall all packages, run broad bootstrap scripts, or repurpose `start_rip.ps1` / `start_rip.sh` unless the user explicitly asks for setup/bootstrap work. Add dependencies only when a phase actually needs them, and validate with the existing root environment.

## Migration Phases

### Phase 0: Baseline Audit and Safety Rails

Deliverables:

- Confirm current server-mode behavior and command surfaces.
- Record current direct dependencies on `Neo4jClient`, `QdrantClientWrapper`, `async_session_factory`, and `ServerRuntime`.
- Confirm which commands must remain server-only.
- Add no runtime behavior changes.

Validation:

- `uv run python -m py_compile cli\main.py cli\commands\index.py core\indexer\pipeline.py server\runtime.py`
- `uv run pytest tests\unit\test_runtime_router.py -q`
- `git diff --check`

### Phase 1: Capabilities, Interfaces, and Registry

Deliverables:

- Add `core/runtime/capabilities.py`.
- Add `core/storage/interfaces/`.
- Add `core/storage/registry.py`.
- Define provider base classes and capability reporting.
- Add focused unit tests for capability composition and provider selection order.

Validation:

- `uv run pytest tests\unit\test_runtime_capabilities.py tests\unit\test_storage_registry.py -q`
- `uv run ruff check core\runtime core\storage tests\unit\test_runtime_capabilities.py tests\unit\test_storage_registry.py`

### Phase 2: Server Providers Wrapping Existing Code

Deliverables:

- Add `Neo4jProvider`, `QdrantProvider`, and `PostgresProvider`.
- Keep existing `core/graph`, `core/search`, and `core/storage/database.py` unchanged except for clearly required helper exposure.
- Prove wrappers can call current clients and preserve project isolation.
- Do not route CLI through providers yet.

Validation:

- Focused provider unit tests with fakes/mocks.
- Existing graph/search tests still pass.
- `uv run python -m py_compile core\storage\providers\neo4j_provider.py core\storage\providers\qdrant_provider.py core\storage\providers\postgres_provider.py`

### Phase 3: Local Providers

Deliverables:

- Add `NetworkXProvider`.
- Add local vector provider with FAISS when available and NumPy/SciPy fallback when not.
- Add `SQLiteProvider`.
- Add `.repo-intel/local/` path helpers.
- Decide and document whether local graph/vector persistence lands now or in a follow-up phase.
- Add `networkx` and any chosen local vector dependency to `pyproject.toml` only when implementation begins.

Validation:

- Unit tests for graph traversal, dependency lookup, impact, architecture, vector search, project isolation, file hashes, and delete.
- Tests must not require Docker.

### Phase 4: Runtime Environment, Resolver, and Doctor

Deliverables:

- Add `RuntimeEnvironment`.
- Add `StorageResolver` with `auto`, `server`, and `local`.
- Add `repo doctor`.
- Make runtime status include provider names and capabilities.
- Keep existing `server/routers/runtime.py` health behavior compatible while adding capability details.

Validation:

- Tests for explicit local mode, explicit server mode failure, auto fallback, and doctor output.
- `uv run repo doctor` from the root `.venv`.

### Phase 5: Provider-Aware Indexing

Deliverables:

- Add a provider-aware indexing path that reuses parser discovery and parsing logic from `core/indexer/pipeline.py`.
- Preserve the existing server indexing path until parity is proven.
- Add `--mode auto|server|local` to `repo index`.
- Ensure `repo index .` in auto mode still works with Docker running.
- Ensure `repo index . --mode local` works without Neo4j, Qdrant, PostgreSQL, or Redis.

Validation:

- Local-mode index fixture test.
- Server-mode smoke test when Docker services are available.
- CLI output confirms active providers.

### Phase 6: Engine and Domain Services

Deliverables:

- Add `core/engine/orchestrator.py`.
- Add service classes for search, explain, trace, impact, architecture, metrics, onboard, dependencies, and dead-code.
- Start by wrapping current query modules and analysis engines rather than rewriting logic.
- Route one low-risk command first, then expand.

Validation:

- Existing CLI/API parity tests remain green.
- Add service tests using fake stores.

### Phase 7: CLI and MCP Runtime Routing

Deliverables:

- Route CLI query commands through the runtime environment and services.
- Route MCP tools through the same runtime environment and services.
- Preserve current flags and output.
- Ensure local mode supports CLI and MCP queries after local index.

Validation:

- `repo search`, `repo explain --no-llm`, `repo trace`, `repo architecture`, and MCP `tools/list` smoke checks.
- Docker-free local-mode tests for query commands where possible.

### Phase 8: Server, Flutter, VS Code, and Gateway Capability Handling

Deliverables:

- Update `repo serve` and `ServerRuntime` to require server capabilities and fail gracefully when local-only.
- Add server health capability details.
- Make Flutter and VS Code API-backed paths display server-mode requirements when REST capability is missing.
- Keep Gateway server-mode only.

Validation:

- `repo serve --mode local` or equivalent graceful-failure test.
- Health endpoint test including capabilities.
- Flutter/VS Code source-level checks for server-mode messaging.

### Phase 9: Persistence, Migration, and Switching Polish

Deliverables:

- Persist local SQLite metadata and optional local vector index.
- Add rebuild/switch guidance for moving between local and server backends.
- Add `repo delete` support for local stores.
- Add docs for `.repo-intel/local/` artifacts.

Validation:

- Index, restart process, query persisted local metadata/vector state.
- Delete local project and re-index.

### Phase 10: Documentation and Release Hardening

Deliverables:

- Update `README.md`, `cli.md`, `docs/architecture.md`, and Gateway/Flutter notes where relevant.
- Add troubleshooting section for local mode, server mode, and `repo doctor`.
- Run focused test suite and static checks.
- Confirm no current commands were renamed or removed.

Validation:

- `uv run pytest tests\unit -q`
- `uv run ruff check .`
- Manual smoke checklist for local mode and server mode.

## Non-Breaking Guarantees

- No existing CLI command is removed or renamed.
- Server mode remains the source of truth for REST API, Flutter, Gateway, shared indexes, concurrent users, and remote Git indexing.
- Existing graph/search/storage implementation remains available through providers.
- New local mode is additive.
- Runtime probing does not write data.
- Local mode failures must be actionable messages, not stack traces.
- Tasks should be tracked in `TASK.md` as phases are implemented.

## Implementation Risks

- FAISS packaging on Windows may be fragile. Keep a NumPy/SciPy fallback behind the `VectorStore` interface.
- NetworkX graph behavior must match enough Neo4j query semantics to preserve command expectations.
- Current command modules call backend clients directly. Routing should be phased command by command to avoid broad regressions.
- `core/storage/` already contains PostgreSQL code. New interfaces and providers must be named clearly to avoid confusing ORM storage with pluggable storage.
- Server runtime currently instantiates Neo4j, Qdrant, embedder, and reranker eagerly. Capability checks should happen before creating server-only resources in local-only mode.
- Local mode project isolation must be explicit from day one.

## Definition of Done

The migration is complete when:

- `repo index . --mode local` works without Docker.
- `repo search`, `repo explain --no-llm`, `repo trace`, `repo impact`, `repo architecture`, `repo metrics`, `repo dependencies`, `repo dead-code`, and `repo onboard` can read a local-mode index where their required capabilities exist.
- `repo index . --mode server` preserves the existing full-stack behavior.
- `repo index .` auto-selects a healthy server stack and falls back to local mode when server services are unavailable.
- `repo doctor` accurately reports selected providers, active capabilities, and upgrade guidance.
- `repo serve`, Flutter, Gateway, and remote Git indexing clearly require server mode instead of failing obscurely.
- Tests cover provider selection, capabilities, local graph/vector/metadata behavior, and at least one end-to-end local indexing/query path.
