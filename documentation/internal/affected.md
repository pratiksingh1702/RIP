# RIP Platform Changes & Affected Components

This document outlines which parts of the RIP platform are affected by the new dual-mode (server + local) distribution plan, and how the flow works end-to-end.

---

## 🏗️ Architecture Overview: Two Modes

RIP now operates in two modes:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Server Mode** | Full-stack with Neo4j, Qdrant, PostgreSQL, Redis, FastAPI, Gateway, Flutter, MCP, and VS Code extension | Teams, shared indexes, Flutter app, Context Gateway |
| **Local Mode** | Zero Docker, zero server configuration: CLI, MCP, and VS Code subprocess workflows with local providers | Individual developers, quick repository analysis without dependencies |

---

## 📦 Affected Components

### 1. Core Layer (`core/`)

#### New Files/Directories Added:
- `core/runtime/`: Runtime environment, capabilities, resolver, and doctor command
- `core/engine/`: Orchestrator and intent handling
- `core/services/`: Domain services for search, explain, trace, impact, etc.
- `core/storage/interfaces/`: Storage interface contracts (GraphStore, VectorStore, MetadataStore)
- `core/storage/providers/`: Pluggable provider implementations
- `core/storage/registry.py`: Provider registry

#### Modified Files:
- Existing `core/graph/`, `core/search/`, `core/storage/database.py` remain unchanged but are wrapped by providers
- `core/indexer/pipeline.py`: Will be updated to support provider-aware indexing

### 2. CLI Layer (`cli/`)

#### New Commands:
- `repo doctor`: Diagnose runtime environment, providers, and capabilities
- `repo --mode auto|server|local`: New global flag for explicit mode selection

#### Updated Commands:
- `repo index`: Now supports `--mode` flag, routes to active providers
- `repo search`, `repo explain`, `repo trace`, `repo impact`, `repo architecture`, `repo metrics`, `repo onboard`, `repo dependencies`, `repo dead-code`: Route through engine and services
- `repo serve`: Now requires server-mode capabilities, fails gracefully if local-only
- `repo delete`: Now supports deleting from local stores as well

### 3. Server Layer (`server/`)

#### Updated Endpoints:
- `/health`: Now includes active capabilities and provider info
- Existing index, search, trace, impact, explain, etc. endpoints: Now use the runtime environment

### 4. MCP Server (`mcp/`)

- Now uses the same runtime resolver and services as the CLI
- Supports local mode where MCP imports core modules directly

### 5. VS Code Extension (`vscode-extension/`)

- Subprocess/CLI actions work in local mode
- API-backed features show server-mode guidance if REST capability is missing

### 6. Flutter App (`rip_app/`)

- **Requires server mode**
- Now displays a server-mode requirement message when connected to a local-only runtime or when `/health` reports missing server capabilities

### 7. Context Gateway (`gateway/`)

- **Requires server mode plus Redis**
- Remains server-mode only; keep root runtime launchers using existing root `.venv` and `gateway/.venv`

---

## 🔄 End-to-End Flow

### Server Mode Flow:
1. User runs `docker compose up -d` to start Neo4j, Qdrant, PostgreSQL, Redis
2. User runs `repo init . --project-name my-project` (or uses existing project)
3. User runs `repo index .` (auto mode selects server providers if healthy)
4. Indexing uses `Neo4jProvider`, `QdrantProvider`, `PostgresProvider`
5. User can then use:
   - CLI commands (`repo search`, `repo explain`, etc.)
   - Flutter mobile app (connects to REST API)
   - MCP server (for AI agents)
   - VS Code extension (API or CLI mode)
   - Context Gateway (for advanced agent orchestration)

### Local Mode Flow:
1. User runs `repo init . --project-name my-project`
2. User runs `repo index . --mode local` (no Docker required!)
3. Indexing uses `NetworkXProvider`, `LocalVectorProvider`, `SQLiteProvider`
4. Data stored locally under `.repo-intel/local/`
5. User can use:
   - CLI commands (`repo search`, `repo explain --no-llm`, `repo trace`, etc.)
   - MCP server (in local mode)
   - VS Code extension (subprocess/CLI mode)
6. Flutter app and Context Gateway are not available in local mode

### Auto Mode Flow (Default):
1. User runs `repo index .`
2. Runtime resolver probes Neo4j, Qdrant, PostgreSQL
3. If server services are healthy → uses server mode
4. If server services are unavailable → falls back to local mode
5. Clear CLI output shows which providers are active

---

## ✨ Key Capabilities by Provider

| Capability | Server Providers | Local Providers |
|------------|------------------|-----------------|
| GRAPH_TRAVERSAL | ✅ Neo4j | ✅ NetworkX |
| VECTOR_SEARCH | ✅ Qdrant | ✅ Local Vector (FAISS/NumPy fallback) |
| METADATA_STORAGE | ✅ PostgreSQL | ✅ SQLite |
| PERSISTENT_STORAGE | ✅ Yes | ✅ Yes (local files) |
| MULTI_PROJECT | ✅ Yes | ✅ Yes |
| INCREMENTAL_INDEX | ✅ Yes | ✅ Yes |
| REST_API | ✅ Yes | ❌ No |
| WEBSOCKET | ✅ Yes | ❌ No |
| CONCURRENT_USERS | ✅ Yes | ❌ No |
| SHARED_INDEXES | ✅ Yes | ❌ No |
| CONTEXT_GATEWAY | ✅ Yes | ❌ No |
| REMOTE_INDEXING | ✅ Yes | ❌ No |
| FLUTTER_CLIENT | ✅ Yes | ❌ No |

---

## 🛡️ Non-Breaking Guarantees

1. ✅ No existing CLI command is removed or renamed
2. ✅ Server mode remains the source of truth for REST API, Flutter, Gateway, shared indexes, concurrent users, and remote Git indexing
3. ✅ Existing graph/search/storage implementation remains available through providers
4. ✅ New local mode is additive
5. ✅ Runtime probing does not write data
6. ✅ Local mode failures must be actionable messages, not stack traces

---

## 📁 New Local Storage Structure

Local mode stores data under `.repo-intel/local/`:
- `rip.sqlite3`: SQLite metadata store (projects, file hashes, index state, embedding cache)
- `graph.pickle` (optional): Persisted NetworkX graph
- `vectors/` (optional): Local vector index files

---

## 🚀 Next Steps

See `setup.md` for step-by-step setup instructions for both server and local modes!
