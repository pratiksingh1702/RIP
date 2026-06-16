#!/usr/bin/env bash
set -euo pipefail

# RIP Development Helper Script

case "${1:-}" in
    start)
        echo "Starting RIP services..."
        docker-compose up -d
        ;;

    stop)
        echo "Stopping RIP services..."
        docker-compose down
        ;;

    restart)
        echo "Restarting RIP services..."
        docker-compose restart
        ;;

    test)
        echo "Running RIP tests..."
        uv run pytest tests/ -v
        ;;

    lint)
        echo "Running RIP lint..."
        uv run ruff check cli core server tests
        ;;

    fmt)
        echo "Running RIP format..."
        uv run ruff format cli core server tests
        ;;

    install)
        echo "Updating global RIP installation..."
        uv tool install .
        ;;

    help)
        echo "RIP Development Helper"
        echo ""
        echo "Commands:"
        echo "  start   - Start Docker services (Neo4j, Qdrant, etc.)"
        echo "  stop    - Stop Docker services"
        echo "  restart - Restart Docker services"
        echo "  test    - Run all tests"
        echo "  lint    - Run linter"
        echo "  fmt     - Run formatter"
        echo "  install - Update global RIP installation"
        echo "  help    - Show this help message"
        ;;

    *)
        echo "Unknown command: ${1:-}"
        echo ""
        $0 help
        exit 1
        ;;
esac
