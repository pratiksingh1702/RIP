# RIP (Repository Intelligence Platform) & Context Gateway
## Complete System Architecture & Capability Blueprint

This document provides a comprehensive technical overview of the **RIP Platform**, the **Context Gateway Engine**, and the **Mobile Remote Repository Infrastructure**.

---

## 1. System Overview & Core Purpose

RIP (Repository Intelligence Platform) is an **autonomous, enterprise-grade Repository Intelligence and AI Orchestration System**. It transforms raw codebases into structured entity-relationship knowledge graphs, enabling deep multi-language semantic code search, dependency tracing, change impact analysis, real-time Docker sandbox execution, and dynamic LLM context synthesis for mobile and desktop developer interfaces.

```
+-----------------------------------------------------------------------------------+
|                                  CLIENT LAYER                                     |
|   +--------------------------+  +--------------------------+  +-----------------+  |
|   | Flutter App (iOS/Android)|  |  VS Code Extension       |  |  RIP CLI (`rip`)|  |
|   +--------------------------+  +--------------------------+  +-----------------+  |
+------------------------------------------|----------------------------------------+
                                           | HTTP / WebSockets / JSON-RPC / SSE
+------------------------------------------v----------------------------------------+
|                                 CONTEXT GATEWAY                                   |
|   +------------------------+  +-------------------------+  +-------------------+  |
|   | Task Intent Resolver   |  | Token Budget Allocation |  | Context Synthesizer| |
|   +------------------------+  +-------------------------+  +-------------------+  |
+------------------------------------------|----------------------------------------+
                                           | FastAPI / Async Services
+------------------------------------------v----------------------------------------+
|                                CORE ENGINE & SERVER                               |
|  +--------------------+  +----------------------+  +---------------------------+  |
|  | Multi-Lang Parsers |  | Graph Indexer & Search| | PTY Container Execution  |  |
|  | (Tree-sitter AST)  |  | (ChromaDB + SQLite)  |  | (Docker Sandbox & Terminal)| |
|  +--------------------+  +----------------------+  +---------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 2. Deep Dive: Core Platform Capabilities

### 2.1 Repository Ingestion & Multi-Language Parsing (`core/index/` & `core/parser/`)
- **Polyglot AST Extraction**: Uses Tree-sitter and AST parsers to extract symbols, function signatures, classes, imports, and variables across 10+ languages (Python, Dart, TypeScript/JavaScript, Go, Rust, C/C++, Java, SQL, HTML/CSS).
- **Symbol & Dependency Graph Construction**: Resolves cross-file references, import graphs, class inheritance, and function call chains.
- **Incremental & Background Re-indexing**: Automatically tracks Git commit diffs and re-indexes modified files on save without full repository re-scans.

### 2.2 Semantic Hybrid Search & Retrieval (`core/search/` & `server/routers/search.py`)
- **Hybrid Retrieval Engine**: Combines **BM25 lexical search** with **ChromaDB vector embeddings** (e.g. OpenAI/Ollama embeddings) to find exact function declarations as well as high-level architectural concepts.
- **Re-ranking & Filtering**: Filters search scope by exact project ID, file types, line bounds, or symbol types.

### 2.3 Dependency Tracing & Change Impact Analysis (`server/routers/trace.py` & `impact.py`)
- **Call-Graph Tracing (`/trace`)**: Recursively traces call hierarchies upstream (who calls this function?) and downstream (what does this function call?).
- **Impact Assessment (`/impact`)**: Predicts the blast radius of modifying a target file or symbol across the entire repository before committing changes.
- **Dead Code Detection (`/dead-code`)**: Scans repository ASTs to discover unreachable functions, unreferenced exports, and orphaned dependencies.

### 2.4 Dynamic Context Gateway Engine (`gateway/` & `core/gateway/`)
- **Dual MCP Architecture (Server & Aggregator)**:
  - **Native MCP Server (`gateway start --mcp`)**: Context Gateway operates as a full Model Context Protocol (MCP) server for external clients (**Claude Code, Cursor, Codex, Custom AI Agents**), exposing high-level tools like `get_context`, `search_codebase`, `explain_architecture`, and `validate_change`.
  - **MCP Source Aggregator**: Connects to and orchestrates third-party MCP sources (**GitHub, Jira, Slack, Notion, Postgres, Redis MCP servers**), unifying cross-platform context into a single token-budgeted package.
- **Intent Resolution & Role-Based Prompting**: Maps developer tasks (e.g., bug fixing, refactoring, security auditing) to precise context extraction strategies.
- **Token Budget Allocator**: Dynamically allocates token limits across code definitions, call graphs, Git diffs, and docstrings to ensure prompts fit within configured LLM window constraints.
- **SSE & Streaming Context Packages**: Streams real-time context packages via Server-Sent Events (SSE) or JSON-RPC to clients.

### 2.5 Multi-Provider LLM Router Pool (`core/llm/`)
- **Model Agnostic Routing**: Seamlessly routes tasks across local or cloud LLM providers:
  - **Ollama** (Llama 3, Qwen, DeepSeek Coder local models)
  - **OpenAI** (GPT-4o, GPT-4o-mini)
  - **Anthropic** (Claude 3.5 Sonnet, Claude 3 Haiku)
  - **Google Gemini** (Gemini 1.5 Pro, Gemini Flash)
  - Custom OpenAI-compatible REST endpoints.
- **Context Synthesis & Code Generation**: Formats structured AST context into system/user prompt pairs for instant code explanation, inline refactoring, and automated patch creation.

### 2.6 Docker Sandbox & PTY Interactive Terminal (`server/routers/sandbox.py` & `rip_app/lib/presentation/screens/`)
- **Isolated Execution Environments**: Spins up isolated Docker containers for running code pipelines, tests, and CLI commands.
- **Real-Time WebSocket PTY Streaming**: Connects the Flutter app's interactive terminal directly to container pseudo-terminals (xterm.js / Dart PTY), supporting bidirectional command execution, ANSI color codes, and stdin/stdout streams.

### 2.7 Git Version Control & Server Synchronization (`server/routers/file_tree.py` & `git_metadata.py`)
- **Remote File Tree Navigation**: Provides absolute directory tree listing, size telemetry, and LOC counting.
- **Atomic Edit & Git Commit Endpoint**: `PUT /projects/{id}/file-content` allows direct file modifications from mobile/desktop apps, automatically running `git add` and `git commit` with user credentials.
- **Git Metadata Tracking**: Returns commit history, modified file statuses, active branch details, and diff previews.

### 2.8 Model Context Protocol (MCP) Infrastructure (`mcp/server.py`)
- **Protocol Compliance**: Fully implements the official **Model Context Protocol (MCP)** spec (`2024-11-05`) over JSON-RPC 2.0 STDIO.
- **Native Integration**: Allows external AI clients (**Claude Desktop, Cursor, VS Code, Custom Agents**) to query RIP repository intelligence directly.
- **Exposed MCP Tool Ecosystem**:
  - `repo_search`: Semantic vector & symbol search across the codebase.
  - `repo_trace`: Upstream & downstream call graph tracing from any symbol or function.
  - `repo_impact`: Analyze change impact and affected blast radius.
  - `repo_explain`: Generate architecture explanations with optional Mermaid flowcharts & dependency trees.
  - `repo_dead_code`: Discover orphaned classes, unused functions, and unreferenced exports.
  - `repo_architecture`: Extract complete architectural diagrams in Mermaid or JSON formats.
  - `repo_metrics`: Inspect module risk scores, coupling, complexity, and Git activity telemetry.
  - `repo_onboard`: Automatically generate comprehensive codebase onboarding documentation.
  - `repo_index` / `repo_init`: Trigger AST indexing and vector/graph index updates directly from MCP clients.

---

## 3. Architecture Component Matrix

| Subsystem | Tech Stack | Primary Responsibilities | Key API Endpoints / Modules |
| :--- | :--- | :--- | :--- |
| **Server Engine** | Python, FastAPI, Uvicorn, AsyncIO | Core REST & WebSocket API, authentication, project metadata storage. | `/projects`, `/search`, `/trace`, `/impact`, `/dead-code` |
| **Context Gateway** | Python, SSE, JSON-RPC | Task intent resolution, token budget management, context streaming. | `/gateway/api/context`, `/gateway/api/stream` |
| **Code Parser & Indexer** | Tree-sitter, ChromaDB, SQLite | AST symbol extraction, vector embedding, graph indexing. | `core/index/`, `core/parser/` |
| **LLM Router Pool** | Async HTTP, Provider Drivers | Unified abstraction layer for Ollama, OpenAI, Anthropic, Gemini. | `core/llm/client.py`, `core/llm/models.py` |
| **Sandbox Execution** | Docker SDK, WebSockets, PTY | Containerized code execution, terminal streaming, process monitoring. | `/sandbox/exec`, `/ws/terminal` |
| **Flutter Mobile Client** | Dart, Riverpod, Highlight.js, Dio | High-performance mobile/desktop IDE, glassmorphic UI, terminal, editor. | `rip_app/lib/` |

---

## 4. Key End-to-End Developer Workflows

### Workflow A: Mobile Remote Code Review & Direct Git Commit
1. User selects a remote repository in the Flutter app.
2. App fetches file tree via `GET /projects/{id}/tree`.
3. Code is displayed in `CodeEditorScreen` with high-performance AST syntax highlighting and line numbers.
4. User modifies code, clicks **Save & Commit**, enters a commit message.
5. Server executes atomic file write and stages/commits changes to Git with user identity.

### Workflow B: AI-Powered One-Tap Code Refactoring
1. User opens a file in the code editor and taps the **AI Sparkle Button**.
2. App calls `/gateway/api/context` passing current code, file path, and refactoring intent.
3. Context Gateway queries active LLM router pool (e.g. Ollama/Gemini) and synthesizes code improvements.
4. User clicks **"Apply AI Refactor to Editor"** to immediately update the code editor canvas.

### Workflow C: Remote Sandbox Command Execution
1. User connects to a project container in the app's Terminal view.
2. WebSockets establish a PTY connection to the server's Docker sandbox engine.
3. User runs tests, builds binaries, or executes scripts with interactive stdin/stdout feedback.

---

## 5. Summary

The RIP System is **not just a UI or editor**—it is a complete, full-stack **Repository Intelligence Infrastructure**. By combining Tree-sitter AST parsing, vector/graph search, context budget orchestration, Docker sandbox PTY streaming, and multi-provider LLM routing, it turns mobile and remote devices into powerful AI-assisted development environments.
