#!/bin/bash

# Creator Agents Platform - Setup Verification Script

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Creator Agents Platform - Setup Verification               ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check Docker
echo -e "${YELLOW}1. Checking Docker...${NC}"
if docker ps &> /dev/null; then
    echo -e "${GREEN}✓ Docker daemon is running${NC}"
else
    echo -e "${RED}✗ Docker daemon is not running${NC}"
    echo "  Start Docker Desktop and try again"
    exit 1
fi

# Check shared postgres container
echo ""
echo -e "${YELLOW}2. Checking shared PostgreSQL container...${NC}"
POSTGRES_CONTAINER="78c632d2fda37816658fdf9c790677cde45d22d9f8703944f5af5ad71863050b"
if docker ps | grep -q "$POSTGRES_CONTAINER"; then
    echo -e "${GREEN}✓ Shared PostgreSQL container is running${NC}"
else
    echo -e "${RED}✗ Shared PostgreSQL container is not running${NC}"
    echo "  Start the shared database container first"
    exit 1
fi

# Check shared network
echo ""
echo -e "${YELLOW}3. Checking shared-db-network...${NC}"
if docker network ls | grep -q "shared-db-network"; then
    echo -e "${GREEN}✓ shared-db-network exists${NC}"
else
    echo -e "${RED}✗ shared-db-network not found${NC}"
    echo "  Run: docker network create shared-db-network"
    exit 1
fi

# Check docker-compose file
echo ""
echo -e "${YELLOW}4. Checking docker-compose.yml...${NC}"
if [ -f "docker-compose.yml" ]; then
    echo -e "${GREEN}✓ docker-compose.yml found${NC}"

    # Check if postgres service is removed
    if grep -q "service.*postgres:" docker-compose.yml; then
        echo -e "${RED}✗ WARNING: postgres service still in docker-compose.yml${NC}"
    else
        echo -e "${GREEN}✓ postgres service removed (using shared)${NC}"
    fi

    # Check if shared-db-network is referenced
    if grep -q "shared-db-network" docker-compose.yml; then
        echo -e "${GREEN}✓ shared-db-network configured${NC}"
    else
        echo -e "${RED}✗ shared-db-network not configured${NC}"
    fi

    # Check DATABASE_URL
    if grep -q "shared-postgres-db" docker-compose.yml; then
        echo -e "${GREEN}✓ DATABASE_URL points to shared-postgres-db${NC}"
    else
        echo -e "${RED}✗ DATABASE_URL not configured correctly${NC}"
    fi
else
    echo -e "${RED}✗ docker-compose.yml not found${NC}"
    exit 1
fi

# Check ports
echo ""
echo -e "${YELLOW}5. Checking required ports...${NC}"
PORTS=(3000 8001 6379)
for port in "${PORTS[@]}"; do
    if lsof -i :$port &> /dev/null; then
        echo -e "${YELLOW}⚠ Port $port is in use${NC}"
    else
        echo -e "${GREEN}✓ Port $port is available${NC}"
    fi
done

# Check environment
echo ""
echo -e "${YELLOW}6. Checking environment...${NC}"
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ .env file exists${NC}"
    if grep -q "OPENAI_API_KEY" .env; then
        echo -e "${GREEN}✓ OPENAI_API_KEY is set${NC}"
    else
        echo -e "${YELLOW}⚠ OPENAI_API_KEY not in .env (using default)${NC}"
    fi
else
    echo -e "${YELLOW}⚠ .env file not found (using defaults)${NC}"
fi

# Summary
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    Setup Verification Done                   ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${GREEN}Ready to start! Run:${NC}"
echo ""
echo "  ${YELLOW}docker-compose up -d${NC}"
echo ""
echo -e "${GREEN}Then open:${NC}"
echo "  ${YELLOW}http://localhost:3000${NC}"
echo ""
