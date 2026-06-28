# Repository Intelligence Platform (RIP) & Context Gateway - Complete API Documentation

---

## Table of Contents
1. [Project Overview](#project-overview)
2. [RIP Backend API](#rip-backend-api)
   - [Authentication](#authentication)
   - [Endpoints](#rip-endpoints)
3. [Context Gateway API](#context-gateway-api)
   - [Endpoints](#gateway-endpoints)
4. [API Flow & Architecture](#api-flow--architecture)

---

## Project Overview

The RIP system consists of two main components:
1. **RIP Backend**: FastAPI server that handles repository indexing, analysis, search, and graph operations
2. **Context Gateway**: FastAPI server that orchestrates context for coding agents, connecting to RIP and other sources

---

## RIP Backend API

### Base URL
`http://localhost:8000`

### Authentication
Most endpoints require API key authentication via middleware. The health endpoint is public.

---

### RIP Endpoints

#### 1. Health Check (Public)
- **Endpoint**: `GET /health`
- **Authentication**: None
- **Description**: Check if RIP backend is healthy
- **Request**: None
- **Response**:
```json
{
  "status": "ready",
  "neo4j": true,
  "qdrant": true
}
```
- **Working Flow**: Simple status check from server runtime
- **Why Made**: To allow clients to verify backend availability without authentication

---

#### 2. Index Repository
- **Endpoint**: `POST /index`
- **Authentication**: Required
- **Description**: Index a local repository
- **Request Body**:
```json
{
  "repo_path": "/path/to/repo",
  "languages": ["python", "typescript"],
  "incremental": false
}
```
- **Response**:
```json
{
  "success": true,
  "data": {
    "job_id": "uuid",
    "status": "completed",
    "repo_path": "/path/to/repo",
    "indexed_files": 123,
    "total_entities": 456,
    "progress": { ... }
  },
  "error": null,
  "duration_ms": 12345
}
```
- **Working Flow**: Accepts repo path, resolves it, runs full indexing pipeline (parsing, graph building, embeddings), returns summary
- **Why Made**: Core API to make RIP ingest code repositories
- **How Made**: Uses `index_repository_with_resources` from `core/indexer/pipeline.py`, accesses server runtime for Neo4j/Qdrant/embedding clients

---

#### 3. Index Status
- **Endpoint**: `GET /index/status`
- **Authentication**: Required
- **Description**: Get last index operation status
- **Request**: None
- **Response**:
```json
{
  "success": true,
  "data": {
    "status": "not_started",
    "progress": 0.0,
    "entity_count": 0
  },
  "duration_ms": 0
}
```
- **Working Flow**: Returns global `LAST_STATUS` variable
- **Why Made**: For clients to check if indexing is in progress/ready

---

#### 4. Trace Symbol
- **Endpoint**: `GET /trace/{symbol}`
- **Authentication**: Required
- **Query Parameters**:
  - `explain`: boolean (optional, default false)
  - `project_id`: string (optional, for multi-project isolation)
- **Description**: Trace a symbol's flow through the codebase
- **Response**:
```json
{
  "success": true,
  "data": { ... },
  "duration_ms": 123
}
```
- **Working Flow**: Creates Neo4j client, runs `trace_symbol` query from `core/graph/queries/trace.py`
- **Why Made**: To understand symbol usage and dependencies
- **How Made**: Uses `Neo4jClient` to query the graph database

---

#### 5. Impact Analysis
- **Endpoint**: `GET /impact/{symbol}`
- **Authentication**: Required
- **Query Parameters**:
  - `project_id`: string (optional)
- **Description**: Analyze impact of changing a symbol
- **Response**:
```json
{
  "success": true,
  "data": { ... },
  "duration_ms": 123
}
```
- **Working Flow**: Uses `impact_symbol` from `core/graph/queries/impact.py`
- **Why Made**: To understand what parts of codebase would be affected by a change

---

#### 6. Hybrid Search
- **Endpoint**: `GET /search`
- **Authentication**: Required
- **Query Parameters**:
  - `q`: string (required, search query)
  - `top`: int (optional, default 20)
  - `language`: string (optional, filter by language)
  - `service`: string (optional)
  - `entity_type`: string (optional)
  - `project_id`: string (required)
- **Description**: Hybrid semantic + keyword search across indexed entities
- **Response**:
```json
{
  "success": true,
  "data": [
    {
      "entity_id": "id",
      "entity_type": "function",
      "name": "name",
      "file_path": "path",
      "language": "python",
      "score": 0.95,
      "raw_code": "def func(): ...",
      "callers": [],
      "callees": []
    }
  ],
  "duration_ms": 123
}
```
- **Working Flow**: Uses `Searcher.hybrid_search()` from `core/search/searcher.py`, combining Qdrant semantic search, Neo4j graph enrichment, and reranking
- **Why Made**: To find relevant code semantically, not just by keyword
- **How Made**: Uses server runtime's Qdrant, embedder, reranker, and Neo4j clients

---

#### 7. Dead Code Detection
- **Endpoint**: `GET /dead-code`
- **Authentication**: Required
- **Query Parameters**:
  - `type`: string (optional, default "all" | "functions" | "classes")
  - `project_id`: string (optional)
- **Description**: Find unused entities
- **Response**:
```json
{
  "success": true,
  "data": {
    "unused": [ ... ],
    "total_count": 5
  },
  "duration_ms": 123
}
```
- **Working Flow**: Uses `DeadCodeDetector` from `core/analysis/dead_code_detector.py`

---

#### 8. Metrics
- **Endpoint**: `GET /metrics`
- **Authentication**: Required
- **Query Parameters**:
  - `module`: string (optional, specific module/file)
  - `top_risk`: int (optional)
  - `project_id`: string (optional)
- **Description**: Get codebase metrics (coupling, risk, change frequency)
- **Response**:
```json
{
  "success": true,
  "data": {
    "modules": [ ... ]
  },
  "duration_ms": 123
}
```
- **Working Flow**: Combines `CouplingAnalyser` and `RiskScorer` from `core/analysis/`

---

#### 9. Architecture Generation
- **Endpoint**: `GET /architecture`
- **Authentication**: Required
- **Query Parameters**:
  - `format`: string (optional, default "json" | "mermaid")
  - `project_id`: string (optional)
- **Description**: Generate architecture diagram/JSON from codebase
- **Response**:
```json
{
  "success": true,
  "data": { ... },
  "duration_ms": 123
}
```
- **Working Flow**: Uses `ArchitectureGenerator` from `core/analysis/architecture_generator.py`

---

#### 10. Onboarding
- **Endpoint**: `GET /onboard`
- **Authentication**: Required
- **Query Parameters**:
  - `project_id`: string (optional)
- **Description**: Generate onboarding data for new developers
- **Response**:
```json
{
  "success": true,
  "data": { ... },
  "duration_ms": 123
}
```
- **Working Flow**: Uses `OnboardEngine` from `core/analysis/onboard_engine.py`

---

#### 11. Explain (Semantic)
- **Endpoint**: `POST /explain`
- **Authentication**: Required
- **Request Body**:
```json
{
  "symbol": "query text or symbol name",
  "project_id": "uuid",
  "provider": "openai",
  "model": "gpt-4",
  "context_level": "medium"
}
```
- **Response**:
```json
{
  "success": true,
  "data": {
    "explanation": "...",
    "suggested_improvements": [ ... ],
    "intent": "SEMANTIC"
  },
  "duration_ms": 1234
}
```
- **Working Flow**:
  1. Detects user intent (FLOW/ARCHITECTURE/API/STATE/SEMANTIC)
  2. Tries hybrid search first
  3. Falls back to symbol lookup
  4. Assembles context with `ContextAssembler`
  5. Queries LLM with prompt
  6. Parses suggested improvements
- **Why Made**: To get AI-powered explanations of code
- **How Made**: Uses `ContextAssembler`, `Searcher`, and LLM client from `core/llm/`

---

#### 12. Runtime Status
- **Endpoint**: `GET /runtime/status`
- **Authentication**: Required
- **Description**: Get server runtime status
- **Response**:
```json
{
  "success": true,
  "data": { ... },
  "duration_ms": 123
}
```

---

#### 13. Git Operations (Remote Indexing)

##### Start Git Index
- **Endpoint**: `POST /git/index`
- **Authentication**: Required
- **Request Body**:
```json
{
  "git_url": "https://github.com/user/repo.git",
  "project_name": "my-project",
  "branch": "main",
  "keep_clone": false
}
```
- **Response**:
```json
{
  "job_id": "uuid",
  "project_name": "my-project",
  "status": "started",
  "message": "Cloning ... Poll /git/status/{job_id} for progress."
}
```
- **Working Flow**: Uses `CloneService` from `core/git/cloner.py` to start async clone + index
- **Why Made**: To index remote Git repositories without local files

##### Get Job Status
- **Endpoint**: `GET /git/status/{job_id}`
- **Authentication**: Required
- **Response**:
```json
{
  "job_id": "uuid",
  "git_url": "...",
  "project_name": "...",
  "branch": "main",
  "status": "indexing",
  "progress_message": "...",
  "project_id": "uuid",
  "files_indexed": 123,
  "entities_found": 456,
  "error": null
}
```

##### List All Jobs
- **Endpoint**: `GET /git/jobs`
- **Authentication**: Required
- **Response**: List of `JobStatusResponse` objects

---

#### 14. Projects Management

##### List Projects
- **Endpoint**: `GET /projects/`
- **Authentication**: Required
- **Response**:
```json
[
  {
    "project_id": "uuid",
    "project_name": "name",
    "indexed_at": "2024-01-01T00:00:00",
    "files_count": 123,
    "entities_count": 456,
    "languages": ["python"],
    "git_url": "...",
    "branch": "main"
  }
]
```

##### Get Project Details
- **Endpoint**: `GET /projects/{project_id}`
- **Authentication**: Required

##### Delete Project
- **Endpoint**: `DELETE /projects/{project_id}`
- **Authentication**: Required
- **Response**:
```json
{
  "message": "Project ... deleted",
  "project_name": "..."
}
```
- **Working Flow**: Deletes Neo4j nodes, Qdrant vectors, and PostgreSQL metadata

---

#### 15. WebSocket (Real-time Indexing Progress)
- **Endpoint**: `WS /ws/index/{job_id}`
- **Authentication**: None (but job must exist)
- **Description**: Real-time streaming of Git indexing progress
- **Message Format**:
```json
{
  "status": "indexing",
  "message": "...",
  "files_indexed": 123,
  "entities_found": 456,
  "project_id": "uuid",
  "error": null
}
```
- **Working Flow**: Polls job status every 2 seconds and sends updates until job completes/fails

---

## Context Gateway API

### Base URL
`http://localhost:8001` (default, configurable)

---

### Gateway Endpoints

#### 1. Gateway Health
- **Endpoint**: `GET /health` or `GET /health/`
- **Authentication**: None
- **Description**: Check gateway health and source statuses
- **Response**:
```json
{
  "status": "healthy",
  "version": "x.y.z",
  "sources": {
    "rip": {
      "available": true,
      "healthy": true
    },
    "github": { ... }
  }
}
```

---

#### 2. Get Context
- **Endpoint**: `POST /api/context` or `POST /api/context/`
- **Authentication**: None (rate-limited)
- **Description**: Get intelligent context for a coding task
- **Request Body**:
```json
{
  "task": "Implement user authentication",
  "max_tokens": 12000,
  "role": "developer"
}
```
- **Response**:
```json
{
  "session_id": "uuid",
  "intent": "...",
  "domain": "...",
  "context": [
    {
      "source": "rip",
      "query_type": "...",
      "content": "...",
      "metadata": { ... },
      "score": 0.95
    }
  ],
  "tokens_used": 1234,
  "conflicts": [ ... ],
  "warnings": [ ... ]
}
```
- **Working Flow**: Uses `GatewayPipeline` to classify intent, retrieve from sources, rank, compress, and assemble context package
- **Why Made**: To provide coding agents with relevant, curated context
- **How Made**: Uses core components (classifier, planner, ranker, sources, memory) from `gateway/core/`

---

#### 3. Validate Change
- **Endpoint**: `POST /api/validate` or `POST /api/validate/`
- **Authentication**: None (rate-limited)
- **Description**: Validate a code change using RIP's impact analysis
- **Request Body**:
```json
{
  "diff": "diff --git ...",
  "files": ["file1.py", "file2.py"]
}
```
- **Response**:
```json
{
  "risk_level": "medium",
  "affected_files": [ ... ],
  "impact_summary": "...",
  "warnings": [],
  "error": null
}
```
- **Working Flow**: Uses `RIPSource` to query RIP's impact analysis

---

#### 4. Sessions
- **Endpoint**: `GET /api/sessions` or `GET /api/sessions/`
- **Authentication**: None (rate-limited)
- **Description**: List all active sessions

- **Endpoint**: `GET /api/sessions/{session_id}`
- **Authentication**: None (rate-limited)
- **Description**: Get details of a specific session

---

#### 5. Sources
- **Endpoint**: `GET /api/sources` or `GET /api/sources/`
- **Authentication**: None (rate-limited)
- **Description**: List all available sources

- **Endpoint**: `POST /api/sources/{source_name}/enable`
- **Authentication**: None (rate-limited)
- **Description**: Enable a source

- **Endpoint**: `POST /api/sources/{source_name}/disable`
- **Authentication**: None (rate-limited)
- **Description**: Disable a source

---

#### 6. Metrics
- **Endpoint**: `GET /api/metrics` or `GET /api/metrics/`
- **Authentication**: None (rate-limited)
- **Description**: Get gateway usage metrics
- **Response**:
```json
{
  "sessions": 0,
  "active_sessions": 0,
  "tokens_retrieved": 0,
  "tokens_delivered": 0
}
```

---

## API Flow & Architecture

### RIP Backend Flow
```
Client Request
    ↓
FastAPI Middleware (auth, error wrapping, logging)
    ↓
Router Handler
    ↓
Core Services (indexer, graph queries, search, analysis, LLM)
    ↓
Databases (Neo4j - graph, Qdrant - vectors, PostgreSQL - metadata, Redis - cache)
    ↓
ApiEnvelope Wrapped Response
```

### Context Gateway Flow
```
Agent Request (get_context)
    ↓
FastAPI Middleware (CORS, rate limit)
    ↓
GatewayPipeline
    ├─ Classifier → Intent/Domain detection
    ├─ Planner → Source selection & queries
    ├─ Sources (RIP, GitHub, Jira, Slack) → Data retrieval
    ├─ Ranker → Score & sort context items
    ├─ Compressor → Token optimization
    └─ Memory → Conflict detection & session tracking
    ↓
ContextPackage Response
```

### Connections Between Services
- Context Gateway → RIP Backend: via `RIPSource` in `gateway/core/sources/rip_client.py`
- RIP Backend → Neo4j: `core/graph/client.py`
- RIP Backend → Qdrant: `core/search/client.py`
- RIP Backend → PostgreSQL: `core/storage/database.py`
- RIP Backend → Redis: `core/storage/cache.py`

