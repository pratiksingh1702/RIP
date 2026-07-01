# Context Gateway Operations Guide

## Runtime Mode

Context Gateway is server-mode only. It requires the RIP REST API and Redis-backed Gateway services, so it is not available when RIP resolves to local mode.

Use the existing root `.venv` and `gateway/.venv` runtime paths:

```powershell
docker compose up -d
.\.venv\Scripts\repo.exe serve --mode server
.\gateway\.venv\Scripts\gateway.exe start
```

Use `repo doctor . --mode server` to diagnose provider availability. If `repo doctor . --mode local` is selected, CLI/MCP local queries can still work, but Gateway, Flutter, WebSockets, and remote Git indexing remain unavailable until server mode is running.

## Health Check
1. Via HTTP: `curl http://127.0.0.1:8001/health`
2. Via CLI: `gateway status

## Troubleshooting
- **Source timeouts: check `GATEWAY_SOURCE_TIMEOUT_SECONDS` in `.env`
- **Database issues: check `GATEWAY_POSTGRES_URL`
- **LLM fallback errors: ensure you have your LLM provider configured

## Configuration
- Gateway uses env vars prefixed with `GATEWAY_`
- See `.env.example` for all available options

## Token Budget
The Gateway enforces token budgets by default via `GATEWAY_DEFAULT_MAX_TOKENS=12000`

## Parallel Execution & Circuit Breakers
- Circuit breakers open if source failures exceed `GATEWAY_CIRCUIT_BREAKER_THRESHOLD` and reset after `GATEWAY_CIRCUIT_BREAKER_RESET_SECONDS`
