# Context Gateway Setup Guide

## Getting Started

### Prerequisites

The Context Gateway is part of Repository Intelligence Platform (RIP), so ensure you have:
1. Have RIP's repository cloned and set up
2. Have RIP's virtual environment set up (uv venv created and activated
3. RIP's dependencies installed

### Installation

The gateway directory has its own `pyproject.toml`, but you can install it within RIP's venv:
```bash
cd gateway
uv pip install -e .
```

### Configuration
Copy the example env file to `.env.example to .env:
```bash
cp .env.example .env
```
Edit the `.env` file if you need to change defaults:
- Default values are usually okay for testing purposes, but you may want to adjust:
  - `GATEWAY_POSTGRES_URL`: reuse RIP's PostgreSQL DB
  - `GATEWAY_REDIS_URL`: Redis for cache
  - `GATEWAY_LLM_FALLBACK_THRESHOLD`: 0.7 (default)
  - External source enables (GitHub/Jira/Slack disabled by default)

### Database Migrations
Run the initial database migration using Alembic:
```bash
uv run alembic upgrade head
```

### Running the Gateway

#### Option 1: Via CLI
```bash
uv run gateway start
```
This starts the FastAPI server on `http://127.0.0.1:8001 by default

#### Option 2: As MCP server
For use with MCP agents, follow `gateway mcp config` gives you the MCP server configuration, then use it in Claude Code/Cursor/etc.

