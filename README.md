# RIP - Repository Intelligence Platform

RIP turns source repositories into structured, queryable context for engineers and AI coding agents. It builds a code knowledge graph, semantic search index, project registry, gateway API, MCP tools, editor integrations, and a Flutter client around one goal: make repository understanding fast, grounded, and reusable.

[Website](https://ripdev.netlify.app/) | [Docs site](web/doc.html) | [Documentation index](documentation/README.md) | [CLI reference](documentation/cli.md)

## What RIP Does

RIP is infrastructure for repository intelligence. It is not just a chatbot over files.

It combines:

- Tree-sitter parsing for source files, symbols, imports, calls, routes, widgets, and relationships.
- Neo4j-backed structural graph queries for trace, impact, dependencies, and architecture.
- Qdrant-backed semantic search for natural-language code discovery.
- PostgreSQL metadata for projects, file hashes, jobs, API keys, users, and gateway state.
- Redis-backed gateway state and caching where the gateway/runtime needs it.
- CLI, FastAPI, MCP, VS Code, web, and Flutter surfaces for different workflows.

## Quick Start

Install the CLI package:

```bash
pip install repo-intelligence==0.1.0
```

Initialize a repository:

```bash
cd path/to/your/repository
repo init --project-name "My Project"
```

Index the codebase:

```bash
repo index -v
```

Ask grounded questions:

```bash
repo search "authentication flow"
repo trace main
repo impact src/auth/session.py
repo explain "how login works" --no-llm --tree
```

Check runtime configuration:

```bash
repo doctor
```

## Runtime Modes

RIP can run without Docker for local repository understanding, or with the full server stack for shared API, gateway, web, and app workflows.

| Mode | Use it when | Storage |
| --- | --- | --- |
| `local` | You want offline CLI search, trace, explain, and indexing without services. | `.repo-intel/local/` |
| `server` | You need REST API, Flutter app, gateway, WebSockets, shared projects, remote Git indexing, or persistent services. | Neo4j, Qdrant, PostgreSQL, Redis |
| `auto` | You want RIP to detect available services and fall back when needed. | Local or server, depending on environment |

Run explicitly in local mode:

```bash
repo index --mode local -v
```

Run with the full service stack:

```bash
docker compose up -d
repo index --mode server -v
```

## Core Surfaces

| Surface | Path | Purpose |
| --- | --- | --- |
| CLI | `cli/` | `repo init`, `repo index`, `repo search`, `repo explain`, `repo projects`, API key management, and operational commands. |
| Core engine | `core/` | Parsing, indexing, graph writes, semantic indexing, retrieval, explain, metrics, and project logic. |
| FastAPI server | `server/` | REST API, authentication, project routes, remote Git flows, WebSocket status, and app/backend integration. |
| Context Gateway | `gateway/` | Context planning, retrieval, compression, validation, API key management, project-aware access, and MCP-facing gateway tools. |
| MCP server | `mcp/` | Direct Model Context Protocol tools for repository intelligence. |
| VS Code extension | `vscode-extension/` | Editor commands, chat panel, and source-context actions. |
| Flutter app | `rip_app/` | Mobile/desktop client for projects, chat, indexing status, and gateway-backed workflows. |
| Web site | `web/` | Product page and production-style documentation site. |
| User documentation | `documentation/` | Workflow, CLI, API, architecture, gateway, setup, and reference material. |

## Common Commands

Project setup:

```bash
repo init --project-name "RIP"
repo projects
repo use <project-id-or-name>
```

Indexing:

```bash
repo index
repo index --smart
repo index --watch
repo index --mode local -v
repo index --mode server -v
```

Repository understanding:

```bash
repo search "payment retry logic"
repo trace <symbol-or-entrypoint>
repo impact <symbol-or-file>
repo dependencies <file>
repo architecture --format mermaid
repo metrics --top-risk 10
repo dead-code
repo onboard --output ONBOARDING.md
```

Explanation and context:

```bash
repo explain "how authentication works" --tree --deps
repo explain "where projects are loaded" --no-llm
repo context "files needed to modify API key management"
```

Operations:

```bash
repo doctor
repo delete <project>
repo serve
```

See [documentation/cli.md](documentation/cli.md) for the full command reference with options and examples.

## Gateway And API Key Management

The Context Gateway provides project-aware context retrieval for agents and applications. It includes API key management, gateway command routing, project-scoped access, MCP integration, and HTTP APIs.

Typical development flow:

```bash
docker compose up -d
cd gateway
uv run gateway start
uv run gateway mcp config
```

Key references:

- [Gateway API flow](documentation/gateway_api_flow.md)
- [API documentation](documentation/api_doc.md)
- [MCP instructions](mcp/mcp-instructions.md)
- [Gateway README](gateway/readme.md)

## Documentation

The main user documentation now lives in [documentation/](documentation/).

Start with:

- [Workflow guide](documentation/workflow.md)
- [CLI reference](documentation/cli.md)
- [Setup guide](documentation/setup.md)
- [API documentation](documentation/api_doc.md)
- [VS Code guide](documentation/vscode.md)
- [Architecture guide](documentation/architecture.md)

The production-style single-page docs site is available at [web/doc.html](web/doc.html), and the product page links to it from [web/index.html](web/index.html).

## Development

Install dependencies:

```bash
uv sync
```

Run tests:

```bash
uv run pytest tests/ -q
```

Run linting:

```bash
uv run ruff check .
```

Start infrastructure:

```bash
docker compose up -d
```

Start the API server:

```bash
uv run repo serve
```

## Repository Hygiene

Generated agent prompts, build prompts, and local assistant instruction files are ignored by `.gitignore`. User-facing documentation belongs in `documentation/`; maintainer planning notes belong in `documentation/internal/`.

This keeps the root focused on runnable project files while preserving the docs that users and contributors need.
