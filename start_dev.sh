#!/bin/bash

# Creator Agents Platform - Development Startup Script
# Starts backend API and frontend server

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "🚀 Creator Agents Platform - Development Environment"
echo "=================================================================="
echo ""

# Check if services are already running
check_port() {
    if nc -z localhost "$1" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v python &> /dev/null; then
    echo -e "${RED}✗ Python 3.11+ not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python found${NC}"

if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Node.js found${NC}"

# Check database connection
echo ""
echo "🗄️  Checking database..."
export DATABASE_URL="${DATABASE_URL:-postgresql://user:password@localhost:5432/creator_agents}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

# Try to create tables
echo "Creating database tables if they don't exist..."
source venv_local/bin/activate 2>/dev/null || python -m venv venv_local && source venv_local/bin/activate
python scripts/create_tables.py 2>/dev/null || echo "Note: Database setup may require manual configuration"

echo ""
echo "=================================================================="
echo "🎯 Starting services..."
echo "=================================================================="
echo ""

# Start Backend API
echo -e "${BLUE}Starting Backend API...${NC}"
echo "API will be available at: ${BLUE}http://localhost:8000${NC}"
source venv_local/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
sleep 2

# Start Frontend Server
echo ""
echo -e "${BLUE}Starting Frontend Server...${NC}"
echo "Frontend will be available at: ${BLUE}http://localhost:3000${NC}"
npm start &
FRONTEND_PID=$!
sleep 2

echo ""
echo "=================================================================="
echo -e "${GREEN}✓ Services Started!${NC}"
echo "=================================================================="
echo ""
echo "📍 Frontend: http://localhost:3000"
echo "🔌 API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for signals
trap cleanup SIGINT SIGTERM

cleanup() {
    echo ""
    echo "Shutting down services..."
    kill $API_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    wait $API_PID 2>/dev/null || true
    wait $FRONTEND_PID 2>/dev/null || true
    echo "Done!"
    exit 0
}

# Keep script running
wait
