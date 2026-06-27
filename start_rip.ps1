# RIP - Repository Intelligence Platform Start Script (PowerShell)
# This script starts the infrastructure and the Context Gateway.

Write-Host "Starting RIP Environment..." -ForegroundColor Blue

# 1. Check for uv
if (!(Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv not found. Please install uv first: https://github.com/astral-sh/uv" -ForegroundColor Yellow
    exit
}

# 2. Start Root Infrastructure (Neo4j, Qdrant, Postgres, Redis)
Write-Host "Starting Root Infrastructure (Docker)..." -ForegroundColor Blue
docker compose up -d

# 3. Wait for Infrastructure to be healthy
Write-Host "Waiting for databases to be healthy..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 4. Sync venv
Write-Host "Syncing RIP venv..." -ForegroundColor Blue
uv sync

# 5. Setup Gateway
if (Test-Path "gateway") {
    Set-Location gateway
    
    # Start Gateway Infrastructure (Postgres, Redis)
    Write-Host "Starting Gateway Infrastructure (Docker)..." -ForegroundColor Blue
    docker compose up -d
    
    # Sync Gateway venv
    Write-Host "Syncing Gateway venv..." -ForegroundColor Blue
    uv sync
    
    # Run Migrations
    Write-Host "Running Gateway Migrations..." -ForegroundColor Blue
    uv run alembic upgrade head
    
    Set-Location ..
}

Write-Host "--------------------------------------------------" -ForegroundColor Green
Write-Host "RIP is ready!" -ForegroundColor Green
Write-Host "--------------------------------------------------" -ForegroundColor Green
Write-Host "Root Services:"
Write-Host " - Neo4j: http://localhost:7474 (neo4j/password)"
Write-Host " - Qdrant: http://localhost:6333"
Write-Host " - Postgres (RIP): localhost:5433"
Write-Host ""
Write-Host "Gateway Services:"
Write-Host " - Postgres (Gateway): localhost:5432"
Write-Host " - Redis: localhost:6379"
Write-Host ""
Write-Host "To start the Gateway API locally:" -ForegroundColor Yellow
Write-Host " cd gateway; uv run gateway start"
Write-Host ""
Write-Host "To run a CLI command:" -ForegroundColor Yellow
Write-Host " uv run repo status"
Write-Host "--------------------------------------------------" -ForegroundColor Green
