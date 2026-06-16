# Repository Intelligence Platform

Repository Intelligence Platform (RIP) turns a source repository into a queryable knowledge system built from static analysis, graph traversal, vector search, and a local explanation layer.

This implementation follows the phase plan in `IMPLEMENTATION_PHASES.md` and the architecture in `REPO_INTELLIGENCE_PLATFORM.md`.

## Quick Start

```bash
uv sync
docker-compose up -d
uv run repo init .
uv run repo index .
```

## Development

```bash
make setup
make lint
make test
```
