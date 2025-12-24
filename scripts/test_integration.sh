#!/bin/bash

# Integration Test Script for Creator Onboarding ↔ Creator Agents Platform
# This script verifies the complete integration flow

set -e  # Exit on error

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================="
echo "Integration Test: Onboarding → Agents"
echo "========================================="
echo ""

# Step 1: Verify shared services
echo -e "${BLUE}Step 1: Verifying shared services...${NC}"
if docker ps | grep -q "shared-postgres-db" && \
   docker ps | grep -q "shared-redis" && \
   docker ps | grep -q "shared-redpanda"; then
    echo -e "${GREEN}✅ Shared services running${NC}"
else
    echo -e "${RED}❌ Shared services not running${NC}"
    echo "Start with: cd ../agents-shared-services && docker-compose -f docker-compose.shared.yml up -d"
    exit 1
fi
echo ""

# Step 2: Verify creator-agents-platform
echo -e "${BLUE}Step 2: Verifying creator-agents-platform...${NC}"
if docker ps | grep -q "creator-agents-api" && \
   docker ps | grep -q "creator-agents-high-priority-consumer"; then
    echo -e "${GREEN}✅ Creator-agents-platform running${NC}"
else
    echo -e "${RED}❌ Creator-agents-platform not running${NC}"
    echo "Start with: docker-compose up -d"
    exit 1
fi
echo ""

# Step 3: Verify creator-onboarding-service
echo -e "${BLUE}Step 3: Verifying creator-onboarding-service...${NC}"
if docker ps | grep -q "creator-onboarding-backend"; then
    echo -e "${GREEN}✅ Creator-onboarding-service running${NC}"
else
    echo -e "${YELLOW}⚠️  Creator-onboarding-service not running${NC}"
    echo "Start with: cd ../creator-onboarding-service && docker-compose up -d"
    # Don't exit - might want to test just the consumer
fi
echo ""

# Step 4: Check Redpanda topics
echo -e "${BLUE}Step 4: Checking Redpanda topics...${NC}"
if docker exec shared-redpanda rpk topic list | grep -q "creator_onboarded"; then
    echo -e "${GREEN}✅ creator_onboarded topic exists${NC}"
else
    echo -e "${YELLOW}⚠️  creator_onboarded topic doesn't exist (will be auto-created on first publish)${NC}"
fi
echo ""

# Step 5: Check consumer group
echo -e "${BLUE}Step 5: Checking consumer groups...${NC}"
docker exec shared-redpanda rpk group list 2>/dev/null || echo -e "${YELLOW}⚠️  No consumer groups yet${NC}"
echo ""

# Step 6: Check high-priority consumer logs
echo -e "${BLUE}Step 6: Checking high-priority consumer status...${NC}"
if docker logs creator-agents-high-priority-consumer 2>&1 | grep -q "EventConsumerService initialized"; then
    echo -e "${GREEN}✅ High-priority consumer initialized${NC}"
    if docker logs creator-agents-high-priority-consumer 2>&1 | grep -q "Registered handler CreatorOnboardedHandler"; then
        echo -e "${GREEN}✅ CreatorOnboardedHandler registered${NC}"
    else
        echo -e "${RED}❌ CreatorOnboardedHandler NOT registered${NC}"
    fi
else
    echo -e "${RED}❌ High-priority consumer not initialized${NC}"
    echo "Check logs: docker logs creator-agents-high-priority-consumer"
fi
echo ""

# Step 7: Check database connectivity
echo -e "${BLUE}Step 7: Checking database connectivity...${NC}"
if docker exec shared-postgres-db psql -U postgres -d creator_agents -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Database creator_agents accessible${NC}"

    # Check if workflows table exists
    if docker exec shared-postgres-db psql -U postgres -d creator_agents -c "\dt workflows" 2>&1 | grep -q "workflows"; then
        echo -e "${GREEN}✅ workflows table exists${NC}"
    else
        echo -e "${YELLOW}⚠️  workflows table doesn't exist (run migrations)${NC}"
    fi

    # Check if worker_tasks table exists
    if docker exec shared-postgres-db psql -U postgres -d creator_agents -c "\dt worker_tasks" 2>&1 | grep -q "worker_tasks"; then
        echo -e "${GREEN}✅ worker_tasks table exists${NC}"
    else
        echo -e "${YELLOW}⚠️  worker_tasks table doesn't exist (run migrations)${NC}"
    fi
else
    echo -e "${RED}❌ Database creator_agents not accessible${NC}"
fi
echo ""

# Step 8: Test event flow (if agent_id provided)
if [ -n "$1" ]; then
    AGENT_ID=$1
    echo -e "${BLUE}Step 8: Testing event flow with agent ID: ${AGENT_ID}${NC}"

    # Activate agent
    echo "Activating agent..."
    RESPONSE=$(curl -s -X POST http://localhost:8001/agents/${AGENT_ID}/activate)

    if echo "$RESPONSE" | grep -q "success"; then
        echo -e "${GREEN}✅ Agent activated successfully${NC}"
        echo "Response: $RESPONSE"

        # Wait for event processing
        echo "Waiting 5 seconds for event processing..."
        sleep 5

        # Check if event was consumed
        if docker logs creator-agents-high-priority-consumer --since 10s 2>&1 | grep -q "Processing creator_onboarded event"; then
            echo -e "${GREEN}✅ Event consumed by high-priority consumer${NC}"

            if docker logs creator-agents-high-priority-consumer --since 10s 2>&1 | grep -q "MainAgent triggered"; then
                echo -e "${GREEN}✅ MainAgent triggered${NC}"

                if docker logs creator-agents-high-priority-consumer --since 10s 2>&1 | grep -q "Successfully processed"; then
                    echo -e "${GREEN}✅ Event processed successfully${NC}"
                else
                    echo -e "${RED}❌ Event processing failed${NC}"
                fi
            else
                echo -e "${RED}❌ MainAgent not triggered${NC}"
            fi
        else
            echo -e "${RED}❌ Event not consumed${NC}"
            echo "Check Redpanda topic: docker exec shared-redpanda rpk topic consume creator_onboarded --num 1"
        fi

        # Check workflow created
        echo ""
        echo "Checking if workflow was created..."
        WORKFLOW_COUNT=$(docker exec shared-postgres-db psql -U postgres -d creator_agents -t -c \
            "SELECT COUNT(*) FROM workflows WHERE created_at > NOW() - INTERVAL '1 minute';" 2>/dev/null | tr -d ' ')

        if [ "$WORKFLOW_COUNT" -gt 0 ]; then
            echo -e "${GREEN}✅ Workflow created (${WORKFLOW_COUNT} workflows in last minute)${NC}"

            # Show latest workflow
            echo ""
            echo "Latest workflow:"
            docker exec shared-postgres-db psql -U postgres -d creator_agents -c \
                "SELECT id, creator_id, purpose, workflow_type, version, created_at
                 FROM workflows
                 ORDER BY created_at DESC
                 LIMIT 1;"
        else
            echo -e "${YELLOW}⚠️  No workflow created in last minute${NC}"
        fi

        # Check worker tasks
        echo ""
        echo "Checking if worker tasks were created..."
        TASK_COUNT=$(docker exec shared-postgres-db psql -U postgres -d creator_agents -t -c \
            "SELECT COUNT(*) FROM worker_tasks WHERE created_at > NOW() - INTERVAL '1 minute';" 2>/dev/null | tr -d ' ')

        if [ "$TASK_COUNT" -gt 0 ]; then
            echo -e "${GREEN}✅ Worker tasks created (${TASK_COUNT} tasks in last minute)${NC}"

            # Show latest tasks
            echo ""
            echo "Latest worker tasks:"
            docker exec shared-postgres-db psql -U postgres -d creator_agents -c \
                "SELECT id, task_type, status, assigned_agent_id
                 FROM worker_tasks
                 ORDER BY created_at DESC
                 LIMIT 5;"
        else
            echo -e "${YELLOW}⚠️  No worker tasks created in last minute${NC}"
        fi

    else
        echo -e "${RED}❌ Agent activation failed${NC}"
        echo "Response: $RESPONSE"
    fi
else
    echo -e "${BLUE}Step 8: Skipped (no agent_id provided)${NC}"
    echo "To test event flow, run: ./scripts/test_integration.sh <agent_id>"
fi
echo ""

# Summary
echo "========================================="
echo "Integration Test Summary"
echo "========================================="
echo ""
echo -e "${GREEN}✅ = Working${NC}"
echo -e "${YELLOW}⚠️  = Warning (may be expected)${NC}"
echo -e "${RED}❌ = Error (needs attention)${NC}"
echo ""
echo "For detailed logs:"
echo "  - Consumer: docker logs creator-agents-high-priority-consumer"
echo "  - API: docker logs creator-agents-api"
echo "  - Redpanda: docker exec shared-redpanda rpk topic consume creator_onboarded --num 5"
echo ""
echo "========================================="
