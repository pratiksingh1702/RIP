#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PYTHON="$ROOT/.venv/bin/python"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
  PYTHON="$ROOT/.venv/Scripts/python.exe"
fi

if [[ ! -f "$PYTHON" ]]; then
  echo "Missing RIP venv Python: $PYTHON" >&2
  exit 1
fi

export RIP_HOST="${RIP_HOST:-127.0.0.1}"
export RIP_PORT="${RIP_PORT:-8000}"
export GATEWAY_HOST="${GATEWAY_HOST:-127.0.0.1}"
export GATEWAY_PORT="${GATEWAY_PORT:-8001}"
export GATEWAY_POSTGRES_URL="${GATEWAY_POSTGRES_URL:-postgresql+asyncpg://repo_intel:repo_intel@localhost:5433/repo_intel?ssl=disable}"
export GATEWAY_REDIS_URL="${GATEWAY_REDIS_URL:-redis://localhost:6379}"
export GATEWAY_RIP_MCP_CWD="${GATEWAY_RIP_MCP_CWD:-$ROOT}"
export PYTHONPATH="$ROOT/gateway${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$ROOT/logs"

# Function to stop processes on a port
stop_processes_on_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -t -i :"$port" 2>/dev/null || true)
  elif command -v netstat >/dev/null 2>&1; then
    pids=$(netstat -tuln 2>/dev/null | grep ":$port" | awk '{print $7}' | cut -d'/' -f1 || true)
  else
    return
  fi
  
  if [ -n "$pids" ]; then
    echo "Stopping processes on port $port..."
    for pid in $pids; do
      if kill -9 "$pid" 2>/dev/null; then
        echo "  Stopped process $pid"
      fi
    done
    sleep 1
  fi
}

echo "Checking for running servers..."
stop_processes_on_port "$RIP_PORT"
stop_processes_on_port "$GATEWAY_PORT"

echo "Checking Docker..."
if ! docker info >/dev/null 2>&1; then
  echo "Docker is not responding. Start Docker Desktop, then run this script again." >&2
  exit 1
fi

echo "Starting RIP Docker services..."
docker compose -f "$ROOT/docker-compose.yml" up -d neo4j qdrant postgres redis

echo "Starting repo server on http://$RIP_HOST:$RIP_PORT"
(
  cd "$ROOT"
  "$PYTHON" -m uvicorn server.app:app --host "$RIP_HOST" --port "$RIP_PORT"
) > "$ROOT/logs/repo-serve.log" 2>&1 &
REPO_PID=$!

sleep 2

echo "Starting Context Gateway on http://$GATEWAY_HOST:$GATEWAY_PORT"
(
  cd "$ROOT"
  "$PYTHON" -m uvicorn gateway.server.main:app --host "$GATEWAY_HOST" --port "$GATEWAY_PORT"
) > "$ROOT/logs/gateway.log" 2>&1 &
GATEWAY_PID=$!

cat <<EOF

Started:
  RIP repo serve:  http://$RIP_HOST:$RIP_PORT  pid=$REPO_PID
  Gateway API:     http://$GATEWAY_HOST:$GATEWAY_PORT  pid=$GATEWAY_PID
  Docker services: Neo4j, Qdrant, Postgres, Redis

Logs:
  $ROOT/logs/repo-serve.log
  $ROOT/logs/gateway.log

To stop servers:
  kill $REPO_PID $GATEWAY_PID

This script does not run uv sync, install packages, app-image builds, or migrations.
EOF
