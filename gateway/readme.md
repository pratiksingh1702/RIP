# Context Gateway

Phase 2 of the Repository Intelligence Platform (RIP). The Context Gateway orchestrates all data sources, classifies intent, plans retrieval, executes queries in parallel, ranks results, manages sessions, and provides a unified MCP interface to AI coding agents.

## Project Structure

```
gateway/
├── gateway/
│   ├── __init__.py
│   ├── config.py           # Gateway configuration (Pydantic + env vars)
│   ├── core/
│   │   ├── classifier/     # Intent classification (rule-based now, LLM fallback later)
│   │   ├── planner/        # Multi-source query planning
│   │   ├── executor/       # Parallel query execution
│   │   ├── ranker/         # Result ranking and compression
│   │   ├── memory/         # Session persistence and conflict detection
│   │   ├── permissions/    # Permission checks
│   │   ├── sources/        # Source abstractions and RIP client
│   │   ├── llm/            # LLM fallback and summarization
│   │   ├── embeddings/     # Embedding logic
│   │   ├── tokenizer/      # Token counting and budget management
│   │   ├── cache/          # Redis/local cache wrapper
│   │   └── metrics/        # Metrics collection and export
│   ├── mcp/                # MCP server and tools
│   ├── server/             # FastAPI HTTP server
│   ├── cli/                # Typer CLI commands
│   └── storage/            # SQLAlchemy ORM and Alembic migrations
├── tests/
│   ├── unit/
│   ├── integration/
│   └── performance/
├── docs/
├── scripts/
├── pyproject.toml
├── alembic.ini
└── .env.example
```

## Quickstart

1. Install dependencies (using RIP's venv):
   ```bash
   cd gateway
   uv pip install -e .
   ```

2. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. Run database migrations:
   ```bash
   uv run alembic upgrade head
   ```

4. Run the gateway:
   ```bash
   uv run gateway start
   ```
