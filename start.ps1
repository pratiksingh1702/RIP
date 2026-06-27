# Context Gateway and RIP Start Script for Windows
$ErrorActionPreference = "Stop"

$ROOT = $PSScriptRoot
$PYTHON = "$ROOT\.venv\Scripts\python.exe"

if (-not (Test-Path $PYTHON)) {
    Write-Host "Missing RIP venv Python: $PYTHON" -ForegroundColor Red
    exit 1
}

# Default environment variables
$env:RIP_HOST = "127.0.0.1"
$env:RIP_PORT = "8000"
$env:GATEWAY_HOST = "127.0.0.1"
$env:GATEWAY_PORT = "8001"
$env:GATEWAY_POSTGRES_URL = "postgresql+asyncpg://repo_intel:repo_intel@localhost:5433/repo_intel?ssl=disable"
$env:GATEWAY_REDIS_URL = "redis://localhost:6379"
$env:GATEWAY_RIP_MCP_CWD = $ROOT
$env:PYTHONPATH = "$ROOT\gateway"

# Create logs directory
New-Item -ItemType Directory -Force -Path "$ROOT\logs" | Out-Null

# Function to stop processes using specific ports
function Stop-ProcessesOnPort {
    param([int]$Port)
    $processes = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess
    if ($processes) {
        Write-Host "Stopping processes on port $Port..." -ForegroundColor Yellow
        foreach ($pid in $processes) {
            try {
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                Write-Host "  Stopped process $pid" -ForegroundColor Gray
            } catch {
                Write-Host "  Failed to stop process $pid" -ForegroundColor Red
            }
        }
        Start-Sleep -Seconds 1
    }
}

# Stop any existing servers
Write-Host "Checking for running servers..." -ForegroundColor Cyan
Stop-ProcessesOnPort -Port $env:RIP_PORT
Stop-ProcessesOnPort -Port $env:GATEWAY_PORT

# Check Docker
Write-Host "Checking Docker..." -ForegroundColor Cyan
try {
    docker info | Out-Null
} catch {
    Write-Host "Docker is not responding. Trying to start Docker Desktop..." -ForegroundColor Yellow
    if (Test-Path "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe") {
        Start-Process "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    } elseif (Test-Path "$env:LocalAppData\Docker\Docker Desktop.exe") {
        Start-Process "$env:LocalAppData\Docker\Docker Desktop.exe"
    }
    Write-Host "Waiting for Docker to start..." -ForegroundColor Cyan
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 2
        try {
            docker info | Out-Null
            break
        } catch {
        }
    }
    if ($i -eq 59) {
        Write-Host "Docker did not become ready in time." -ForegroundColor Red
        exit 1
    }
}

# Start RIP Docker services
Write-Host "Starting RIP Docker services..." -ForegroundColor Cyan
docker compose -f "$ROOT\docker-compose.yml" up -d neo4j qdrant postgres redis

# Start RIP server
Write-Host "Starting repo server on http://$($env:RIP_HOST):$($env:RIP_PORT)" -ForegroundColor Cyan
$repoProcess = Start-Process -FilePath $PYTHON -ArgumentList "-m", "uvicorn", "server.app:app", "--host", $env:RIP_HOST, "--port", $env:RIP_PORT -WorkingDirectory $ROOT -RedirectStandardOutput "$ROOT\logs\repo-serve.log" -RedirectStandardError "$ROOT\logs\repo-serve.log" -PassThru

# Wait a bit
Start-Sleep -Seconds 2

# Start Gateway server
Write-Host "Starting Context Gateway on http://$($env:GATEWAY_HOST):$($env:GATEWAY_PORT)" -ForegroundColor Cyan
$gatewayProcess = Start-Process -FilePath $PYTHON -ArgumentList "-m", "uvicorn", "gateway.server.main:app", "--host", $env:GATEWAY_HOST, "--port", $env:GATEWAY_PORT -WorkingDirectory $ROOT -RedirectStandardOutput "$ROOT\logs\gateway.log" -RedirectStandardError "$ROOT\logs\gateway.log" -PassThru

# Print status
Write-Host ""
Write-Host "Started:" -ForegroundColor Green
Write-Host "  RIP repo serve:  http://$($env:RIP_HOST):$($env:RIP_PORT)  pid=$($repoProcess.Id)"
Write-Host "  Gateway API:     http://$($env:GATEWAY_HOST):$($env:GATEWAY_PORT)  pid=$($gatewayProcess.Id)"
Write-Host "  Docker services: Neo4j, Qdrant, Postgres, Redis"
Write-Host ""
Write-Host "Logs:"
Write-Host "  $ROOT\logs\repo-serve.log"
Write-Host "  $ROOT\logs\gateway.log"
Write-Host ""
Write-Host "To stop servers manually:"
Write-Host "  Stop-Process -Id $($repoProcess.Id),$($gatewayProcess.Id)"
Write-Host ""
Write-Host "This script does not run uv sync, install packages, or migrations." -ForegroundColor Gray
