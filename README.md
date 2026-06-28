# Repository Intelligence Platform

Repository Intelligence Platform (RIP) turns software repositories into structured knowledge graphs, semantic indexes, and agent-ready context packages.

RIP is infrastructure for repository understanding. It parses source code with Tree-sitter, writes architectural relationships into Neo4j, indexes compact semantic payloads in Qdrant, and exposes the result through a CLI, FastAPI service, MCP servers, a Context Gateway, and a VS Code extension.

It is not a chatbot over files. The LLM, when used, is the final explanation step after static analysis, graph traversal, retrieval, reranking, and context assembly have already reduced the repository to grounded evidence.

## Problem Statement

Large repositories are hard to reason about because the important facts are not stored in one place.

Source files contain symbols and local control flow. Imports describe partial dependencies. Git history hints at ownership and coupling. API routes and database models define runtime boundaries. Documentation is often stale. Keyword search can find strings, but it cannot reliably answer what calls a function, what depends on a file, which flow crosses module boundaries, or what context an AI coding agent should see before changing code.

AI agents make this sharper. A useful agent needs the same context a senior engineer would collect manually: entry points, dependent files, ownership, architectural risk, related snippets, and the change surface. Dumping files into a context window does not scale. Embeddings alone miss exact structural relationships. Graph traversal alone misses natural-language intent and fuzzy discovery.

RIP exists to make repository context queryable, composable, and precise.

## How RIP Works

RIP builds two complementary indexes:

- A structural knowledge graph in Neo4j: projects, files, modules, classes, functions, widgets, calls, imports, containment, inheritance, ownership, and dependency edges.
- A semantic index in Qdrant: compact code/entity payloads embedded for natural-language discovery and reranked before context assembly.

Those indexes are tied together by deterministic project isolation, PostgreSQL metadata, file hashes, incremental indexing, and graph-aware retrieval.

```mermaid
flowchart TD
    repo["Repository on disk"] --> traversal["Traversal and git-aware file discovery"]
    traversal --> parser["Tree-sitter parsers"]
    parser --> ast["Language ASTs"]
    ast --> entities["Entity extraction"]
    ast --> rels["Relationship extraction"]
    entities --> kg["Neo4j knowledge graph"]
    rels --> kg
    entities --> payloads["Compact semantic payloads"]
    payloads --> embeddings["Sentence Transformers / ONNX embeddings"]
    embeddings --> qdrant["Qdrant vector index"]
    repo --> metadata["PostgreSQL metadata and file hashes"]
    kg --> retrieval["Hybrid retrieval"]
    qdrant --> retrieval
    metadata --> retrieval
    retrieval --> rerank["Cross-encoder reranking"]
    rerank --> context["Context assembly"]
    context --> interfaces["CLI / FastAPI / MCP / VS Code / Gateway"]
    context --> llm["Optional LLM explanation"]
```

## System Architecture

```mermaid
flowchart LR
    subgraph Interfaces
        cli["Typer CLI\nrepo index/search/trace/impact/explain"]
        api["FastAPI service\nrepo serve"]
        mcp["RIP MCP server"]
        vscode["VS Code extension"]
        gateway["Context Gateway\nMCP + HTTP + CLI"]
    end

    subgraph Core
        parser["Parser registry\nPython / TypeScript / Java / Go / Rust / Dart"]
        indexer["Index pipeline\nfull / incremental / smart / watch"]
        graphq["Graph queries\ntrace / impact / dependencies / architecture"]
        search["Hybrid search\nvector + lexical + graph expansion"]
        analysis["Analysis engines\ndead code / coupling / risk / onboard"]
        explain["Explain engine\ncontext assembler + LiteLLM"]
    end

    subgraph Storage
        neo4j["Neo4j\nknowledge graph"]
        qdrant["Qdrant\nvectors"]
        postgres["PostgreSQL\nprojects, file hashes, jobs, gateway state"]
        redis["Redis\ncache and gateway state"]
    end

    cli --> Core
    api --> Core
    mcp --> Core
    vscode --> cli
    vscode --> api
    gateway --> mcp
    gateway --> api

    parser --> indexer
    indexer --> neo4j
    indexer --> qdrant
    indexer --> postgres
    graphq --> neo4j
    search --> qdrant
    search --> neo4j
    analysis --> neo4j
    analysis --> postgres
    explain --> search
    explain --> graphq
    gateway --> redis
    gateway --> postgres
```

## End-to-End Pipeline

1. `repo init` creates project metadata in `.repo-intel/config.toml`.
2. `repo index` discovers source files, parses supported languages, and extracts entities and relationships.
3. Neo4j receives the structural graph: files, modules, symbols, calls, imports, dependencies, containment, inheritance, and ownership.
4. Qdrant receives embedded, compact payloads with project filters and code previews rather than full raw file dumps.
5. PostgreSQL stores project records, index state, file hashes, embedding cache metadata, and gateway state.
6. Read commands combine exact graph traversal, semantic retrieval, lexical fallback, project-scoped expansion, and reranking.
7. `repo explain` and Context Gateway responses assemble bounded context packages for AI agents and optional LLM narration.

## Feature Map

| Feature | What it answers | Primary command or surface |
|---|---|---|
| Multi-language parsing | What files, symbols, widgets, imports, calls, and inheritance relationships exist? | `repo index` |
| Knowledge graph generation | How are files, modules, classes, functions, widgets, and projects connected? | Neo4j, `repo trace`, `repo impact`, `repo dependencies` |
| Semantic indexing | Where is code related to a natural-language concept? | `repo search "retry logic"` |
| Hybrid retrieval | Which results are both semantically relevant and structurally connected? | `repo search`, `repo explain`, Context Gateway |
| Cross-encoder reranking | Which candidate snippets are most relevant after broad retrieval? | Search and explain pipeline |
| Dependency graph generation | What imports this file and what does it import? | `repo dependencies <file>` |
| Workflow extraction | What is the execution path from this symbol or feature? | `repo trace <symbol>`, `repo explain --tree` |
| Architecture understanding | What are the major modules and service boundaries? | `repo architecture --format mermaid` |
| Repository explain | How does this feature, module, or flow work? | `repo explain "<topic>" --diagram --tree --deps` |
| Impact analysis | What breaks if I change this symbol or file? | `repo impact <symbol-or-file>` |
| Dead-code detection | Which functions/classes look unused from graph evidence? | `repo dead-code` |
| Onboarding generation | What should a new engineer read first? | `repo onboard --output ONBOARDING.md` |
| Metrics and risk | Which modules are coupled, central, or risky? | `repo metrics --top-risk 10` |
| Smart indexing | What changed since the last commit and needs refresh? | `repo index --smart` |
| Persistent runtime | How can clients reuse graph/vector/model objects? | `repo serve` |
| MCP integration | How can an AI agent request structured repo context? | `mcp/server.py`, gateway MCP tools |
| Context Gateway | How can an agent plan, retrieve, compress, and validate context? | `gateway start`, `gateway mcp config` |
| VS Code integration | How can developers use RIP inside the editor? | `RIP: Open Chat Panel`, context actions |
| Verbose command logs | What happened during a slow or failed command? | Any command with `-v` |

## Core Components

| Component | Directory | Responsibility |
|---|---|---|
| Parser layer | `core/parser` | Tree-sitter based extraction of files, modules, classes, functions, widgets, imports, calls, inheritance, API routes, and database entities. |
| Index pipeline | `core/indexer` | Full indexing, incremental indexing, smart git-diff indexing, watch mode, stale entity cleanup, graph writes, semantic indexing, and progress reporting. |
| Knowledge graph | `core/graph` | Neo4j schema setup, batch writes, project-scoped graph queries, trace, impact, dependencies, architecture, coupling, ownership, and dead-code queries. |
| Search layer | `core/search` | Embedding generation, Qdrant upserts/deletes, project-filtered vector search, lexical graph enrichment, and cross-encoder reranking. |
| LLM layer | `core/llm` | Provider fallback through LiteLLM, graph-first context assembly, prompt templates, and raw-context fallback when no provider is available. |
| Analysis engines | `core/analysis` | Flow tracing, impact analysis, dead-code detection, coupling analysis, risk scoring, onboarding, and architecture generation. |
| CLI | `cli` | The `repo` command surface for indexing, querying, deletion, status, config, serving, and verbose runtime logs. |
| FastAPI server | `server` | Persistent runtime for API clients and long-lived Neo4j/Qdrant/model objects. |
| MCP server | `mcp` | Stdio interface for AI agents to call repository intelligence tools. |
| Context Gateway | `gateway` | Intent classification, planning, parallel source execution, ranking, compression, session memory, conflict detection, permissions, and agent-facing MCP/HTTP tools. |
| VS Code extension | `vscode-extension` | Editor commands, context actions, chat panel, architecture/metrics views, CLI-backed execution, and optional server integration. |

## Why Hybrid Retrieval

RIP uses graph retrieval and vector retrieval together because neither is sufficient alone.

Graph traversal is exact. It can answer "what calls this?", "what imports this file?", "what is affected if this symbol changes?", and "which files contain this entity?" It fails when the user starts with an imprecise natural-language query such as "where is retry handling?" or "how does checkout work?"

Vector search is fuzzy. It finds semantically similar code even when names do not match. It fails when architectural correctness depends on exact edges, project isolation, dependency direction, ownership, or call relationships.

RIP's retrieval path starts with project-scoped vector and lexical candidates, expands them through Neo4j relationships, deduplicates by entity identity, reranks the merged candidates, then compresses the result into a bounded context package. This gives AI agents context that is both discoverable and structurally grounded.

## Supported Languages

| Language | Parser status | Extracted structure |
|---|---|---|
| Python | Implemented | Modules, classes, functions, methods, imports, calls, inheritance, database/API signals. |
| TypeScript / JavaScript | Implemented | Modules, functions/classes where supported by parser rules, imports, and dependency edges. |
| Java | Implemented | Classes, methods, imports, inheritance-oriented structure. |
| Go | Implemented | Packages, functions, imports, and call/dependency signals. |
| Rust | Implemented | Modules, functions, imports, and dependency signals. |
| Dart / Flutter | Implemented | Classes, methods, functions, Flutter widget entities, imports, calls, containment, and inheritance. |

Parser maturity varies by language. Python and Dart/Flutter currently have the richest project-specific validation in this repository.

## Real-Life Workflows

These are the workflows RIP is built for. The examples use realistic names, but the same commands work against any indexed project.

### 1. A new engineer joins a large codebase

The question is not "where are the files?" It is "what should I understand first?"

```bash
repo init /work/billing-api --project-name billing-api
repo index /work/billing-api -v
repo architecture --format mermaid
repo metrics --top-risk 10
repo onboard --output ONBOARDING.md
```

Expected result:

- A service/module architecture diagram.
- A ranked list of central or risky modules.
- An onboarding document grounded in actual indexed files and relationships.
- A repeatable starting point for the next engineer instead of tribal memory.

### 2. A developer needs to change authentication

The risky part is not editing `AuthService`. The risky part is missing a caller, route, provider, widget, test fixture, or downstream dependency.

```bash
repo search "authentication token refresh"
repo trace AuthService --depth 8
repo impact AuthService --format json
repo explain "how token refresh works" --diagram --tree --deps
```

What RIP should surface:

- The core auth classes/functions.
- Files that call or import the auth path.
- Related routes, repositories, providers, or UI screens.
- A workflow tree suitable for a PR description or implementation plan.

### 3. A production bug appears in payment retry logic

Keyword search may find `retry`, but it will not show whether the retry path is connected to checkout, invoices, jobs, or notifications.

```bash
repo search "payment failure retry backoff"
repo dependencies core/payments/retry.py
repo trace PaymentRetryPolicy --depth 10
repo impact core/payments/retry.py
```

How this helps:

- Search finds fuzzy matches such as `backoff`, `attempt`, `idempotency`, or `failure handler`.
- Dependency view shows file-level imports in both directions.
- Trace shows the execution path.
- Impact analysis shows the change surface before the fix is written.

### 4. A Flutter screen behavior needs investigation

RIP indexes Dart/Flutter structure as graph data, including widget classes, methods, imports, calls, containment, and inheritance.

```bash
repo search "daily add entry floating action button"
repo trace ModuleScreenV2 --depth 8
repo dependencies lib/features/modules/module_screen_v2.dart
repo explain "how Daily Add Entry works" --tree --deps
```

Useful output:

- Candidate widgets and providers by semantic relevance.
- Caller/callee and import context around the screen.
- A dependency table showing what the screen imports and what imports it.
- A compact explanation that an agent can use before touching UI code.

### 5. A tech lead wants to delete old code

Dead code is rarely just "no text references." The better question is whether indexed call/import/dependency relationships still reach it.

```bash
repo dead-code --type all
repo impact LegacyInvoiceExporter
repo search "legacy invoice export"
```

The safe workflow is:

1. Use graph evidence to identify likely unused entities.
2. Run impact analysis before deletion.
3. Search semantically for business names that may not match symbol names.
4. Delete only after tests and reviewers confirm the runtime path is gone.

### 6. An AI coding agent needs context before editing

Without RIP, an agent usually starts by grepping, opening files, and guessing what matters. With RIP, it can ask for a bounded context package first.

```bash
uv run gateway mcp config
```

Then the agent can call:

```text
get_context(
  task = "Add audit logging to failed login attempts",
  repo_path = "/work/auth-service",
  token_budget = 6000
)
```

The gateway classifies the task, plans retrieval, queries RIP and optional sources, ranks and compresses evidence, checks session conflicts, applies permissions, and returns a package designed for implementation.

### 7. A reviewer wants to validate a proposed change

Review is faster when the reviewer can see likely blast radius before reading every line.

```text
validate_change(
  files = ["core/auth/session.py", "server/routers/auth.py"],
  summary = "Change session expiry calculation and login failure audit logging"
)
```

Expected context:

- Impacted symbols and files.
- Related routes or callers.
- Possible overlap with active sessions.
- Risk hints from graph centrality, coupling, and ownership signals.

## Example Outputs

RIP output is intentionally structured so it can be read by humans or passed into agents.

### Dependency View

```text
repo dependencies lib/typeProvider/type_provider.dart

Target
  lib/typeProvider/type_provider.dart

Imported by
  lib/features/modules/module_screen_v2.dart
  lib/features/pm/screens/pm_screen.dart

Imports
  package:flutter_riverpod/flutter_riverpod.dart
  lib/models/work_type.dart

Contained symbols
  TypeNotifier
  typeProvider
```

### Explain View

```text
repo explain "how login works" --diagram --tree --deps

Workflow
  LoginScreen
    -> AuthController.login
    -> AuthRepository.authenticate
    -> TokenStore.save
    -> SessionProvider.refresh

Dependencies
  AuthController imports AuthRepository
  LoginScreen watches SessionProvider
  AuthRepository calls ApiClient.post

Explanation
  Login starts in the UI, passes credentials through the controller,
  writes tokens through the repository path, and refreshes session state
  through the provider layer. The highest-risk change points are the
  repository call and token persistence boundary.
```

### Agent Context Package

```json
{
  "intent": "feature_addition",
  "domain": "auth",
  "risk": "medium",
  "context": [
    {
      "source": "rip.trace",
      "title": "Login workflow",
      "files": ["server/routers/auth.py", "core/auth/session.py"]
    },
    {
      "source": "rip.impact",
      "title": "Affected symbols",
      "symbols": ["AuthController.login", "SessionProvider.refresh"]
    }
  ],
  "conflicts": [],
  "token_budget_used": 4310
}
```

## CLI Examples

```bash
# Initialize and index a repository
repo init /path/to/repo --project-name billing-api
repo index /path/to/repo -v

# Re-index only files changed in git
repo index /path/to/repo --smart

# Find relevant code using semantic + graph retrieval
repo search "retry logic around payment failure" --limit 10

# Trace a symbol through the graph
repo trace CheckoutService --depth 8

# Show affected files and downstream dependencies
repo impact core/payments/service.py --format json

# Explain a system area with graph evidence and optional diagrams
repo explain "how login works" --diagram --tree --deps

# Inspect file-level dependencies
repo dependencies lib/typeProvider/type_provider.dart

# Generate architecture and onboarding output
repo architecture --format mermaid
repo onboard --output ONBOARDING.md
```

Every CLI command accepts `-v` / `--verbose` and writes command logs to `.repo-intel/logs/<command>-YYYYMMDD-HHMMSS.log`.

## MCP Integration

RIP exposes repository intelligence through stdio MCP so coding agents can request context instead of scraping files manually.

The RIP MCP server mirrors the CLI-oriented tool surface, including search, trace, impact, explain, architecture, metrics, status, indexing, and guarded delete/config commands. Destructive or long-running operations require explicit opt-in flags in the MCP layer.

The Context Gateway adds a second MCP surface for higher-level agent workflows:

| Gateway tool | Purpose |
|---|---|
| `get_context` | Classify a task, plan retrieval, query sources, rank/compress results, and return an agent-ready context package. |
| `validate_change` | Use RIP impact/trace data plus session conflict checks to evaluate a proposed change. |
| `search_codebase` | Search repository context through the gateway ranking and permission pipeline. |
| `explain_architecture` | Produce architecture context using RIP graph/explain sources. |

Generate gateway MCP configuration with:

```bash
uv run gateway mcp config
```

## Context Gateway

The gateway is the agent orchestration layer on top of RIP. It is designed for AI coding agents that need more than one retrieval call.

Its pipeline is:

```mermaid
flowchart TD
    task["Developer or agent task"] --> classify["Intent classifier"]
    classify --> plan["Multi-source planner"]
    plan --> execute["Parallel executor"]
    execute --> rank["Ranker and deduplicator"]
    rank --> compress["Token-budget compression"]
    compress --> permissions["Permission filter and audit log"]
    permissions --> memory["Session memory and conflict detection"]
    memory --> response["Context package"]
```

RIP is the primary source. Optional GitHub, Jira, and Slack sources are present behind enable/disable configuration and are expected to degrade cleanly when unavailable.

## VS Code Integration

The VS Code extension is a thin interface over RIP's CLI/API capabilities. It contributes:

- `RIP: Open Chat Panel`
- `RIP: Explain Selected`
- `RIP: Trace Selected`
- `RIP: Impact Analysis`
- `RIP: Search Codebase`
- `RIP: Architecture`
- `RIP: Metrics Dashboard`
- `RIP: Index Repository`
- `RIP: Check Status`

The chat panel can run exact `repo ...` and `uv run repo ...` commands, stream terminal output, and render the final result in the webview.

## Repository Isolation

RIP treats each indexed repository as a project.

- PostgreSQL stores project metadata and file/index state.
- Neo4j stores `Project` nodes and project-scoped file/entity relationships.
- Qdrant payloads carry `project_id` and `project_name`.
- Read commands accept `--project` and can also use `.repo-intel/active_project`.

This prevents duplicate filenames or symbol names in different repositories from colliding during search, trace, impact, explain, or dependency queries.

## API Key Authentication

RIP provides API key authentication to secure access to the FastAPI server.

### Key Features
- API keys are stored as SHA-256 hashes (never plaintext)
- Keys can have optional expiration dates
- Keys can be revoked at any time
- Last-used timestamps are tracked
- Development mode (no auth) when no keys exist

### Setup

1. Start the RIP server
2. Create an API key via CLI:
   ```powershell
   uv run repo api-keys create "Flutter App" --description "For the Flutter mobile app" --expires-in 365
   ```
3. List keys:
   ```powershell
   uv run repo api-keys list
   ```
4. Revoke a key (if needed):
   ```powershell
   uv run repo api-keys revoke <key-id>
   ```

### Using API Keys
Include the key in the `Authorization` header:
```
Authorization: Bearer <your-api-key>
```

## Flutter Mobile App

RIP includes a Flutter mobile app that provides an intuitive interface for interacting with the RIP system.

### Features
- Repository indexing and status monitoring
- Semantic search and knowledge graph queries
- Project isolation and switching
- Chat interface with rich content rendering
- Local persistence with Drift
- Riverpod state management

### Setup

1. Navigate to the Flutter app directory:
   ```powershell
   cd rip_app
   ```

2. Install dependencies:
   ```powershell
   flutter pub get
   ```

3. Run the app:
   ```powershell
   flutter run
   ```

4. On the Setup screen:
   - Enter your RIP server URL (e.g., `http://localhost:8000`)
   - Optionally enter your API key (if authentication is enabled)
   - Connect to start using the app

## Installation

Prerequisites:

- Python 3.11 or newer
- `uv`
- Docker / Docker Compose
- Node.js only if developing the VS Code extension

```bash
git clone <repo-url>
cd RIP
uv sync
docker compose up -d
```

Run a smoke check:

```bash
uv run repo --help
uv run repo index --help
```

## Setup And Startup

RIP has two startup paths. Use the bootstrap scripts when the environment still needs dependency sync or migrations. Use the runtime scripts when the virtual environments already exist and you just want to run the local platform.

### First-Time Bootstrap

Use these when setting up the repository on a machine for the first time:

```bash
./start_rip.sh
```

or on Windows PowerShell:

```powershell
.\start_rip.ps1
```

These scripts:

- Check that `uv` is installed.
- Start Docker infrastructure.
- Run `uv sync` for the RIP workspace.
- Enter `gateway/`, run its setup flow, and apply Alembic migrations.
- Print service URLs and next commands.

They are setup/bootstrap helpers, not the fastest daily runtime path.

### Daily Runtime Start

Use these after the environment already exists:

```bash
./start.sh
```

or on Windows PowerShell:

```powershell
.\start.ps1
```

or:

```cmd
start.bat
```

The runtime scripts:

- Reuse the existing `.venv` Python.
- Start Docker services from the root compose file: Neo4j, Qdrant, Postgres, Redis.
- Stop any process already using `RIP_PORT` or `GATEWAY_PORT`.
- Start RIP on `http://127.0.0.1:8000`.
- Start the Context Gateway on `http://127.0.0.1:8001`.
- Write logs to `logs/repo-serve.log` and `logs/gateway.log`.
- Do not run `uv sync`, install packages, build gateway images, or run migrations.

Default runtime environment:

| Variable | Default |
|---|---|
| `RIP_HOST` | `127.0.0.1` |
| `RIP_PORT` | `8000` |
| `GATEWAY_HOST` | `127.0.0.1` |
| `GATEWAY_PORT` | `8001` |
| `GATEWAY_POSTGRES_URL` | `postgresql+asyncpg://repo_intel:repo_intel@localhost:5433/repo_intel?ssl=disable` |
| `GATEWAY_REDIS_URL` | `redis://localhost:6379` |
| `GATEWAY_RIP_MCP_CWD` | repository root |

After startup:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8001/health
tail -f logs/repo-serve.log
tail -f logs/gateway.log
```

On Windows PowerShell:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
Invoke-WebRequest http://127.0.0.1:8001/health
Get-Content .\logs\repo-serve.log -Wait
Get-Content .\logs\gateway.log -Wait
```

## Quick Start

```bash
# Start infrastructure
docker compose up -d

# Index a target repository
uv run repo init /path/to/repo --project-name my-project
uv run repo index /path/to/repo -v

# Query it
uv run repo status /path/to/repo
uv run repo search "authentication flow" --project <project-id>
uv run repo explain "how authentication works" --diagram --tree --deps
uv run repo impact AuthService
```

For persistent API use:

```bash
uv run repo serve --host 127.0.0.1 --port 8000
```

For gateway use:

```bash
uv run gateway status
uv run gateway start
```

## API Surface

The FastAPI server exposes repository operations behind the same core engine used by the CLI:

| Area | Endpoints |
|---|---|
| Indexing | `/index`, `/index/status` |
| Graph queries | `/trace/{symbol}`, `/impact/{symbol}`, `/graph` |
| Search/explain | `/search`, `/explain` |
| Analysis | `/dead-code`, `/onboard`, `/architecture`, `/metrics` |
| Runtime | `/health`, runtime status endpoints |

The gateway server runs separately, by default on port `8001`, and exposes health, context, validation, source, session, and metrics routes.

## Performance Design

RIP's current implementation includes several performance-oriented paths:

- Lazy CLI command imports so `repo --help` does not load graph, vector, LLM, or model dependencies.
- Parallel parsing during indexing.
- Batched Neo4j writes for graph entities, git commits, commit-file edges, and ownership relationships.
- Batched Qdrant upserts and deletes.
- Embedding cache keyed by content hash.
- Compact Qdrant payloads with code previews instead of full raw source.
- Smart indexing from git changed/staged/untracked/deleted files.
- Persistent server runtime for reusing Neo4j, Qdrant, embedding, and reranker objects.
- Verbose per-command logs for diagnosing indexing and runtime stalls.

### Benchmark Reporting

The repository contains a benchmark script and multiple performance-focused validation paths, but benchmark numbers are environment-dependent. Use this table format when publishing measured results:

| Workload | Repository size | Hardware | Command | Result |
|---|---:|---|---|---:|
| Full index | TBD | TBD | `repo index <repo> -v` | TBD |
| Smart index | TBD | TBD | `repo index <repo> --smart -v` | TBD |
| Search latency | TBD | TBD | `repo search "<query>"` | TBD |
| Explain assembly | TBD | TBD | `repo explain "<topic>" --no-llm` | TBD |

Do not compare RIP against grep, GitHub search, or embedding-only systems without recording repository size, language mix, cache state, hardware, model, and whether Neo4j/Qdrant/PostgreSQL were already warm.

## Design Decisions

### Why Tree-sitter

Tree-sitter gives language-aware structure without requiring a running language server or build system. It is fast enough for repository-scale indexing and supports incremental parser development across languages. Regex is too brittle for class/function ownership, imports, nesting, and language-specific syntax.

### Why Neo4j

Repository understanding is relationship-heavy. Calls, imports, containment, ownership, inheritance, and dependency edges are first-class graph data. Neo4j and Cypher make reverse impact, bounded traversal, dependency expansion, and architecture queries more direct than storing the same structure only in relational tables.

### Why Qdrant

Natural-language discovery needs vector search, and repository isolation needs metadata filters. Qdrant provides local, self-hosted vector search with payload filtering and operationally simple collections for development.

### Why PostgreSQL

Graph and vector stores are not ideal for metadata such as projects, file hashes, index state, embedding cache records, gateway sessions, feedback, source health, and audit logs. PostgreSQL handles those durable relational records cleanly.

### Why MCP

MCP gives coding agents a structured interface to ask for repository context. Instead of asking agents to run shell commands, grep files, and infer architecture ad hoc, RIP exposes higher-level tools with explicit schemas, guardrails, and project-scoped behavior.

### Why a Context Gateway

A single search or explain call is not enough for larger tasks. The gateway classifies intent, builds a retrieval plan, queries sources in parallel, ranks evidence, compresses to a token budget, tracks session memory, detects conflicts, and returns a context package an agent can act on.

## Repository Structure

| Path | Purpose |
|---|---|
| `cli/` | Typer command surface for local developer and agent workflows. |
| `core/` | Repository intelligence engine: parsing, graph, search, storage, analysis, LLM context, and indexing. |
| `server/` | FastAPI service over the RIP core. |
| `mcp/` | RIP stdio MCP server and MCP instructions. |
| `gateway/` | Context Gateway package, CLI, server, MCP tools, storage, tests, and docs. |
| `vscode-extension/` | VS Code extension source and webview integration. |
| `docs/` | Architecture, API, language-extension, and retrieval documentation. |
| `tests/` | Unit, integration, fixture, and e2e coverage for RIP core. |
| `scripts/` | Utility scripts such as benchmarking helpers. |
| `TASK.md` | Build ledger and current project state. |
| `cli.md` | Full CLI command reference. |

## Validation

Common checks:

```bash
uv run ruff check .
uv run pytest tests/ -q
uv run pytest gateway/tests/unit -q
npm --prefix vscode-extension run compile
```

Gateway health, when services are running:

```bash
uv run gateway status
curl http://127.0.0.1:8001/health
```

RIP service health, when `repo serve` is running:

```bash
curl http://127.0.0.1:8000/health
```

## Limitations

- Parser depth differs by language. Python and Dart/Flutter have received the most focused validation in this workspace.
- External gateway sources for GitHub, Jira, and Slack are optional and configuration-dependent.
- LLM quality depends on configured providers. RIP can return graph/raw context when LLM providers are unavailable.
- Full benchmark numbers should be measured on the target machine and repository before publishing performance claims.
- Very large monorepos may require tuning Neo4j heap, Qdrant storage, embedding batch size, and project isolation strategy.

## Roadmap

Near term:

- Complete final gateway verification gates for HTTP health, MCP manual checks, linter checks, and full gateway tests.
- Publish measured indexing and retrieval benchmarks on representative repositories.
- Expand parser-specific tests for TypeScript, Java, Go, and Rust to match Python/Dart confidence.

Mid term:

- Improve architecture summaries with richer service boundary extraction.
- Add more precise API, ORM, and event-bus relationship extraction.
- Harden multi-repository and large-monorepo operating profiles.

Long term:

- Add distributed indexing workers.
- Support alternative graph/vector backends behind stable interfaces.
- Expose richer agent workflows through the Context Gateway, including change validation and cross-source context provenance.

## Contributing

Contributions should preserve the layer boundaries:

- `core/` should not depend on CLI, server, MCP, or VS Code modules.
- CLI/API/MCP surfaces should call stable core interfaces.
- New language parsers should enter through the parser registry.
- New analysis features should include source-level tests and, where relevant, graph query tests.
- Performance claims should include measurement context.

Useful references:

- `REPO_INTELLIGENCE_PLATFORM.md` for the original technical blueprint.
- `IMPLEMENTATION_PHASES.md` for build sequencing.
- `TASK.md` for the current ledger and completed work.
- `cli.md` for command details.

## License

Add the project license before publishing this repository as open source.
