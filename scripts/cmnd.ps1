#!/usr/bin/env pwsh
# RIP Development Helper Script (PowerShell)

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "restart", "test", "lint", "fmt", "install", "help")]
    [string]$Command = "help"
)

function Show-Help {
    Write-Host "RIP Development Helper" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  start   - Start Docker services (Neo4j, Qdrant, etc.)" -ForegroundColor Green
    Write-Host "  stop    - Stop Docker services" -ForegroundColor Yellow
    Write-Host "  restart - Restart Docker services" -ForegroundColor Magenta
    Write-Host "  test    - Run all tests" -ForegroundColor Cyan
    Write-Host "  lint    - Run linter" -ForegroundColor Blue
    Write-Host "  fmt     - Run formatter" -ForegroundColor Gray
    Write-Host "  install - Update global RIP installation" -ForegroundColor Green
    Write-Host "  help    - Show this help message" -ForegroundColor White
}

switch ($Command) {
    "start" {
        Write-Host "Starting RIP services..." -ForegroundColor Green
        docker-compose up -d
    }

    "stop" {
        Write-Host "Stopping RIP services..." -ForegroundColor Yellow
        docker-compose down
    }

    "restart" {
        Write-Host "Restarting RIP services..." -ForegroundColor Magenta
        docker-compose restart
    }

    "test" {
        Write-Host "Running RIP tests..." -ForegroundColor Cyan
        uv run pytest tests/ -v
    }

    "lint" {
        Write-Host "Running RIP lint..." -ForegroundColor Blue
        uv run ruff check cli core server tests
    }

    "fmt" {
        Write-Host "Running RIP format..." -ForegroundColor Gray
        uv run ruff format cli core server tests
    }

    "install" {
        Write-Host "Updating global RIP installation..." -ForegroundColor Green
        uv tool install .
    }

    "help" {
        Show-Help
    }

    default {
        Write-Host "Unknown command: $Command" -ForegroundColor Red
        Write-Host ""
        Show-Help
        exit 1
    }
}
