#!/bin/bash

# Creator Agents Platform - Docker Startup Script
# Starts all services: PostgreSQL, Redis, Backend API, Worker, Frontend

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Creator Agents Platform - Docker Startup                   ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

if ! docker ps &> /dev/null; then
    echo "❌ Docker daemon is not running. Please start Docker."
    exit 1
fi

echo -e "${GREEN}✓ Docker is running${NC}"
echo ""

# Build and start services
echo -e "${YELLOW}📦 Building and starting services...${NC}"
echo ""

docker-compose up -d

echo ""
echo -e "${GREEN}✓ Services started!${NC}"
echo ""

# Wait a bit for services to come up
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check health
echo ""
echo -e "${BLUE}📋 Service Status:${NC}"
echo ""

# Check PostgreSQL
if docker exec creator-agents-db pg_isready -U postgres &> /dev/null; then
    echo -e "${GREEN}✓ PostgreSQL${NC} - Ready on port 5432"
else
    echo -e "${YELLOW}⏳ PostgreSQL${NC} - Starting up..."
fi

# Check Redis
if docker exec creator-agents-redis redis-cli ping &> /dev/null; then
    echo -e "${GREEN}✓ Redis${NC} - Ready on port 6379"
else
    echo -e "${YELLOW}⏳ Redis${NC} - Starting up..."
fi

# Wait for API
echo -e "${YELLOW}⏳ API - Starting up...${NC}"
sleep 3

if curl -s http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}✓ Backend API${NC} - Ready on port 8000"
else
    echo -e "${YELLOW}⏳ Backend API${NC} - Starting up..."
fi

# Check Frontend
if curl -s http://localhost:3000/api/health > /dev/null; then
    echo -e "${GREEN}✓ Frontend${NC} - Ready on port 3000"
else
    echo -e "${YELLOW}⏳ Frontend${NC} - Starting up..."
fi

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    All Services Ready!                       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BLUE}📍 Access Points:${NC}"
echo -e "   ${GREEN}Frontend${NC}:     ${BLUE}http://localhost:3000${NC}"
echo -e "   ${GREEN}API${NC}:          ${BLUE}http://localhost:8000${NC}"
echo -e "   ${GREEN}API Docs${NC}:     ${BLUE}http://localhost:8000/docs${NC}"
echo -e "   ${GREEN}Database${NC}:     ${BLUE}localhost:5432${NC}"
echo -e "   ${GREEN}Redis${NC}:        ${BLUE}localhost:6379${NC}"
echo ""

echo -e "${BLUE}📚 Useful Commands:${NC}"
echo "   View logs:       ${YELLOW}docker-compose logs -f${NC}"
echo "   View API logs:   ${YELLOW}docker-compose logs -f api${NC}"
echo "   View frontend:   ${YELLOW}docker-compose logs -f frontend${NC}"
echo "   Stop services:   ${YELLOW}docker-compose down${NC}"
echo "   Stop & remove:   ${YELLOW}docker-compose down -v${NC}"
echo ""

echo -e "${BLUE}🧪 First Test:${NC}"
echo "   1. Open ${BLUE}http://localhost:3000${NC} in your browser"
echo "   2. Go to 'Onboard Creator' tab"
echo "   3. Enter username: ${YELLOW}ajay_shenoy${NC}"
echo "   4. Click 'Onboard Creator'"
echo "   5. Check dashboard stats update"
echo ""

# Keep showing logs
echo -e "${YELLOW}Showing live logs (Press Ctrl+C to stop):${NC}"
echo ""
docker-compose logs -f
