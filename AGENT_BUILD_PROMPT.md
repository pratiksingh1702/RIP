# Agent Build Prompt — Repository Intelligence Platform
## Full Execution Instructions for an AI Coding Agent

---

## WHO YOU ARE AND WHAT YOU ARE BUILDING

You are a senior software engineer AI agent tasked with building the **Repository Intelligence Platform (RIP)** — a complete, production-quality developer tool that transforms any software repository into a queryable, searchable, explainable knowledge system. This is not a chatbot, not a code generator, and not an AI wrapper. It is a software understanding engine built on static analysis, graph databases, vector search, and a local LLM explanation layer.

The platform has three phases that build on top of each other. You are implementing Phase 1 (RIP Core) in full, with Phase 2 (Context Gateway) and Phase 3 (Agent Connections via MCP) designed into the architecture from day one so they can be added on top without refactoring.

---

## YOUR REFERENCE DOCUMENTS — READ ALL OF THEM FIRST

Before writing a single line of code, you must read and fully internalize the following documents. They are your specification, execution plan, tech stack rationale, and architectural contracts. Do not proceed past this section until all four are loaded into your working memory.

**Document 1 — `REPO_INTELLIGENCE_PLATFORM.md`**
This is the master specification. It contains the complete system architecture across all six layers, every tech stack choice with its justification, the full file and directory structure (§7), all database schemas (§9), every CLI command with its flags (§10), all FastAPI endpoint contracts with request/response shapes (§11), the VS Code extension architecture (§12), end-to-end data flow walkthroughs (§13), the scalability design including graceful degradation rules (§14), the configuration system with the full `config.toml` schema (§15), and the ordered build sequence (§16). When you are unsure how to implement anything, the answer is in this document. Reference it by section number throughout your work.

**Document 2 — `IMPLEMENTATION_PHASES.md`**
This is your execution plan. It breaks the build into 10 phases, each with checkbox tasks and a Phase Gate Test. You must not start a phase until every checkbox in the previous phase is checked and its Phase Gate Test passes. The phase gate tests are not optional — they are the verification that your implementation is actually correct before the next phase builds on top of it. Work through phases 0 through 9 in strict order.

**Document 3 — `RIP_AGENT_INTEGRATION_THEORY.md`**
This explains how RIP connects to Claude Code, Codex, and the Context Gateway. Read this so you understand *why* the architecture is designed the way it is. Specifically: understand the two-tier MCP topology, the token economics argument (60× reduction), the feedback loop from agents back to RIP, and the five Context Gateway interception steps. This shapes architectural decisions you will make in Phase 1 — particularly around the `core/` engine's interface design, which must be clean enough for the Gateway to sit on top without modification.

**Document 4 — `tech_stack_table.html`**
This is the complete tech stack reference showing every technology, its exact role, what it connects to, and why it was chosen over alternatives. Use it to resolve any "should I use X or Y?" questions. Every choice has already been made and justified — do not substitute technologies without a strong reason.

---

## THE CORE PHILOSOPHY YOU MUST NEVER VIOLATE

**The Water Principle.** The system must be scalable, adaptable, and expandable. Three rules enforce this at all times:

**Rule 1 — No layer knows more than it needs to.** The parser does not know about the graph. The graph does not know about the LLM. The LLM does not know about the CLI. If you find yourself importing a graph module inside a parser module, stop and restructure.

**Rule 2 — Every component has a defined interface.** All inter-layer communication goes through Pydantic v2 models. `ParsedFile`, `ParsedEntity`, `ParsedRelationship`, `FlowTrace`, `SearchResult`, `RiskScore` — these are contracts. Nothing passes between layers as raw dicts or untyped data.

**Rule 3 — Everything is addable without breaking what exists.** New language parser: implement `BaseParser`, register it, done — zero changes to existing parsers. New analysis engine: implement `BaseAnalyser`, done. New CLI command: add a file in `cli/commands/`, done. If adding something new requires modifying existing working code, your interfaces are wrong.

**The LLM is the last step, not the first.** The LLM never reads raw files. It never sees the full codebase. It receives only a compact context package (3,000–8,000 tokens) assembled by `ContextAssembler` from graph traversal results and vector search results. The graph and the vector index do the understanding. The LLM narrates findings. If you find yourself sending large amounts of raw code to the LLM, you have made an architectural error.

**Graceful degradation over crashing.** If Neo4j is down, fall back to in-memory graph (limited). If Qdrant is down, fall back to keyword search. If Ollama is down, return raw structural results without narration. If a file type has no parser, log and skip — never crash. The system must always return something useful even in partial-failure conditions.

---

## TECHNOLOGY STACK — NON-NEGOTIABLE CHOICES

Use exactly these technologies. Do not substitute without a documented reason.

**Python runtime and tooling:** Python 3.11+, `uv` for package management (not pip, not poetry), `ruff` for linting and formatting (replaces flake8 + black + isort), `pytest` with `pytest-asyncio` for all tests.

**Parsing:** `tree-sitter` with `tree-sitter-languages` bundle for Python, Java, TypeScript, Go, Rust. `GitPython` for git history ingestion. `watchdog` for file system watching in `--watch` mode.

**Graph database:** Neo4j Community Edition via `neo4j` Python driver (async). All graph queries are Cypher — never build graph traversal logic in Python that duplicates what Cypher can do natively.

**Vector database:** Qdrant (self-hosted via Docker) via `qdrant-client`. Embedding model is `BAAI/bge-m3` via `sentence-transformers`. Cross-encoder reranking for precision improvement on search results.

**Relational + cache:** PostgreSQL with `SQLAlchemy 2.0` async ORM and `Alembic` migrations. Redis for query result caching (optional but included in docker-compose). Single-user mode uses SQLite — controlled by `use_sqlite = true` in config.

**LLM layer:** `Ollama` for local model serving (default model: `qwen2.5-coder:7b`). `LiteLLM` as the unified abstraction so any model can be swapped in via config without code changes. Anthropic SDK available as opt-in cloud fallback.

**API and CLI:** `FastAPI` for the HTTP server (used by VS Code extension). `Typer` for the CLI (direct Python imports into `core/` — no HTTP overhead for CLI commands). `Rich` for terminal output formatting. `Pydantic v2` for all data models.

**VS Code extension:** TypeScript, VS Code Extension API (child process communication via stdout JSON for basic commands, FastAPI HTTP for webview panels), `D3.js` for dependency graph visualization in webviews.

**Infrastructure (local dev):** `docker-compose.yml` must spin up Neo4j, Qdrant, PostgreSQL, and Redis with a single `docker-compose up -d` command. No manual database installation should ever be required.

---

## FILE STRUCTURE — CREATE THIS SKELETON IN PHASE 0

Create every directory and file listed below at the start of Phase 0, even if files are empty stubs. This prevents structural drift across phases. The exact structure is specified in §7 of `REPO_INTELLIGENCE_PLATFORM.md` — replicate it exactly.

```
repo-intelligence/
├── README.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── .env
├── docker-compose.yml
├── Makefile
├── cli/
│   ├── __init__.py
│   ├── main.py
│   ├── commands/
│   │   ├── __init__.py
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
│       ├── __init__.py
│       ├── formatters.py
│       └── themes.py
├── server/
│   ├── __init__.py
│   ├── app.py
│   ├── config.py
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── logging.py
│   │   └── errors.py
│   ├── routers/
│   │   ├── __init__.py
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
│       ├── __init__.py
│       ├── requests.py
│       └── responses.py
├── core/
│   ├── __init__.py
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── traversal.py
│   │   ├── git_ingestor.py
│   │   ├── languages/
│   │   │   ├── __init__.py
│   │   │   ├── python.py
│   │   │   ├── java.py
│   │   │   ├── typescript.py
│   │   │   ├── go.py
│   │   │   └── rust.py
│   │   └── extractors/
│   │       ├── __init__.py
│   │       ├── entities.py
│   │       ├── imports.py
│   │       ├── apis.py
│   │       └── databases.py
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── schema.py
│   │   ├── builder.py
│   │   ├── models.py
│   │   └── queries/
│   │       ├── __init__.py
│   │       ├── trace.py
│   │       ├── impact.py
│   │       ├── dead_code.py
│   │       ├── coupling.py
│   │       ├── architecture.py
│   │       └── ownership.py
│   ├── search/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── embedder.py
│   │   ├── indexer.py
│   │   ├── searcher.py
│   │   └── reranker.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── cache.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── index_state.py
│   │   │   ├── file_hash.py
│   │   │   └── analysis_job.py
│   │   └── migrations/
│   │       └── versions/
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── flow_tracer.py
│   │   ├── impact_analyser.py
│   │   ├── dead_code_detector.py
│   │   ├── coupling_analyser.py
│   │   ├── risk_scorer.py
│   │   ├── onboard_engine.py
│   │   └── architecture_generator.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── context_assembler.py
│   │   ├── models.py
│   │   └── prompts/
│   │       ├── __init__.py
│   │       ├── explain.py
│   │       ├── trace.py
│   │       ├── onboard.py
│   │       └── architecture.py
│   └── indexer/
│       ├── __init__.py
│       ├── pipeline.py
│       ├── incremental.py
│       └── worker.py
├── vscode-extension/
│   ├── package.json
│   ├── tsconfig.json
│   ├── .vscodeignore
│   └── src/
│       ├── extension.ts
│       ├── client/
│       │   ├── apiClient.ts
│       │   └── serverManager.ts
│       ├── providers/
│       │   ├── hoverProvider.ts
│       │   ├── codeActionProvider.ts
│       │   └── definitionProvider.ts
│       ├── panels/
│       │   ├── dependencyGraphPanel.ts
│       │   ├── impactPanel.ts
│       │   ├── tracePanel.ts
│       │   └── architecturePanel.ts
│       ├── watchers/
│       │   └── fileSaveWatcher.ts
│       └── utils/
│           ├── lspHelper.ts
│           └── themeHelper.ts
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   │   └── sample_repos/
│   │       ├── python_simple/
│   │       ├── java_spring/
│   │       └── multi_service/
│   ├── unit/
│   │   ├── test_parser_python.py
│   │   ├── test_parser_java.py
│   │   ├── test_graph_builder.py
│   │   ├── test_flow_tracer.py
│   │   ├── test_impact_analyser.py
│   │   ├── test_dead_code_detector.py
│   │   └── test_context_assembler.py
│   ├── integration/
│   │   ├── test_index_pipeline.py
│   │   ├── test_search.py
│   │   └── test_api_endpoints.py
│   └── e2e/
│       └── test_full_workflow.py
├── scripts/
│   ├── setup_dev.sh
│   ├── seed_test_repo.sh
│   └── benchmark.py
└── docs/
    ├── architecture.md
    ├── adding_a_language.md
    ├── adding_an_analysis.md
    └── api_reference.md
```

---

## KEY INTERFACES — IMPLEMENT THESE EXACTLY

These are the Pydantic contracts that govern inter-layer communication. Do not change field names or types without updating all consumers.

### Parser output contracts

```python
# core/parser/base.py

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from abc import ABC, abstractmethod

@dataclass
class ParsedEntity:
    entity_type: str        # "class"|"function"|"interface"|"api_route"|"db_model"
    name: str
    fqn: str                # fully qualified: "module.ClassName.method_name"
    file_path: str
    line_start: int
    line_end: int
    language: str
    docstring: Optional[str]
    decorators: List[str]
    is_exported: bool
    raw_code: str

@dataclass
class ParsedRelationship:
    from_fqn: str
    to_fqn: str
    relationship_type: str  # "CALLS"|"IMPORTS"|"EXTENDS"|"IMPLEMENTS"
    file_path: str
    line: int

@dataclass
class ParsedFile:
    file_path: str
    language: str
    entities: List[ParsedEntity]
    relationships: List[ParsedRelationship]
    imports: List[str]
    sha256_hash: str

class BaseParser(ABC):
    @abstractmethod
    def can_parse(self, file_path: Path) -> bool: ...
    @abstractmethod
    def parse_file(self, file_path: Path, content: str) -> ParsedFile: ...
```

### Parser registry — plug-in architecture

```python
# core/parser/registry.py

class LanguageParserRegistry:
    def __init__(self):
        self._parsers: List[BaseParser] = []

    def register(self, parser: BaseParser) -> None:
        self._parsers.append(parser)

    def get_parser(self, file_path: Path) -> Optional[BaseParser]:
        for parser in self._parsers:
            if parser.can_parse(file_path):
                return parser
        return None  # Unknown language = skip gracefully, never crash
```

### Graph node and edge schema

Neo4j node labels: `File`, `Module`, `Class`, `Function`, `Interface`, `APIRoute`, `DBEntity`, `Developer`, `Commit`

Neo4j relationship types: `CONTAINS`, `CALLS`, `IMPORTS`, `EXTENDS`, `IMPLEMENTS`, `EXPOSES_API`, `HANDLED_BY`, `QUERIES`, `OWNED_BY`, `AUTHORED`, `MODIFIES`, `DEPENDS_ON`

Neo4j constraints (run on startup — see §9):
```cypher
CREATE CONSTRAINT file_path_unique IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE;
CREATE CONSTRAINT function_fqn_unique IF NOT EXISTS FOR (fn:Function) REQUIRE fn.fqn IS UNIQUE;
CREATE CONSTRAINT class_fqn_unique IF NOT EXISTS FOR (c:Class) REQUIRE c.fqn IS UNIQUE;
CREATE INDEX function_name IF NOT EXISTS FOR (fn:Function) ON (fn.name);
CREATE INDEX file_language IF NOT EXISTS FOR (f:File) ON (f.language);
```

### Core Cypher queries — implement these exactly

```cypher
-- Flow trace
MATCH path = (start:Function {name: $entry_point})-[:CALLS*1..10]->(end:Function)
RETURN path ORDER BY length(path) DESC LIMIT 50

-- Impact analysis (reverse traversal)
MATCH (target {name: $symbol})<-[:CALLS|IMPORTS|DEPENDS_ON*1..5]-(affected)
RETURN affected.name, affected.file_path, labels(affected) AS type

-- Dead code
MATCH (f:Function)
WHERE NOT ()-[:CALLS]->(f)
AND NOT f.name IN $known_entry_points
RETURN f.name, f.file_path

-- Coupling: afferent
MATCH (m:Module {name: $module})<-[:DEPENDS_ON]-(dep:Module)
RETURN count(dep) AS afferent_coupling

-- Risk components
MATCH (f:File {path: $file_path})
OPTIONAL MATCH (f)<-[:MODIFIES]-(c:Commit)
OPTIONAL MATCH ()-[:CALLS]->(fn:Function)<-[:CONTAINS]-(f)
RETURN f.path, count(DISTINCT c) AS change_frequency, count(DISTINCT fn) AS incoming_calls
```

### Context assembler — the most critical component

```python
# core/llm/context_assembler.py
# The LLM never sees raw files. Max context: 6000 tokens by default.
# Assemble: query intent + graph nodes + code snippets (token-budgeted)
# Priority: graph results > code snippets > metadata
# If budget runs out mid-snippets, truncate — never exceed max_tokens
```

### FastAPI response envelope — all endpoints use this

```python
{
  "success": bool,
  "data": Any,
  "error": Optional[str],
  "duration_ms": int
}
```

### Configuration file schema

Create `.repo-intel/config.toml` on `repo init`. Full schema in §15 of `REPO_INTELLIGENCE_PLATFORM.md`. Key fields: `[project]` name/root/languages/exclude, `[graph]` neo4j_uri/user/password/max_trace_depth, `[search]` qdrant_host/port/embedding_model/top_k, `[storage]` postgres_url/redis_url/use_sqlite, `[llm]` provider/model/ollama_host/max_context_tokens/explain_by_default, `[server]` host/port/auto_start.

---

## PHASE-BY-PHASE EXECUTION INSTRUCTIONS

Execute phases in this exact order. Do not skip. Do not parallelize unless explicitly noted.

### Phase 0 — Infrastructure and Skeleton

Set up the project with `uv init repo-intelligence`. Add all dependencies to `pyproject.toml`: fastapi, uvicorn, typer, rich, pydantic, pydantic-settings, tree-sitter, tree-sitter-languages, neo4j, qdrant-client, sentence-transformers, sqlalchemy, alembic, asyncpg, redis, gitpython, watchdog, litellm, httpx, and dev dependencies (pytest, pytest-asyncio, ruff). Create the full directory skeleton listed above. Write `docker-compose.yml` with Neo4j (port 7474/7687), Qdrant (port 6333), PostgreSQL (port 5432), and Redis (port 6379). Write `.env.example` with all required environment variables. Write a `Makefile` with targets: `make setup` (uv sync + docker-compose up), `make test` (pytest), `make lint` (ruff check), `make index path=X` (repo index shortcut). Create three small sample repos under `tests/fixtures/sample_repos/python_simple/`, `java_spring/`, and `multi_service/` — these are your test targets throughout all phases. Gate test: `docker-compose up -d` starts all four services without error. `uv sync` installs all deps without error. Directory structure matches §7 exactly.

### Phase 1 — Parser Layer (Python first)

Implement `core/parser/base.py` with `ParsedEntity`, `ParsedRelationship`, `ParsedFile` dataclasses and `BaseParser` abstract class exactly as specified above. Implement `core/parser/registry.py` with `LanguageParserRegistry`. Implement `core/parser/traversal.py` with a `FileTraversal` class that walks a directory recursively, respects `.gitignore` patterns, skips files larger than `max_file_size_kb`, and calls the registry to get the right parser per file. Implement `core/parser/languages/python.py` as a full `PythonParser(BaseParser)` using tree-sitter. It must extract: all class definitions with their docstrings, all function/method definitions with their docstrings, all import statements (resolved to module paths where possible), all decorators, REST route annotations (Flask `@app.route`, FastAPI `@router.get`, Django `urlpatterns`), SQLAlchemy model classes. Write unit tests in `tests/unit/test_parser_python.py` against `tests/fixtures/sample_repos/python_simple/`. Gate test: parser correctly extracts all classes, functions, imports, and relationships from the Python fixture. `ParsedFile` objects contain no `None` fqn values.

### Phase 2 — Graph Layer

Implement `core/graph/client.py` as an async Neo4j connection pool wrapper. Implement `core/graph/schema.py` that runs all constraints and indexes on startup (the five Cypher statements listed above). Implement `core/graph/models.py` with Pydantic models for `GraphNode`, `GraphEdge`, `FlowTrace`, `FlowHop`, `ImpactResult`. Implement `core/graph/builder.py` as `GraphBuilder` that takes a `ParsedFile` and writes all nodes and edges to Neo4j using batched Cypher writes. Implement `core/graph/queries/trace.py` and `core/graph/queries/impact.py` with the exact Cypher queries listed above. Write integration tests against the dockerized Neo4j. Gate test: index `python_simple` fixture, run `MATCH (f:Function) RETURN f LIMIT 10` in Neo4j browser and see expected functions. Trace query returns non-empty call chain. Impact query returns correct reverse dependents.

### Phase 3 — CLI Skeleton + FastAPI (real index/trace/impact)

Implement `server/app.py` FastAPI factory with middleware registered. Implement `server/config.py` using pydantic-settings reading from `config.toml` and environment variables. Implement `server/schemas/requests.py` and `server/schemas/responses.py` with all Pydantic models matching §11 API contracts exactly. Implement `server/routers/index.py`, `trace.py`, `impact.py` as real endpoints. Implement `cli/main.py` root Typer app. Implement `cli/commands/init.py` (writes config), `index.py` (calls parser + graph builder), `trace.py` (calls trace Cypher), `impact.py` (calls impact Cypher). All remaining CLI commands return a clear "not yet implemented" Typer error — no crashes, no exceptions. Gate test: `repo init`, `repo index`, `repo trace`, `repo impact` all work. FastAPI `/docs` loads. All endpoints return correct schema.

### Phase 4 — Vector Search

Implement `core/search/client.py` as Qdrant client wrapper that creates the collection on first connect with correct vector size (1024 for BGE-M3) and payload schema. Implement `core/search/embedder.py` as `EmbeddingPipeline` that loads BGE-M3 via sentence-transformers and provides batched embedding with chunking (functions and classes are chunked at their natural boundaries — do not split mid-function). Implement `core/search/indexer.py` that takes parsed entities and stores embeddings with full metadata payload. Implement `core/search/searcher.py` with hybrid search: vector similarity query + metadata filters (language, service, entity_type, owner) combined. Implement `core/search/reranker.py` with cross-encoder reranking of top-40 results to top-20. Wire the embedding step into the `repo index` pipeline so it runs after graph building. Implement `cli/commands/search.py` and `server/routers/search.py`. Gate test: `repo search "database connection pooling"` returns semantically relevant functions. Re-running `repo index` does not duplicate embeddings.

### Phase 5 — Analysis Engines

Implement `core/analysis/base.py` with `BaseAnalyser` abstract class. Implement all six analysis engines in order: `dead_code_detector.py` (uses dead_code Cypher query), `coupling_analyser.py` (uses coupling Cypher), `risk_scorer.py` (centrality × churn from git data / test coverage), `flow_tracer.py` (orchestrates trace Cypher into a structured `FlowTrace`), `onboard_engine.py` (assembles entry points + architecture summary + owner map + risk highlights), `architecture_generator.py` (produces Mermaid diagram and JSON service map from graph). Implement `core/parser/git_ingestor.py` using GitPython to extract commit history, blame, churn, and ownership. Wire git data into Neo4j via `GraphBuilder` as Developer and Commit nodes. Implement all remaining CLI commands and server endpoints. Gate test: all 10 CLI commands work end-to-end on a real test repo with no stubs remaining.

### Phase 6 — LLM Explanation Layer

Implement `core/llm/models.py` with `LLMConfig` and `ModelProvider` enum (`ollama`, `claude`, `openai`, `gemini`). Implement `core/llm/client.py` as `LiteLLMClient` that routes to the configured provider via LiteLLM. The client must accept a pre-assembled context string and a prompt template — it must not assemble context itself. Implement `core/llm/context_assembler.py` as `ContextAssembler`. This is the most critical component in the LLM layer. It takes graph results + search results + the user query and assembles a structured prompt context that fits within `max_context_tokens`. Priority order: query intent first, graph findings second (up to 10 nodes), code snippets third (fill remaining budget). Never exceed the token budget. Log the token count for every assembly. Implement all four prompt templates. Wire `--explain` flag into `repo trace`. Implement `cli/commands/explain.py` and `server/routers/explain.py`. Gate test: `repo explain "authentication flow"` returns coherent natural-language description. Token count logged is always below `max_context_tokens`. System works correctly with `explain_by_default = false`.

### Phase 7 — Incremental Indexing, Caching, Error Handling

Implement all SQLAlchemy ORM models and run Alembic migrations. Implement `core/storage/cache.py` Redis wrapper with TTL helpers. Implement `core/indexer/pipeline.py` as `IndexPipeline` that orchestrates the full index in order: file traversal → parse → graph build → embed → store hashes. Implement `core/indexer/incremental.py` as `IncrementalIndexer` using the file hash strategy from §13: read stored hash, compare to current file hash, if different then delete old entities from Neo4j, delete old embeddings from Qdrant, re-parse, rebuild, re-embed, update stored hash. Add Redis caching to `trace`, `impact`, and `search` queries with configurable TTL. Implement `--watch` flag using watchdog. Add comprehensive error handling: unknown file types log and skip, corrupted files log and skip, Neo4j unavailable falls back to limited in-memory graph, Qdrant unavailable falls back to keyword search, Ollama unavailable returns raw results. Gate test: modify one file, run `repo index --incremental`, only that file's data changes in Neo4j and Qdrant. Cache hit latency is measurably lower than cache miss. Unsupported file types do not crash indexing.

### Phase 8 — VS Code Extension

Scaffold the TypeScript extension with `package.json` (contributes commands: `repoIntel.trace`, `repoIntel.impact`, `repoIntel.explain`, `repoIntel.showArchitecture`, `repoIntel.showDependencyGraph`). The extension communicates with the Python backend via child process for simple queries (spawn `python -m repo_intel <args>`, read stdout as JSON) and via FastAPI HTTP for webview panels that need streaming data. `serverManager.ts` auto-starts the FastAPI server when the extension activates if `auto_start = true` in config. `fileSaveWatcher.ts` listens to `onDidSaveTextDocument` and sends an incremental re-index request. Webview panels use D3 force-directed layout for dependency graphs. `definitionProvider.ts` queries the graph first, falls back to VS Code LSP if the graph returns nothing (handles dynamic imports that static analysis misses). Gate test: right-click a class in VS Code, dependency graph panel opens with correct D3 visualization. File save triggers re-index visible in server logs. Impact and trace panels render real data.

### Phase 9 — Additional Language Parsers

Implement `TypeScriptParser`, `JavaParser`, `GoParser`, `RustParser` — each extends `BaseParser`, each is registered in `LanguageParserRegistry`. No other files change. Each language parser must handle: class/function extraction, import resolution, API route detection (Express routes for TS, Spring `@RequestMapping` for Java, `http.HandleFunc` for Go), ORM model detection. Add fixture repos and tests per language. Gate test: `pytest` full suite green with no regressions. New language parsers extract correct entities from their fixture repos.

---

## THINGS YOU MUST NEVER DO

Never send raw file contents to an LLM. Never skip a Phase Gate Test and proceed to the next phase. Never modify `BaseParser` or `BaseAnalyser` when adding a new language or analysis — only extend them. Never put business logic in CLI commands or FastAPI routers — they call `core/` functions and format output only. Never use synchronous I/O in any `async def` function — always use `asyncio.gather` for parallel queries. Never hardcode paths — everything reads from config. Never build graph traversal logic in Python that Cypher can do natively. Never crash on an unknown file type — log and skip. Never let the incremental indexer skip the hash check — always compare before re-parsing. Never put `import` statements from `server/` or `cli/` inside `core/` — the engine has no knowledge of its consumers.

---

## HOW TO VERIFY YOUR WORK AT EVERY PHASE

At the end of each phase, before moving on, run these checks in order:

1. `ruff check .` — must be clean with zero warnings
2. `pytest tests/unit/` — all unit tests green
3. `pytest tests/integration/` — all integration tests green (requires docker services running)
4. Run the Phase Gate Tests listed in `IMPLEMENTATION_PHASES.md` for that phase manually
5. If any check fails, fix it before proceeding — never carry technical debt forward across phase boundaries

The final verification is the end-to-end sequence from §16 Quick Start of `REPO_INTELLIGENCE_PLATFORM.md`:

```bash
repo init /path/to/real/repo
repo index /path/to/real/repo
repo architecture
repo trace <entry_point>
repo impact <symbol>
repo search "<natural language query>"
repo explain "<architectural question>"
repo dead-code
repo onboard --output ONBOARDING.md
```

All ten commands must produce real, correct, useful output on a real repository that was not part of your test fixtures. This is the final proof that the system works.

---

## WHAT COMES NEXT (PHASE 2 AND 3 — NOT YOUR CURRENT SCOPE BUT DESIGN FOR THEM)

The `core/` engine you build must be designed so that the Context Gateway (Phase 2) can sit on top of it without any refactoring. The Gateway will be a thin orchestration layer that calls the same `core/` functions you are implementing now — `FlowTracer.trace()`, `ImpactAnalyser.analyse()`, `Searcher.search()`, `ContextAssembler.assemble()` — and adds token budgeting, multi-source merging, permission filtering, and session memory on top.

The MCP server (Phase 3) will be another thin adapter that exposes these same `core/` functions as MCP tools: `rip_trace`, `rip_impact`, `rip_search`, `rip_explain`. Claude Code and Codex will call these tools instead of reading raw files. One RIP tool call will return pre-digested architectural knowledge that replaces 50,000 tokens of raw file reading. This is the 60× token reduction described in `RIP_AGENT_INTEGRATION_THEORY.md`.

Design every public function in `core/` with clean, typed inputs and outputs. Keep function signatures stable. This is how you make Phase 2 and Phase 3 a matter of adding adapters rather than rewriting internals.

---

## START HERE

Run these commands in order to begin:

```bash
mkdir repo-intelligence && cd repo-intelligence
uv init .
# Add all dependencies to pyproject.toml as listed in Phase 0
uv sync
docker-compose up -d
# Create full directory skeleton
# Begin Phase 1: core/parser/base.py
```

Read `REPO_INTELLIGENCE_PLATFORM.md` §7 for the exact file structure before creating anything. Read §5 for every dependency version to use. Read §9 for every database schema. Read §11 for every API contract. Read §15 for the configuration schema. Read §16 for the ordered build sequence.

Work through `IMPLEMENTATION_PHASES.md` top to bottom. Check every box. Pass every Phase Gate Test. Build the water.
