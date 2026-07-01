# Architecture

See `REPO_INTELLIGENCE_PLATFORM.md` for the full architecture.

## Runtime Layer

RIP now resolves execution through `core/runtime`.

- `StorageResolver` supports `auto`, `server`, and `local`.
- `RuntimeEnvironment` holds the active graph, vector, and metadata providers.
- `Capability` values describe features such as graph traversal, vector search, REST API, WebSockets, remote indexing, and Flutter support.

Server mode wraps the existing implementation with `Neo4jProvider`, `QdrantProvider`, and `PostgresProvider`. Local mode uses `NetworkXProvider`, `LocalVectorProvider`, and `SQLiteProvider` under `.repo-intel/local/`.

`core/engine/orchestrator.py` remains thin and delegates to service modules in `core/services/`. The existing graph/search/storage code remains the server-mode foundation; local mode is additive and non-breaking.

REST API, Flutter, Context Gateway, WebSockets, and remote Git indexing are server-mode capabilities. CLI, MCP, and VS Code subprocess workflows can run against local mode.
