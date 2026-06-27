#!/bin/bash

# RIP - Repository Intelligence Platform Start Script
# This script starts the infrastructure and the Context Gateway.

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting RIP Environment...${NC}"

# 1. Check for uv
if ! command -v uv &> /dev/null
then
    echo -e "${YELLOW}uv not found. Please install uv first: https://github.com/astral-sh/uv${NC}"
    exit 1
fi

# 2. Start Root Infrastructure (Neo4j, Qdrant, Postgres, Redis)
echo -e "${BLUE}Starting Root Infrastructure (Docker)...${NC}"
docker compose up -d

# 3. Wait for Infrastructure to be healthy
echo -e "${YELLOW}Waiting for databases to be healthy...${NC}"
sleep 5

# 4. Sync venv
echo -e "${BLUE}Syncing RIP venv...${NC}"
uv sync

# 5. Setup Gateway
echo -e "${BLUE}Setting up Context Gateway...${NC}"
if [ -d "gateway" ]; then
    cd gateway
    
    # Start Gateway Infrastructure (Postgres, Redis)
    echo -e "${BLUE}Starting Gateway Infrastructure (Docker)...${NC}"
    docker compose up -d
    
    # Sync Gateway venv
    echo -e "${BLUE}Syncing Gateway venv...${NC}"
    uv sync
    
    # Run Migrations
    echo -e "${BLUE}Running Gateway Migrations...${NC}"
    uv run alembic upgrade head
    
    cd ..
fi

echo -e "${GREEN}--------------------------------------------------${NC}"
echo -e "${GREEN}RIP is ready!${NC}"
echo -e "${GREEN}--------------------------------------------------${NC}"
echo -e "Root Services:"
echo -e " - Neo4j: http://localhost:7474 (neo4j/password)"
echo -e " - Qdrant: http://localhost:6333"
echo -e " - Postgres (RIP): localhost:5433"
echo -e ""
echo -e "Gateway Services:"
echo -e " - Postgres (Gateway): localhost:5432"
echo -e " - Redis: localhost:6379"
echo -e ""
echo -e "${YELLOW}To start the Gateway API locally:${NC}"
echo -e " cd gateway && uv run gateway start"
echo -e ""
echo -e "${YELLOW}To run a CLI command:${NC}"
echo -e " uv run repo status"
echo -e "${GREEN}--------------------------------------------------${NC}"
