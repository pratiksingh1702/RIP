# Repository Intelligence Platform
## Complete Technical Blueprint — Build Document for AI Agents & Developers

---

## Table of Contents

1. [What Is This Project](#1-what-is-this-project)
2. [Why This Exists — The Real Problem](#2-why-this-exists--the-real-problem)
3. [Core Philosophy — The Water Principle](#3-core-philosophy--the-water-principle)
4. [How It Works — System Overview](#4-how-it-works--system-overview)
5. [Tech Stack — Every Choice Explained](#5-tech-stack--every-choice-explained)
6. [Full Architecture — All Layers](#6-full-architecture--all-layers)
7. [Complete File Structure](#7-complete-file-structure)
8. [Layer-by-Layer Build Guide](#8-layer-by-layer-build-guide)
9. [Database Schemas](#9-database-schemas)
10. [CLI Commands — Full Specification](#10-cli-commands--full-specification)
11. [API Contracts — FastAPI Endpoints](#11-api-contracts--fastapi-endpoints)
12. [VS Code Extension Architecture](#12-vs-code-extension-architecture)
13. [Data Flow — End to End](#13-data-flow--end-to-end)
14. [Scalability Design](#14-scalability-design)
15. [Configuration System](#15-configuration-system)
16. [Build Order for AI Agent](#16-build-order-for-ai-agent)

---

## 1. What Is This Project

**Repository Intelligence Platform (RIP)** is a developer tool that transforms any software repository into a queryable, searchable, explainable knowledge system.

It is **not** a code generator. It is **not** an AI pair programmer. It is **not** a chatbot wrapper over a codebase.

It is a **software understanding engine** — the equivalent of hiring a senior engineer who has read every file, traced every request flow, memorized every dependency, and can answer any architectural question instantly.

### What it can answer

```
"How does authentication work in this system?"
"What services are involved in the checkout flow?"
"What breaks if I modify UserService?"
"Where is retry logic implemented?"
"Which modules depend on PaymentService?"
"What code is never called?"
"Who owns the database layer?"
"Which files change together most often?"
"What is the riskiest module to touch right now?"
"Generate onboarding documentation for a new engineer."
```

### What it produces

- Request flow traces across files and services
- Dependency graphs between modules, classes, functions
- Impact analysis before any change
- Dead code reports
- Risk scores per module
- Architecture overviews
- Onboarding documentation
- Natural language explanations of any part of the codebase

### Who uses it

- New engineers joining a large codebase
- Senior engineers answering "how does X work?" for the tenth time
- Tech leads doing pre-change impact analysis
- Teams doing refactoring or migration
- AI coding agents (Claude Code, Cursor, Copilot) that need codebase context

---

## 2. Why This Exists — The Real Problem

### The real bottleneck in software engineering is not writing code

Modern AI tools (Claude Code, Copilot, Cursor, Codex) are excellent at generating code. But they fail at one fundamental task: **understanding large existing systems**.

When a developer joins a 500,000-line codebase with 50 services and 20 developers, the following problems appear immediately:

| Problem | Time cost | Current solution | Why it fails |
|---|---|---|---|
| Understanding architecture | 2–4 weeks | Read the code | Too slow, incomplete |
| Finding relevant files | Hours per task | `grep`, keyword search | Keyword ≠ meaning |
| Impact analysis before change | Hours per PR | Ask a senior engineer | Senior engineer bottleneck |
| Understanding a request flow | 1–2 days | Read + debug | Brittle, incomplete |
| Finding dead code | Never done | No tool | No tool exists |
| Onboarding a new engineer | 3–6 weeks | Pair programming | Doesn't scale |

### Why existing tools don't solve this

**Sourcegraph** — great for code search, not for graph-based architectural understanding.

**GitHub Copilot / Cursor** — generate code inside the current file. No persistent knowledge of the full system. Context window limits kill them on large repos.

**Documentation** — always outdated. Nobody reads it.

**The senior engineer** — becomes a bottleneck. Their knowledge is not queryable.

### What this platform does differently

It treats the repository as a **graph of knowledge**, not a collection of files. Every function, class, service, API endpoint, and database entity is a node. Every call, import, dependency, and ownership relationship is an edge. The graph is built once, kept up to date incrementally, and is queryable at any time — by developers, CLI tools, VS Code extensions, and AI agents.

---

## 3. Core Philosophy — The Water Principle

The system is designed to be like water: **scalable, adaptable, and expandable**.

### Water takes the shape of its container

The system works whether the repository has 1,000 lines or 1,000,000. It works on a single monolith or 50 microservices. It adapts to the project's shape without requiring changes to its core.

### Water flows around obstacles

If a language parser is not available for a specific language, the system degrades gracefully — it indexes what it can and skips what it cannot. It never crashes on unknown input.

### Water can be frozen, poured, or evaporated

The intelligence layer (graph + embeddings) is storage-agnostic. Today it runs on Neo4j + Qdrant. Tomorrow it can run on DGraph or Weaviate. The parsers are pluggable. The LLM backend is swappable. The CLI, VS Code extension, and API are all thin clients over the same core engine.

### Three rules that enforce this

1. **No layer knows more than it needs to.** The parser does not know about the graph. The graph does not know about the LLM. The LLM does not know about the CLI.
2. **Every component has a defined interface.** Components communicate through contracts, not internal state.
3. **Everything is addable without breaking what exists.** New language support, new analysis engines, new CLI commands — all addable without touching existing code.

---

## 4. How It Works — System Overview

### The two-phase lifecycle

#### Phase 1: Indexing (runs once, then incrementally)

```
Repository on disk
        ↓
File Traversal (Tree-sitter, git)
        ↓
Entity Extraction (classes, functions, APIs, imports)
        ↓
Graph Construction (Neo4j nodes + edges)
        ↓
Embedding Generation (Qdrant vector store)
        ↓
Metadata Storage (PostgreSQL)
        ↓
Index is ready — system is queryable
```

#### Phase 2: Query (runs on every user request)

```
User query (CLI command or VS Code action)
        ↓
Intent Classification (what type of query is this?)
        ↓
┌──────────────────┬──────────────────┐
│  Graph Traversal │  Vector Search   │  (parallel)
│  (Neo4j Cypher)  │  (Qdrant)        │
└──────────────────┴──────────────────┘
        ↓
Context Assembler (merge + rank results)
        ↓
[Optional] LLM Explanation (Ollama / Claude)
        ↓
Formatted Output (CLI / JSON / VS Code webview)
```

### The key insight — LLM is the last step, not the first

Most AI developer tools send the entire codebase to an LLM and ask it to understand things. This breaks at scale — a 500,000-line repo cannot fit in any context window.

This platform inverts that. The graph and vector search do the understanding. The LLM only receives a small, precise context package (3,000–8,000 tokens) containing exactly the relevant nodes and code snippets. It then narrates findings in natural language.

The LLM never sees the full codebase. It never needs to.

---

## 5. Tech Stack — Every Choice Explained

### Backend runtime

| Technology | Role | Why this, not alternatives |
|---|---|---|
| **Python 3.11+** | Core backend language | Best ecosystem for parsing, graph, ML, embeddings. FastAPI is Python-native. Alternatives (Node, Go) lack the parsing/ML library depth. |
| **FastAPI** | HTTP server | Async, auto-generates OpenAPI docs, Pydantic models enforce contracts, fastest Python HTTP framework. Flask is too bare, Django is too heavy. |
| **Typer** | CLI framework | Built on Click, auto-generates help text, type-safe arguments. Click alone is lower-level than needed. Argparse is too verbose. |
| **Pydantic v2** | Data validation + schemas | Enforces contracts between layers. Rust-backed, 10x faster than v1. Used for all inter-layer data models. |
| **asyncio + httpx** | Async I/O | Graph queries and vector searches run in parallel. Must be async or latency doubles. |

### Parsing layer

| Technology | Role | Why this, not alternatives |
|---|---|---|
| **Tree-sitter** | AST parsing | Language-agnostic, blazing fast (C core with Python bindings), incremental, exact. LSP is editor-dependent. Regex is brittle. AST is ground truth. |
| **tree-sitter-python** | Python grammar | Official grammar, maintained by tree-sitter org |
| **tree-sitter-java** | Java grammar | Same |
| **tree-sitter-typescript** | TypeScript/JS grammar | Same |
| **tree-sitter-go** | Go grammar | Same |
| **tree-sitter-rust** | Rust grammar | Same |
| **GitPython** | Git history ingest | Access commit history, blame, file ownership, change frequency. Pure Python, well-maintained. |
| **watchdog** | File system watcher | Triggers incremental re-index on file save. Cross-platform. Used when running in watch mode. |

### Graph layer

| Technology | Role | Why this, not alternatives |
|---|---|---|
| **Neo4j Community** | Graph database | Native graph storage and traversal. Cypher query language is expressive for dependency analysis. Alternatives: DGraph (less mature), PostgreSQL with recursive CTEs (no graph algorithms), NetworkX (in-memory only, no persistence). |
| **neo4j Python driver** | Neo4j client | Official async driver. |

### Vector search layer

| Technology | Role | Why this, not alternatives |
|---|---|---|
| **Qdrant** | Vector database | Self-hostable, Rust core (fast), supports payload filters (filter by language, service, owner). Alternatives: Chroma (less production-ready), Pinecone (cloud-only), Weaviate (heavier). |
| **sentence-transformers** | Embedding model | BGE-M3 or `nomic-embed-code` — state-of-the-art for code. Runs locally on CPU. No API key needed. |
| **BGE-M3** | Default embedding model | Best open-source multilingual code embeddings as of 2025. |

### Metadata + cache layer

| Technology | Role | Why this, not alternatives |
|---|---|---|
| **PostgreSQL** | Relational metadata | Index state, file hashes, analysis job history, user config. ACID, reliable, known quantity. SQLite for single-user mode. |
| **SQLAlchemy 2.0** | ORM | Async support, clean migration path. Alembic handles schema migrations. |
| **Redis** | Cache + pub/sub | Cache hot graph query results, session state. Also used for job queue when running async analysis. Optional — system works without it (slower). |

### LLM layer

| Technology | Role | Why this, not alternatives |
|---|---|---|
| **Ollama** | Local LLM runtime | Run Qwen2.5-Coder or DeepSeek-Coder locally, zero API cost, privacy-preserving. Required for offline mode. |
| **Qwen2.5-Coder-7B** | Default local model | Best code understanding in the 7B class. Runs on 8GB RAM. |
| **DeepSeek-Coder-V2** | Alternative local model | Better on complex reasoning, requires 16GB RAM. |
| **Anthropic SDK** | Claude API client | Optional cloud fallback for explanation quality. Privacy opt-in only. |
| **LiteLLM** | LLM abstraction layer | Single interface for Ollama, Claude, GPT-4o, Gemini. Swap models without changing code. |

### VS Code extension

| Technology | Role | Why this, not alternatives |
|---|---|---|
| **TypeScript** | Extension language | Required by VS Code extension API. |
| **VS Code Extension API** | Editor integration | `workspace.findFiles`, `onDidSaveTextDocument`, `DocumentSymbolProvider`, webview panels |
| **vscode-webview-ui-toolkit** | UI components | Microsoft's official Webview component library. Matches VS Code theme automatically. |
| **D3.js** | Graph visualization | Dependency graphs, architecture views inside webview panels. Force-directed layout. |

### Dev tooling

| Technology | Role |
|---|---|
| **uv** | Python package manager (replaces pip + venv, 10x faster) |
| **ruff** | Linter + formatter (replaces flake8 + black + isort) |
| **pytest + pytest-asyncio** | Testing |
| **Docker + docker-compose** | Neo4j + Qdrant + PostgreSQL + Redis local dev |
| **Alembic** | PostgreSQL schema migrations |

---

## 6. Full Architecture — All Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                         Interface Layer                          │
│  ┌──────────────────────┐      ┌──────────────────────────────┐ │
│  │   CLI (Typer)        │      │  VS Code Extension (TS)      │ │
│  │   repo init          │      │  Right-click context menu    │ │
│  │   repo index         │      │  Inline dep graph panel      │ │
│  │   repo trace         │      │  Hover explanations          │ │
│  │   repo impact        │      │  On-save re-index trigger    │ │
│  │   repo explain       │      │  LSP fallback for symbols    │ │
│  │   repo search        │      └──────────────┬───────────────┘ │
│  │   repo dead-code     │                     │                  │
│  │   repo onboard       │                     │                  │
│  └──────────┬───────────┘                     │                  │
└─────────────┼───────────────────────────────┬─┘                  │
              │  HTTP (localhost:8000)         │                   
              ▼                               ▼                   
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Server                              │
│   /index   /trace   /impact   /search   /explain   /graph       │
│   /dead-code   /onboard   /architecture   /metrics              │
│                                                                  │
│   Middleware: auth (optional), request logging, error handling   │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │      Core Engine            │
              │   (repo_intelligence/)      │
              └──────────────┬──────────────┘
                             │
    ┌────────────────────────┼────────────────────────┐
    ▼                        ▼                        ▼
┌───────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Parser   │      │  Analysis       │      │  LLM Engine     │
│  Layer    │      │  Engines        │      │  (Explanation)  │
│           │      │                 │      │                 │
│ Tree-     │      │ Flow Tracer     │      │ Context         │
│ sitter    │      │ Impact Analyser │      │ Assembler       │
│           │      │ Dead Code Det.  │      │                 │
│ Entity    │      │ Coupling Calc.  │      │ LiteLLM         │
│ Extractor │      │ Risk Scorer     │      │ (Ollama/Claude) │
│           │      │ Onboard Engine  │      │                 │
│ Git       │      │ Arch Generator  │      │ Prompt          │
│ Ingestor  │      │                 │      │ Templates       │
└─────┬─────┘      └────────┬────────┘      └────────┬────────┘
      │                     │                        │
      └──────────┬──────────┘                        │
                 ▼                                   │
    ┌────────────────────────┐                       │
    │     Storage Layer      │ ◄─────────────────────┘
    │                        │
    │  Neo4j (graph)         │
    │  Qdrant (vectors)      │
    │  PostgreSQL (metadata) │
    │  Redis (cache)         │
    └────────────────────────┘
```

---

## 7. Complete File Structure

```
repo-intelligence/
│
├── README.md
├── REPO_INTELLIGENCE_PLATFORM.md        ← this file
├── pyproject.toml                        ← uv project config, all dependencies
├── uv.lock
├── .env.example
├── .env                                  ← local secrets (gitignored)
├── docker-compose.yml                    ← Neo4j + Qdrant + PostgreSQL + Redis
├── Makefile                              ← dev shortcuts
│
├── cli/                                  ← Typer CLI entry point
│   ├── __init__.py
│   ├── main.py                           ← root CLI app, registers all command groups
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── init.py                       ← repo init
│   │   ├── index.py                      ← repo index [path] [--watch] [--incremental]
│   │   ├── trace.py                      ← repo trace <entry_point>
│   │   ├── impact.py                     ← repo impact <symbol>
│   │   ├── explain.py                    ← repo explain <topic>
│   │   ├── search.py                     ← repo search <query>
│   │   ├── dead_code.py                  ← repo dead-code
│   │   ├── onboard.py                    ← repo onboard [--output=md]
│   │   ├── architecture.py               ← repo architecture [--format=mermaid]
│   │   └── metrics.py                    ← repo metrics [--module=X]
│   └── output/
│       ├── __init__.py
│       ├── formatters.py                 ← plain, json, markdown, rich-table output
│       └── themes.py                     ← rich console themes
│
├── server/                               ← FastAPI application
│   ├── __init__.py
│   ├── app.py                            ← FastAPI app factory
│   ├── config.py                         ← settings via pydantic-settings
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── logging.py
│   │   └── errors.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── index.py                      ← POST /index, GET /index/status
│   │   ├── trace.py                      ← GET /trace/{symbol}
│   │   ├── impact.py                     ← GET /impact/{symbol}
│   │   ├── search.py                     ← GET /search?q=...
│   │   ├── explain.py                    ← POST /explain
│   │   ├── graph.py                      ← GET /graph/{node_id}, GET /graph/subgraph
│   │   ├── analysis.py                   ← GET /dead-code, GET /metrics, GET /coupling
│   │   ├── onboard.py                    ← GET /onboard
│   │   └── architecture.py              ← GET /architecture
│   └── schemas/
│       ├── __init__.py
│       ├── requests.py                   ← Pydantic request models
│       └── responses.py                  ← Pydantic response models
│
├── core/                                 ← Pure engine — no HTTP, no CLI concerns
│   │
│   ├── parser/                           ← Layer 1: Source code parsing
│   │   ├── __init__.py
│   │   ├── base.py                       ← BaseParser abstract class
│   │   ├── registry.py                   ← LanguageParserRegistry — maps extension → parser
│   │   ├── traversal.py                  ← FileTraversal — walks repo, respects .gitignore
│   │   ├── languages/
│   │   │   ├── __init__.py
│   │   │   ├── python.py                 ← PythonParser(BaseParser)
│   │   │   ├── java.py                   ← JavaParser(BaseParser)
│   │   │   ├── typescript.py             ← TypeScriptParser(BaseParser)
│   │   │   ├── go.py                     ← GoParser(BaseParser)
│   │   │   └── rust.py                   ← RustParser(BaseParser)
│   │   ├── extractors/
│   │   │   ├── __init__.py
│   │   │   ├── entities.py               ← extract classes, functions, interfaces
│   │   │   ├── imports.py                ← extract and resolve import relationships
│   │   │   ├── apis.py                   ← detect REST routes, GraphQL, gRPC
│   │   │   └── databases.py              ← detect ORM models, DB entities
│   │   └── git_ingestor.py               ← GitPython — commits, blame, ownership, churn
│   │
│   ├── graph/                            ← Layer 2: Neo4j graph construction + query
│   │   ├── __init__.py
│   │   ├── client.py                     ← Neo4jClient — async connection pool
│   │   ├── schema.py                     ← Node labels, relationship types, constraints
│   │   ├── builder.py                    ← GraphBuilder — takes parsed entities, writes to Neo4j
│   │   ├── queries/
│   │   │   ├── __init__.py
│   │   │   ├── trace.py                  ← Cypher: full call chain from entry point
│   │   │   ├── impact.py                 ← Cypher: reverse traversal — what depends on X
│   │   │   ├── dead_code.py              ← Cypher: nodes with no incoming edges
│   │   │   ├── coupling.py               ← Cypher: afferent/efferent coupling per module
│   │   │   ├── architecture.py           ← Cypher: service map, top-level structure
│   │   │   └── ownership.py              ← Cypher: file/module ownership from git data
│   │   └── models.py                     ← Pydantic models for graph nodes and edges
│   │
│   ├── search/                           ← Layer 3: Qdrant vector search
│   │   ├── __init__.py
│   │   ├── client.py                     ← QdrantClient wrapper
│   │   ├── embedder.py                   ← EmbeddingPipeline — chunks code, calls model
│   │   ├── indexer.py                    ← takes parsed entities, embeds, stores in Qdrant
│   │   ├── searcher.py                   ← hybrid search: vector + metadata filters
│   │   └── reranker.py                   ← CrossEncoderReranker — rerank top-k results
│   │
│   ├── storage/                          ← Layer 4: PostgreSQL + Redis
│   │   ├── __init__.py
│   │   ├── database.py                   ← SQLAlchemy async engine + session factory
│   │   ├── cache.py                      ← Redis client wrapper, TTL helpers
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── index_state.py            ← IndexState ORM model
│   │   │   ├── file_hash.py              ← FileHash ORM model (incremental indexing)
│   │   │   └── analysis_job.py           ← AnalysisJob ORM model
│   │   └── migrations/
│   │       └── versions/                 ← Alembic migration files
│   │
│   ├── analysis/                         ← Layer 5: Analysis engines
│   │   ├── __init__.py
│   │   ├── base.py                       ← BaseAnalyser abstract class
│   │   ├── flow_tracer.py                ← FlowTracer — traces request paths
│   │   ├── impact_analyser.py            ← ImpactAnalyser — what breaks if X changes
│   │   ├── dead_code_detector.py         ← DeadCodeDetector — unused nodes
│   │   ├── coupling_analyser.py          ← CouplingAnalyser — afferent/efferent metrics
│   │   ├── risk_scorer.py                ← RiskScorer — centrality × churn × coverage
│   │   ├── onboard_engine.py             ← OnboardEngine — generates onboarding docs
│   │   └── architecture_generator.py    ← generates Mermaid + JSON architecture maps
│   │
│   ├── llm/                              ← Layer 6: LLM explanation engine
│   │   ├── __init__.py
│   │   ├── client.py                     ← LiteLLMClient — unified interface
│   │   ├── context_assembler.py          ← merges graph + search results into prompt context
│   │   ├── prompts/
│   │   │   ├── __init__.py
│   │   │   ├── explain.py                ← prompt template for explanation
│   │   │   ├── trace.py                  ← prompt template for flow narration
│   │   │   ├── onboard.py                ← prompt template for onboarding docs
│   │   │   └── architecture.py           ← prompt template for architecture summary
│   │   └── models.py                     ← LLMConfig, ModelProvider enum
│   │
│   └── indexer/                          ← Orchestration — ties all layers together
│       ├── __init__.py
│       ├── pipeline.py                   ← IndexPipeline — full index orchestration
│       ├── incremental.py                ← IncrementalIndexer — diff-based re-index
│       └── worker.py                     ← background worker for async indexing
│
├── vscode-extension/                     ← VS Code extension (TypeScript)
│   ├── package.json
│   ├── tsconfig.json
│   ├── .vscodeignore
│   ├── src/
│   │   ├── extension.ts                  ← activate(), registers all commands + providers
│   │   ├── client/
│   │   │   ├── apiClient.ts              ← HTTP client for FastAPI server
│   │   │   └── serverManager.ts          ← starts/stops the Python server process
│   │   ├── providers/
│   │   │   ├── hoverProvider.ts          ← inline hover explanations
│   │   │   ├── codeActionProvider.ts     ← right-click context menu actions
│   │   │   └── definitionProvider.ts     ← go-to-definition (graph + LSP fallback)
│   │   ├── panels/
│   │   │   ├── dependencyGraphPanel.ts   ← D3 force graph in webview
│   │   │   ├── impactPanel.ts            ← impact analysis webview
│   │   │   ├── tracePanel.ts             ← request flow trace webview
│   │   │   └── architecturePanel.ts      ← architecture map webview
│   │   ├── watchers/
│   │   │   └── fileSaveWatcher.ts        ← onDidSaveTextDocument → trigger re-index
│   │   └── utils/
│   │       ├── lspHelper.ts              ← VS Code LSP API wrappers
│   │       └── themeHelper.ts            ← reads VS Code color theme for webviews
│   └── webviews/
│       ├── graph/
│       │   ├── index.html
│       │   ├── graph.js                  ← D3 force-directed graph
│       │   └── graph.css
│       ├── impact/
│       │   ├── index.html
│       │   └── impact.js
│       └── trace/
│           ├── index.html
│           └── trace.js
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                       ← shared fixtures, test DB setup
│   ├── fixtures/
│   │   ├── sample_repos/
│   │   │   ├── python_simple/            ← small Python repo for parser tests
│   │   │   ├── java_spring/              ← small Spring Boot repo
│   │   │   └── multi_service/            ← multiple service repo for integration tests
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
│
├── scripts/
│   ├── setup_dev.sh                      ← installs uv, pulls docker images, runs migrations
│   ├── seed_test_repo.sh                 ← indexes a sample repo for manual testing
│   └── benchmark.py                      ← measures indexing speed on large repos
│
└── docs/
    ├── architecture.md
    ├── adding_a_language.md              ← guide for adding new language parser
    ├── adding_an_analysis.md             ← guide for adding new analysis engine
    └── api_reference.md
```

---

## 8. Layer-by-Layer Build Guide

### Layer 1: Parser

**Purpose:** Read source files, extract structured entities and relationships. No LLM involved.

**BaseParser interface** — every language parser must implement this:

```python
# core/parser/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

@dataclass
class ParsedEntity:
    entity_type: str          # "class" | "function" | "interface" | "api_route" | "db_model"
    name: str
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
    from_entity: str          # fully qualified name: "module.ClassName.method_name"
    to_entity: str
    relationship_type: str    # "CALLS" | "IMPORTS" | "EXTENDS" | "IMPLEMENTS"
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

**Language parser registry** — maps file extensions to parsers, enables plug-in architecture:

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
        return None  # graceful — unknown language is skipped, not an error
```

**Adding a new language** — implement `BaseParser`, register it. Nothing else changes.

### Layer 2: Graph

**Node labels:**

```
File          — a source file
Module        — a package or module
Class         — a class definition
Function      — a function or method
Interface     — an interface or protocol
APIRoute      — an HTTP endpoint
DBEntity      — an ORM model or database table
Developer     — a git contributor
Commit        — a git commit
```

**Relationship types:**

```
(File)-[:CONTAINS]->(Class)
(File)-[:CONTAINS]->(Function)
(Class)-[:EXTENDS]->(Class)
(Class)-[:IMPLEMENTS]->(Interface)
(Function)-[:CALLS]->(Function)
(File)-[:IMPORTS]->(Module)
(Module)-[:DEPENDS_ON]->(Module)
(APIRoute)-[:HANDLED_BY]->(Function)
(Function)-[:QUERIES]->(DBEntity)
(File)-[:OWNED_BY]->(Developer)
(Commit)-[:MODIFIES]->(File)
(Developer)-[:AUTHORED]->(Commit)
```

**Core Cypher queries:**

```cypher
-- Flow trace: full call chain from entry point
MATCH path = (start:Function {name: $entry_point})-[:CALLS*1..10]->(end:Function)
RETURN path ORDER BY length(path) DESC LIMIT 50

-- Impact analysis: what depends on X
MATCH (target {name: $symbol})<-[:CALLS|IMPORTS|DEPENDS_ON*1..5]-(affected)
RETURN affected.name, affected.file_path, labels(affected) AS type

-- Dead code: nodes with no callers (except known entry points)
MATCH (f:Function)
WHERE NOT ()-[:CALLS]->(f)
AND NOT f.name IN $known_entry_points
RETURN f.name, f.file_path

-- Coupling: afferent (who depends on this module)
MATCH (m:Module {name: $module})<-[:DEPENDS_ON]-(dependent:Module)
RETURN count(dependent) AS afferent_coupling

-- Risk score components
MATCH (f:File {path: $file_path})
OPTIONAL MATCH (f)<-[:MODIFIES]-(c:Commit)
OPTIONAL MATCH ()-[:CALLS]->(fn:Function)<-[:CONTAINS]-(f)
RETURN f.path,
       count(DISTINCT c) AS change_frequency,
       count(DISTINCT fn) AS incoming_calls
```

### Layer 3: Vector Search

**What gets embedded:**

- Function body + docstring (chunk per function)
- Class definition + all method signatures
- Commit messages (for "why was this changed?" queries)
- README and inline documentation

**Qdrant collection schema:**

```python
# core/search/client.py

from qdrant_client.models import VectorParams, Distance, PayloadSchemaType

COLLECTION_NAME = "repo_entities"
VECTOR_SIZE = 1024  # BGE-M3 output dimension

# Payload fields stored alongside each vector:
# {
#   "entity_id": str,          # matches Neo4j node ID
#   "entity_type": str,        # "function" | "class" | "commit" etc
#   "name": str,
#   "file_path": str,
#   "language": str,
#   "service": str,            # for multi-service repos
#   "owner": str,              # from git blame
#   "change_frequency": int,   # commits touching this entity
#   "raw_code": str            # for LLM context assembly
# }
```

**Hybrid search — vector + graph:**

```python
# core/search/searcher.py

async def hybrid_search(
    query: str,
    filters: dict = None,
    top_k: int = 20
) -> List[SearchResult]:
    # 1. embed the query
    query_vector = await embedder.embed(query)

    # 2. vector search in Qdrant (with optional payload filters)
    vector_results = await qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        query_filter=build_filter(filters),
        limit=top_k * 2  # over-fetch for reranking
    )

    # 3. for each result, fetch graph context from Neo4j
    enriched = await graph.enrich_with_neighbors(
        [r.entity_id for r in vector_results]
    )

    # 4. rerank using cross-encoder
    reranked = reranker.rerank(query, enriched, top_k=top_k)

    return reranked
```

### Layer 5: Analysis Engines

**FlowTracer:**

```python
# core/analysis/flow_tracer.py

class FlowTracer:
    """
    Traces the full execution path starting from any entry point.
    Traverses the CALLS graph up to max_depth hops.
    Returns a structured flow with metadata at each hop.
    """
    async def trace(
        self,
        entry_point: str,       # e.g. "CheckoutController.checkout"
        max_depth: int = 10,
        include_external: bool = True
    ) -> FlowTrace:
        # Graph traversal — pure Cypher, no LLM
        raw_path = await self.graph.query(TRACE_QUERY, {
            "entry_point": entry_point,
            "max_depth": max_depth
        })
        return self._build_flow_trace(raw_path)
```

**RiskScorer:**

```python
# core/analysis/risk_scorer.py

class RiskScorer:
    """
    Risk = (graph centrality × change frequency) / test_coverage
    High risk = heavily used module that changes often and has low test coverage.
    """
    async def score_module(self, module_path: str) -> RiskScore:
        centrality = await self.graph.get_centrality(module_path)
        churn = await self.storage.get_change_frequency(module_path)
        coverage = await self.storage.get_test_coverage(module_path)  # optional
        score = (centrality * churn) / max(coverage, 0.1)
        return RiskScore(module=module_path, score=score, components={
            "centrality": centrality,
            "churn": churn,
            "coverage": coverage
        })
```

### Layer 6: LLM Engine

**Context assembler — the critical component:**

```python
# core/llm/context_assembler.py

class ContextAssembler:
    """
    Merges graph traversal results + vector search results into a
    compact, structured prompt context.

    The LLM NEVER receives raw files. It only receives this package.
    Maximum context size: 6000 tokens by default.
    """

    def assemble(
        self,
        query: str,
        graph_results: List[GraphNode],
        search_results: List[SearchResult],
        max_tokens: int = 6000
    ) -> str:
        sections = []

        # 1. query intent
        sections.append(f"User query: {query}\n")

        # 2. graph findings — most important, highest priority
        sections.append("## Relevant code entities (from dependency graph)\n")
        for node in graph_results[:10]:
            sections.append(f"- {node.type}: `{node.name}` in `{node.file_path}`")
            if node.relationships:
                for rel in node.relationships[:3]:
                    sections.append(f"  → {rel.type}: `{rel.target}`")

        # 3. code snippets — from vector search
        sections.append("\n## Relevant code snippets\n")
        token_budget = max_tokens - self._count_tokens("\n".join(sections))
        for result in search_results:
            snippet_tokens = self._count_tokens(result.raw_code)
            if snippet_tokens > token_budget:
                break
            sections.append(f"### {result.name} ({result.file_path})\n```\n{result.raw_code}\n```\n")
            token_budget -= snippet_tokens

        return "\n".join(sections)
```

---

## 9. Database Schemas

### PostgreSQL (via SQLAlchemy)

```python
# core/storage/models/index_state.py

class IndexState(Base):
    __tablename__ = "index_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_path: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50))    # "indexing" | "ready" | "error"
    total_files: Mapped[int]
    indexed_files: Mapped[int]
    total_entities: Mapped[int]
    last_indexed_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class FileHash(Base):
    __tablename__ = "file_hashes"

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_path: Mapped[str] = mapped_column(String(1024), index=True)
    file_path: Mapped[str] = mapped_column(String(2048), index=True)
    sha256: Mapped[str] = mapped_column(String(64))
    last_parsed_at: Mapped[datetime]
    entity_count: Mapped[int]
```

### Neo4j constraints (run on startup)

```cypher
CREATE CONSTRAINT file_path_unique IF NOT EXISTS
FOR (f:File) REQUIRE f.path IS UNIQUE;

CREATE CONSTRAINT function_fqn_unique IF NOT EXISTS
FOR (fn:Function) REQUIRE fn.fqn IS UNIQUE;

CREATE CONSTRAINT class_fqn_unique IF NOT EXISTS
FOR (c:Class) REQUIRE c.fqn IS UNIQUE;

CREATE INDEX function_name IF NOT EXISTS
FOR (fn:Function) ON (fn.name);

CREATE INDEX file_language IF NOT EXISTS
FOR (f:File) ON (f.language);
```

---

## 10. CLI Commands — Full Specification

```
repo init                           Initialize .repo-intel/ config in current directory
repo index                          Index entire repo (current directory)
repo index <path>                   Index repo at specified path
repo index --watch                  Index + watch for file changes, re-index on save
repo index --incremental            Only re-index files changed since last run
repo index --languages py,java      Restrict to specific languages

repo trace <symbol>                 Trace full call chain from symbol
repo trace <symbol> --depth 5       Limit trace depth
repo trace <symbol> --format json   Output as JSON

repo impact <symbol>                What is affected if this symbol changes
repo impact <file_path>             Impact of changing an entire file

repo explain <topic>                Natural language explanation of any topic
repo explain auth                   Explain authentication flow
repo explain "checkout service"     Explain checkout service

repo search <query>                 Semantic search over codebase
repo search "retry logic"
repo search "payment failure handling" --top 10
repo search <query> --language java --service payments

repo dead-code                      Find unused classes, functions, files
repo dead-code --type functions     Only unused functions
repo dead-code --format json

repo architecture                   Generate architecture overview
repo architecture --format mermaid  Output as Mermaid diagram
repo architecture --format json     Output as JSON service map

repo onboard                        Generate onboarding document
repo onboard --output onboarding.md Save to file

repo metrics                        Coupling, cohesion, risk scores
repo metrics --module <module>      Metrics for a specific module
repo metrics --top-risk 10          Top 10 riskiest modules

repo status                         Show index status, last run, entity counts
repo config                         Show/edit configuration
```

---

## 11. API Contracts — FastAPI Endpoints

```python
# All responses follow this envelope:
{
  "success": bool,
  "data": Any,
  "error": Optional[str],
  "duration_ms": int
}

POST /index
Body: { "repo_path": str, "languages": List[str] | None, "incremental": bool }
Response: { "job_id": str, "status": "started" }

GET /index/status
Response: { "status": "indexing|ready|error", "progress": float, "entity_count": int }

GET /trace/{symbol}
Params: depth=10, format=json|text
Response: { "entry_point": str, "hops": List[Hop], "mermaid": str }

GET /impact/{symbol}
Response: { "symbol": str, "affected_files": List[str], "affected_apis": List[str], "risk_level": "low|medium|high" }

GET /search
Params: q=str, top=20, language=str, service=str
Response: { "results": List[SearchResult], "total": int }

POST /explain
Body: { "query": str, "model": "ollama/qwen2.5-coder" | "claude-3-5-sonnet" }
Response: { "explanation": str, "sources": List[str], "model_used": str }

GET /dead-code
Params: type=functions|classes|all
Response: { "unused": List[Entity], "total_count": int }

GET /architecture
Params: format=json|mermaid
Response: { "services": List[Service], "dependencies": List[Dep], "mermaid": str }

GET /onboard
Response: { "markdown": str, "entry_points": List[str], "key_modules": List[str] }

GET /metrics
Params: module=str, top_risk=int
Response: { "modules": List[ModuleMetrics] }
```

---

## 12. VS Code Extension Architecture

### Communication pattern

```
VS Code Extension (TypeScript)
         │
         │ HTTP (localhost:8000)
         ▼
FastAPI Server (Python) — same server the CLI uses
         │
         ▼
Core Engine (Neo4j + Qdrant + Analysers)
```

The extension is a **thin UI client**. All intelligence lives in the Python server.

### Extension activation

```typescript
// src/extension.ts

export async function activate(context: vscode.ExtensionContext) {
    // 1. start Python server if not running
    const server = new ServerManager(context);
    await server.ensureRunning();

    // 2. register commands (right-click menu)
    context.subscriptions.push(
        vscode.commands.registerCommand('repoIntel.traceSymbol', traceSymbol),
        vscode.commands.registerCommand('repoIntel.impactAnalysis', impactAnalysis),
        vscode.commands.registerCommand('repoIntel.explainSymbol', explainSymbol),
        vscode.commands.registerCommand('repoIntel.showArchitecture', showArchitecture),
    );

    // 3. register providers
    context.subscriptions.push(
        vscode.languages.registerHoverProvider('*', new HoverProvider(server)),
        vscode.languages.registerDefinitionProvider('*', new DefinitionProvider(server)),
    );

    // 4. watch for file saves → trigger incremental re-index
    const watcher = new FileSaveWatcher(server);
    watcher.start(context);
}
```

### File save → incremental re-index

```typescript
// src/watchers/fileSaveWatcher.ts

export class FileSaveWatcher {
    start(context: vscode.ExtensionContext) {
        context.subscriptions.push(
            vscode.workspace.onDidSaveTextDocument(async (doc) => {
                if (this.isSourceFile(doc.uri)) {
                    // non-blocking — fire and forget
                    await this.server.post('/index', {
                        repo_path: this.getRepoRoot(),
                        incremental: true,
                        changed_file: doc.uri.fsPath
                    });
                }
            })
        );
    }
}
```

---

## 13. Data Flow — End to End

### Example: `repo trace CheckoutController`

```
1. CLI receives: repo trace CheckoutController
2. CLI calls: POST http://localhost:8000/trace/CheckoutController
3. FastAPI router calls: FlowTracer.trace("CheckoutController", depth=10)
4. FlowTracer runs Cypher against Neo4j:
   MATCH path = (start:Function {name: "CheckoutController"})-[:CALLS*1..10]->(end)
   RETURN path
5. Neo4j returns: list of nodes and relationships
6. FlowTracer builds: FlowTrace object with hops
7. If --explain flag: ContextAssembler packages the trace + relevant code snippets
8. LiteLLM sends context to Ollama/Claude for natural language narration
9. FastAPI returns JSON response
10. CLI formats and prints to terminal
```

### Example: `repo search "retry logic"`

```
1. CLI receives: repo search "retry logic"
2. FastAPI router calls: hybrid_search("retry logic")
3. Embedder encodes "retry logic" → 1024-dimensional vector
4. Qdrant returns: top 40 nearest code chunks by cosine similarity
5. For each result, Neo4j fetches: callers, callees, file path, owner
6. Reranker reranks: top 20 by cross-encoder relevance score
7. Response: list of functions/classes with similarity score + graph context
8. CLI prints: ranked list with file paths, entity names, confidence scores
```

---

## 14. Scalability Design

### Horizontal scalability

| Component | How it scales |
|---|---|
| FastAPI server | Stateless — run N instances behind nginx |
| Parsing | Parallel file processing using `asyncio.gather` + process pool |
| Neo4j | Read replicas for query load |
| Qdrant | Sharded collections for very large repos |
| PostgreSQL | Standard replication |

### Vertical scalability (single machine)

| Repo size | RAM needed | Index time (est.) | Query latency |
|---|---|---|---|
| < 50k LOC | 4 GB | < 30s | < 100ms |
| 50k–200k LOC | 8 GB | 1–3 min | < 200ms |
| 200k–1M LOC | 16 GB | 5–15 min | < 500ms |
| 1M+ LOC | 32 GB | 30–60 min | < 1s |

### Graceful degradation

- If Neo4j is unavailable: fall back to SQLite-backed lightweight graph (limited traversal depth)
- If Qdrant is unavailable: keyword search only, no semantic search
- If Ollama is unavailable: return raw graph results without LLM explanation
- If a language has no parser: skip those files, index what is parseable

### Incremental indexing design

```python
# core/indexer/incremental.py

async def incremental_index(repo_path: str, changed_file: str):
    # 1. compute new hash of changed file
    new_hash = sha256(read_file(changed_file))

    # 2. check against stored hash
    stored = await storage.get_file_hash(repo_path, changed_file)
    if stored and stored.sha256 == new_hash:
        return  # file unchanged, skip

    # 3. delete old entities for this file from Neo4j
    await graph.delete_file_entities(changed_file)

    # 4. delete old embeddings for this file from Qdrant
    await search.delete_file_embeddings(changed_file)

    # 5. re-parse and re-index only this file
    parser = registry.get_parser(Path(changed_file))
    parsed = parser.parse_file(Path(changed_file), read_file(changed_file))
    await graph.build_from_file(parsed)
    await search.index_file(parsed)

    # 6. update hash record
    await storage.upsert_file_hash(repo_path, changed_file, new_hash)
```

---

## 15. Configuration System

```toml
# .repo-intel/config.toml  (created by repo init)

[project]
name = "my-project"
root = "."
languages = ["python", "java", "typescript"]
exclude = ["node_modules", "__pycache__", "*.min.js", "vendor/", "dist/"]

[indexing]
incremental = true
watch = false
max_file_size_kb = 500          # skip files larger than this

[graph]
neo4j_uri = "bolt://localhost:7687"
neo4j_user = "neo4j"
neo4j_password = "password"
max_trace_depth = 15

[search]
qdrant_host = "localhost"
qdrant_port = 6333
embedding_model = "BAAI/bge-m3"
top_k = 20

[storage]
postgres_url = "postgresql+asyncpg://user:pass@localhost/repo_intel"
redis_url = "redis://localhost:6379"
use_sqlite = false              # set true for zero-config single-user mode

[llm]
provider = "ollama"             # "ollama" | "claude" | "openai" | "gemini"
model = "qwen2.5-coder:7b"
ollama_host = "http://localhost:11434"
max_context_tokens = 6000
explain_by_default = false      # if false, LLM only called when --explain flag used

[server]
host = "127.0.0.1"
port = 8000
auto_start = true               # VS Code extension auto-starts the server
```

---

## 16. Build Order for AI Agent

Follow this exact order. Each step produces a working, testable artifact before the next begins.

### Step 1 — Infrastructure (Day 1)

```bash
# Create project structure
uv init repo-intelligence
cd repo-intelligence

# Add core dependencies
uv add fastapi uvicorn typer rich pydantic pydantic-settings
uv add tree-sitter tree-sitter-languages
uv add neo4j qdrant-client sentence-transformers
uv add sqlalchemy alembic asyncpg redis
uv add gitpython watchdog litellm
uv add --dev pytest pytest-asyncio ruff

# Start infrastructure
docker-compose up -d  # Neo4j + Qdrant + PostgreSQL + Redis

# Run migrations
alembic upgrade head
```

**Deliverable:** All services running, project structure created.

### Step 2 — Parser (Days 2–3)

Build `core/parser/` in this order:
1. `base.py` — define `ParsedEntity`, `ParsedRelationship`, `ParsedFile`, `BaseParser`
2. `languages/python.py` — implement Python parser using tree-sitter
3. `traversal.py` — walk a directory, call parser for each file
4. Write tests against `tests/fixtures/sample_repos/python_simple/`

**Deliverable:** `python parse_test.py ./sample_repo` prints all extracted entities.

### Step 3 — Graph (Days 4–5)

Build `core/graph/` in this order:
1. `client.py` — Neo4j async connection
2. `schema.py` — run constraint/index setup queries
3. `builder.py` — take `ParsedFile`, write nodes and edges to Neo4j
4. `queries/trace.py` and `queries/impact.py` — first two Cypher queries

**Deliverable:** Index a Python repo, run `MATCH (f:Function) RETURN f LIMIT 10` in Neo4j browser and see results.

### Step 4 — CLI skeleton + FastAPI (Day 6)

Build `cli/` and `server/` with stub implementations:
1. `repo index` calls the parser + graph builder — real implementation
2. `repo trace` calls the trace Cypher query — real implementation
3. `repo impact` calls the impact Cypher query — real implementation
4. All other commands return "not yet implemented" stubs

**Deliverable:** `repo index ./sample_repo && repo trace UserService` produces real output.

### Step 5 — Vector Search (Days 7–8)

Build `core/search/`:
1. `embedder.py` — embed code chunks with BGE-M3
2. `indexer.py` — store embeddings in Qdrant during index phase
3. `searcher.py` — hybrid search
4. `repo search "retry logic"` command wired up

**Deliverable:** `repo search "database connection pooling"` returns relevant functions.

### Step 6 — Analysis Engines (Days 9–11)

Build `core/analysis/` one engine at a time:
1. `dead_code_detector.py` + `repo dead-code`
2. `coupling_analyser.py` + `repo metrics`
3. `risk_scorer.py`
4. `onboard_engine.py` + `repo onboard`
5. `architecture_generator.py` + `repo architecture`

**Deliverable:** All CLI commands work end-to-end on a real test repo.

### Step 7 — LLM Layer (Day 12)

Build `core/llm/`:
1. `client.py` — LiteLLM with Ollama backend
2. `context_assembler.py` — package graph + search results into prompt
3. Wire `--explain` flag into `repo trace` and `repo explain`

**Deliverable:** `repo explain "authentication flow" --explain` returns natural language description.

### Step 8 — VS Code Extension (Days 13–15)

Build `vscode-extension/` in this order:
1. `serverManager.ts` — auto-start Python server
2. `apiClient.ts` — HTTP calls to FastAPI
3. `fileSaveWatcher.ts` — incremental re-index on save
4. `codeActionProvider.ts` — right-click menu
5. `dependencyGraphPanel.ts` — D3 graph webview

**Deliverable:** Install extension in VS Code, right-click any class, see dep graph panel.

### Step 9 — Incremental indexing + polish (Day 16)

1. `core/indexer/incremental.py` — diff-based re-index
2. File hash tracking in PostgreSQL
3. Redis caching for hot queries
4. Error handling throughout — graceful degradation

### Step 10 — Additional languages (ongoing)

Add `core/parser/languages/java.py`, `typescript.py`, `go.py` following the same `BaseParser` interface. No other changes required.

---

## Quick Start

```bash
# 1. clone and setup
git clone https://github.com/yourname/repo-intelligence
cd repo-intelligence
uv sync
docker-compose up -d

# 2. initialize on your repo
repo init /path/to/your/repo
repo index /path/to/your/repo

# 3. start exploring
repo architecture
repo trace UserService
repo impact PaymentService
repo search "retry logic"
repo explain "how does auth work"
repo dead-code
repo onboard --output ONBOARDING.md
```

---

*This document is the single source of truth for the Repository Intelligence Platform.*
*Version: 1.0.0 — Phase 1 (Repository Intelligence)*
*Phase 2 (Context Gateway + MCP Server Management) builds on top of this foundation.*
