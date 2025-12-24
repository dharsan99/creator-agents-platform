# Supervisor-Worker Architecture Guide

**Version:** 1.0.0
**Date:** 2025-12-17
**Status:** ✅ Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Key Components](#key-components)
4. [How It Works](#how-it-works)
5. [API Reference](#api-reference)
6. [Deployment Guide](#deployment-guide)
7. [Configuration](#configuration)
8. [Testing](#testing)
9. [Troubleshooting](#troubleshooting)
10. [Migration from Old Architecture](#migration-from-old-architecture)

---

## Overview

### What is the Supervisor-Worker Architecture?

The Supervisor-Worker pattern is a **generic, purpose-agnostic multi-agent orchestration system** that enables AI agents to work together hierarchically:

- **MainAgent (Supervisor)**: Global orchestrator that plans workflows and delegates tasks
- **WorkerAgents**: Specialized agents that execute delegated tasks using tools
- **Dynamic Tool System**: Runtime tool calling with 30-second timeout and retry logic
- **Workflow Versioning**: Full change tracking with rollback capability
- **Human-in-Loop**: Escalation system for complex scenarios

### Key Features

✅ **Purpose-Agnostic**: Works for ANY creator goal (sales, coaching, content, community, etc.)
✅ **Dynamic Tool Discovery**: Plans with available tools, logs missing ones
✅ **Event-Driven**: Redpanda with 5 consumer groups and priority-based routing
✅ **Multi-Worker Support**: Multiple specialized workers per creator
✅ **Workflow Versioning**: Full version history with diff tracking
✅ **On-Demand Data Fetching**: No database syncing between services
✅ **Human Escalation**: API-ready dashboard integration

### What Changed from Old Architecture?

| **Old Architecture** | **New Architecture** |
|----------------------|----------------------|
| Local creator onboarding | Onboarding in external service |
| Per-creator agents | Single global MainAgent |
| Action planning only | Runtime tool calling |
| No workflow management | Workflow versioning |
| No task delegation | Supervisor → Worker pattern |
| No human escalation | Full conversation API |

---

## Architecture

### System Overview

```
creator-onboarding-service
        ↓ (creator onboarded + worker agents created)
Redpanda Topics & Consumer Groups:
  - creator_onboarded (high-priority group)
  - supervisor_tasks (worker-task group)
  - task_results (worker-task group)
  - workflow_events (batch group)
  - analytics_events (analytics group)
  - audit_events (audit group)
        ↓
creator-agents-platform
        ↓
MainAgent (Global Supervisor)
  - Analyzes creator purpose
  - Discovers available tools
  - Plans workflow with LLM
  - Versions workflow changes
  - Delegates to workers
  - Monitors metrics
        ↓
WorkerAgent 1 (Email)  WorkerAgent 2 (WhatsApp)  WorkerAgent 3 (Analytics)
  - Receives tasks
  - Checks tool availability
  - Executes with tools
  - Reports completion
  - Escalates if needed
```

### Data Flow

```
1. Creator Onboarded Event → MainAgent
2. MainAgent → Fetch creator profile (on-demand)
3. MainAgent → Discover available tools
4. MainAgent → Plan workflow with LLM
5. MainAgent → Create workflow (versioned)
6. MainAgent → Delegate tasks to workers
7. WorkerAgent → Execute task with tools
8. WorkerAgent → Report completion
9. MainAgent → Update workflow based on results
10. (Optional) WorkerAgent → Escalate to human
```

---

## Key Components

### 1. MainAgent (Global Supervisor)

**Location:** `app/agents/main_agent.py`

**Purpose:** Purpose-agnostic global orchestrator for ALL creators

**Responsibilities:**
- Analyze creator purpose and goals
- Discover available tools dynamically
- Plan multi-stage workflows using LLM
- Create versioned workflow records
- Delegate tasks to worker agents
- Monitor metrics and adjust workflow
- Handle workflow state changes

**Configuration:**
```python
{
    "agent_class": "app.agents.main_agent:MainAgent",
    "purpose": "orchestration",
    "capabilities": [
        "workflow_planning",
        "tool_discovery",
        "task_delegation",
        "metric_monitoring",
        "dynamic_adjustment"
    ]
}
```

**Events Handled:**
- `creator_onboarded` - Initialize workflow for new creator
- `workflow_metric_update` - Adjust based on performance
- `worker_task_completed` - Check if stage is complete
- `workflow_state_change` - Handle state transitions

### 2. WorkerAgent (Task Executor)

**Location:** `app/agents/worker_agent.py`

**Purpose:** Base class for specialized worker agents

**Responsibilities:**
- Receive task assignments from MainAgent
- Route to task-specific handlers
- Execute tasks using available tools
- Generate content with LLM
- Detect and escalate complex scenarios
- Report completion/failure to MainAgent

**Task Types:**
- `create_intro_email` - Generate and send introduction email
- `create_followup_email` - Generate and send follow-up
- `create_whatsapp_message` - Create WhatsApp message
- `send_whatsapp` - Send WhatsApp message
- `collect_metrics` - Gather analytics
- `generate_content` - Create content
- (Custom task types can be added)

**Example:**
```python
class EmailWorker(WorkerAgent):
    """Specialized worker for email campaigns."""

    def handle_create_intro_email(self, task: WorkerTask):
        # 1. Get consumer context
        consumer_ctx = self.call_tool("get_consumer_context", ...)

        # 2. Generate email with LLM
        email = self.generate_email_with_llm(...)

        # 3. Send email
        result = self.call_tool("send_email", ...)

        # 4. Update consumer stage
        self.call_tool("update_consumer_stage", ...)

        return {"success": True, "message_id": result["message_id"]}
```

### 3. Dynamic Tool System

**Location:** `app/domain/tools/`

**Purpose:** Runtime tool execution with timeout and retry

**Components:**
- **BaseTool**: Interface all tools implement
- **ToolRegistry**: Self-registering tool discovery
- **ToolExecutor**: Executes tools with timeout/retry
- **MissingToolLogger**: Tracks unavailable tools

**Available Tools:**

| Tool | Category | Timeout | Retry |
|------|----------|---------|-------|
| send_email | Communication | 30s | Yes |
| send_whatsapp | Communication | 30s | Yes |
| send_sms | Communication | 30s | Yes |
| escalate_to_human | Communication | 15s | No |
| get_consumer_context | Data | 10s | Yes |
| update_consumer_stage | Data | 10s | Yes |
| search_faq | Data | 15s | Yes |

**Adding New Tools:**
```python
from app.domain.tools.base import BaseTool, ToolResult, ToolCategory

class MyCustomTool(BaseTool):
    name = "my_custom_tool"
    description = "Does something useful"
    category = ToolCategory.CUSTOM
    timeout_seconds = 30

    def check_availability(self) -> bool:
        # Check if dependencies available
        return True

    def execute(self, **kwargs) -> ToolResult:
        # Execute tool logic
        return ToolResult(success=True, data={...})

# Register tool
from app.domain.tools.registry import get_registry
get_registry().register_tool(MyCustomTool())
```

### 4. Workflow Versioning

**Location:** `app/domain/workflow/`

**Purpose:** Track all workflow changes with full history

**Models:**
- **Workflow**: Current workflow definition
- **WorkflowVersion**: Historical version record
- **WorkflowExecution**: Runtime state

**Example:**
```python
from app.domain.workflow.service import WorkflowService

service = WorkflowService(session)

# Create workflow (v1)
workflow = service.create_workflow({
    "creator_id": creator_id,
    "purpose": "coaching_program",
    "stages": {...},
    "metrics_thresholds": {...}
})

# Update workflow (creates v2)
updated = service.update_workflow(
    workflow.id,
    changes={"stages": {...}},  # Modified stages
    reason="Added personalization based on engagement metrics",
    changed_by="MainAgent"
)

# Get history
history = service.get_workflow_history(workflow.id)
# Returns: [Version 1, Version 2, ...]

# Rollback to v1
rolled_back = service.rollback_workflow(
    workflow.id,
    to_version=1,
    reason="Performance decreased with v2 changes"
)
```

### 5. Human-in-Loop

**Location:** `app/domain/conversations/`

**Purpose:** Escalate complex scenarios to human dashboard

**Flow:**
```
1. WorkerAgent detects complex scenario (complaint, custom request, etc.)
2. WorkerAgent calls escalate_to_human tool
3. ConversationThread created
4. Workflow paused for this consumer
5. Human receives notification (dashboard)
6. Human exchanges messages with consumer
7. Human resolves thread
8. Workflow resumes with resolution context
```

**API Endpoints:**
- `GET /conversations` - List threads needing attention
- `GET /conversations/{id}` - Get thread details
- `GET /conversations/{id}/messages` - Get conversation history
- `POST /conversations/{id}/messages` - Human sends message
- `POST /conversations/{id}/resolve` - Resolve and resume workflow

**Example:**
```python
# In WorkerAgent
if self.should_escalate(consumer_message):
    result = self.call_tool(
        "escalate_to_human",
        creator_id=creator_id,
        consumer_id=consumer_id,
        workflow_execution_id=execution_id,
        agent_id=self.agent_id,
        reason="pricing_negotiation",
        context={
            "workflow_id": workflow_id,
            "current_stage": "followup",
            "consumer_question": "Can I get a payment plan?"
        },
        consumer_message="Can I get a custom 6-month payment plan?"
    )
    # Workflow paused, human notified
```

---

## How It Works

### Flow 1: Creator Onboarded

```
1. creator-onboarding-service publishes creator_onboarded event to Redpanda
   {
     "creator_id": "uuid",
     "worker_agent_ids": ["uuid1", "uuid2"],
     "consumers": ["uuid3", "uuid4", "uuid5"],
     "purpose": "coaching_program",
     "goal": "Maximize enrollment in 30-day coaching",
     "start_date": "2025-01-01",
     "end_date": "2025-01-31"
   }

2. High-priority consumer picks up event

3. MainAgent.should_act() → True (orchestration event)

4. MainAgent.plan_actions():
   a. Fetch creator profile from onboarding service
   b. Discover available tools (send_email, send_whatsapp, etc.)
   c. Plan workflow with LLM:
      - Stage 1 (Day 1): Send personalized introduction
      - Stage 2 (Day 3): Follow up if opened but not responded
      - Stage 3 (Day 7): Special offer if engaged
      - Stage 4 (Day 14): Final reminder
      - Decision points based on metrics
   d. Create Workflow v1 in database
   e. Create WorkflowExecution
   f. Log any missing tools (e.g., "send_linkedin_message")

5. MainAgent delegates initial tasks:
   - Creates WorkerTask for each consumer
   - Publishes to supervisor_tasks topic
   - Tasks distributed round-robin to worker agents

6. WorkerAgent receives task via worker-task consumer

7. WorkerAgent executes:
   a. Calls get_consumer_context tool
   b. Calls generate_email_with_llm (LLM creates personalized email)
   c. Calls send_email tool
   d. Calls update_consumer_stage tool
   e. Reports completion to MainAgent

8. MainAgent receives completion event

9. MainAgent checks if stage complete (all consumers contacted)

10. MainAgent advances workflow to next stage
```

### Flow 2: Workflow Adjustment

```
1. Consumer opens email → email_opened event

2. MainAgent receives workflow_metric_update event

3. MainAgent analyzes metrics:
   - Email open rate: 65% (above threshold)
   - Click-through rate: 12% (below threshold)
   - Decision: Adjust follow-up messaging to emphasize urgency

4. MainAgent updates workflow:
   workflow_service.update_workflow(
       workflow_id,
       changes={"stages": {"followup": {"actions": ["Send urgent CTA email"]}}},
       reason="Low CTR - adding urgency to follow-up",
       changed_by="MainAgent"
   )
   # Creates Workflow v2

5. MainAgent delegates new followup tasks with updated instructions

6. Workflow execution continues with v2 logic
```

### Flow 3: Human Escalation

```
1. Consumer replies: "I need a custom payment plan for 12 months"

2. WorkerAgent analyzes with LLM:
   result = self.should_escalate(consumer_message)
   # Returns: True (pricing_negotiation)

3. WorkerAgent calls escalate_to_human tool:
   - Creates ConversationThread
   - Pauses workflow for this consumer
   - Adds consumer message to thread
   - Sends notification (TODO: webhook to dashboard)

4. Human receives notification in dashboard

5. Human views conversation:
   GET /conversations/{thread_id}/messages

6. Human responds:
   POST /conversations/{thread_id}/messages
   {
     "sender_id": "human_uuid",
     "content": "I can offer a 10-month plan at $X/month. Would that work?"
   }

7. Consumer and human exchange messages

8. Human resolves:
   POST /conversations/{thread_id}/resolve
   {
     "resolution": {
       "outcome": "custom_payment_plan",
       "details": "10-month plan at $X/month agreed",
       "next_steps": "Send payment plan link"
     },
     "resume_workflow": true,
     "resolved_by": "human_uuid"
   }

9. Workflow resumes with resolution context

10. WorkerAgent sends payment plan link as next action
```

---

## API Reference

### Onboarding Endpoints

#### GET /onboarding/profile/{creator_id}
Fetch creator profile (proxied from onboarding service)

**Response:**
```json
{
  "creator_id": "uuid",
  "external_username": "john_doe",
  "name": "John Doe",
  "email": "john@example.com",
  "services": [...],
  "sales_pitch": "Transform your life with personalized coaching...",
  "target_audience": "Professionals seeking career growth"
}
```

#### GET /onboarding/agents/{creator_id}
List agents for creator (includes MainAgent + creator-specific workers)

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "MainAgent",
    "creator_id": null,
    "enabled": true,
    "implementation": "simple"
  },
  {
    "id": "uuid",
    "name": "EmailWorker",
    "creator_id": "uuid",
    "enabled": true,
    "implementation": "simple"
  }
]
```

#### POST /onboarding/admin/deploy-main-agent
Deploy global MainAgent (admin only, run once)

**Response:**
```json
{
  "success": true,
  "message": "MainAgent deployed successfully",
  "agent_id": "uuid",
  "agent_name": "MainAgent",
  "enabled": true,
  "triggers": [
    "creator_onboarded",
    "workflow_metric_update",
    "worker_task_completed",
    "workflow_state_change"
  ]
}
```

### Conversation Endpoints

#### GET /conversations
List conversation threads (default: waiting for human)

**Query Parameters:**
- `status` (optional): Filter by status (active, waiting_human, resolved, etc.)
- `creator_id` (optional): Filter by creator
- `limit` (default: 100, max: 500): Max threads to return

**Response:**
```json
[
  {
    "id": "uuid",
    "creator_id": "uuid",
    "consumer_id": "uuid",
    "workflow_execution_id": "uuid",
    "agent_id": "uuid",
    "status": "waiting_human",
    "escalation_reason": "pricing_negotiation",
    "context": {...},
    "created_at": "2025-01-01T12:00:00Z",
    "message_count": 3
  }
]
```

#### GET /conversations/{thread_id}
Get conversation thread details

#### GET /conversations/{thread_id}/messages
Get messages in conversation

**Response:**
```json
[
  {
    "id": "uuid",
    "thread_id": "uuid",
    "sender_type": "consumer",
    "sender_id": "uuid",
    "content": "Can I get a custom payment plan?",
    "metadata": {},
    "created_at": "2025-01-01T12:00:00Z"
  },
  {
    "id": "uuid",
    "thread_id": "uuid",
    "sender_type": "human",
    "sender_id": "uuid",
    "content": "I can offer a 10-month plan...",
    "created_at": "2025-01-01T12:05:00Z"
  }
]
```

#### POST /conversations/{thread_id}/messages
Human sends message

**Request:**
```json
{
  "sender_id": "uuid",
  "content": "I can offer a 10-month payment plan at $500/month",
  "metadata": {}
}
```

#### POST /conversations/{thread_id}/resolve
Resolve conversation and resume workflow

**Request:**
```json
{
  "resolution": {
    "outcome": "custom_payment_plan",
    "details": "10-month plan at $500/month",
    "next_steps": "Send payment link"
  },
  "resume_workflow": true,
  "resolved_by": "uuid"
}
```

---

## Deployment Guide

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- PostgreSQL 15+ (shared database)
- Redpanda (Kafka-compatible)
- OpenAI API key

### Step 1: Setup Shared Infrastructure

If using `agents-shared-services`:

```bash
cd /path/to/agents-shared-services
docker-compose up -d
```

This starts:
- PostgreSQL (shared-postgres-db)
- Redis (shared-redis)
- Redpanda (shared-redpanda)

### Step 2: Run Database Migration

```bash
cd /path/to/creator-agents-platform

# Create tables
python scripts/migrate_supervisor_worker.py
```

Expected output:
```
✅ Tables created successfully!

New Tables for Supervisor-Worker Architecture:

Phase 1 - Tool Calling:
  - missing_tool_requests

Phase 3 - Workflow Versioning:
  - workflows
  - workflow_versions
  - workflow_executions

Phase 4 - Worker Tasks:
  - worker_tasks

Phase 5 - Human-in-Loop:
  - conversation_threads
  - messages
```

### Step 3: Deploy MainAgent

**Option A: Via Script**
```bash
python scripts/deploy_main_agent.py
```

**Option B: Via API**
```bash
curl -X POST http://localhost:8000/onboarding/admin/deploy-main-agent
```

Expected output:
```
✅ MainAgent deployed successfully!
   ID: <uuid>
   Triggers: 4
   Status: Enabled
```

### Step 4: Start Consumer Services

```bash
docker-compose up -d high-priority-consumer worker-task-consumer
```

This starts:
- **high-priority-consumer**: Processes creator_onboarded events
- **worker-task-consumer**: Processes worker task assignments

### Step 5: Start API Server

```bash
docker-compose up -d api
```

Or for development:
```bash
python app/main.py
```

### Step 6: Verify Deployment

```bash
# Check health
curl http://localhost:8000/health

# Verify MainAgent
curl http://localhost:8000/onboarding/agents/<creator_id>
```

---

## Configuration

### Environment Variables

**Required:**
```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@shared-postgres-db:5432/creator_agents

# Redis
REDIS_URL=redis://shared-redis:6379/0

# Redpanda
REDPANDA_BROKERS=shared-redpanda:9092

# OpenAI (for LLM-based planning)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview

# Onboarding Service
ONBOARDING_SERVICE_URL=http://creator-onboarding-backend:8000

# Application
ENV=production
LOG_LEVEL=INFO
```

**Optional:**
```bash
# Twilio (for WhatsApp/SMS)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# AWS SES (for Email)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
SES_SENDER_EMAIL=noreply@example.com
```

### Consumer Group Configuration

**Location:** `app/infra/events/consumer_groups.py`

Modify concurrency levels based on load:

```python
HIGH_PRIORITY_GROUP = ConsumerGroupConfig(
    group_id="high-priority-consumer-group",
    topics=["creator_onboarded", "critical_alerts"],
    concurrency=10,  # Increase for higher throughput
)

WORKER_TASK_GROUP = ConsumerGroupConfig(
    group_id="worker-task-consumer-group",
    topics=["supervisor_tasks", "task_results"],
    concurrency=8,  # Adjust based on worker load
)
```

---

## Testing

### Unit Tests

Test individual components:

```bash
# Test tools
pytest tests/domain/tools/

# Test MainAgent logic
pytest tests/agents/test_main_agent.py

# Test WorkflowService
pytest tests/domain/workflow/
```

### Integration Tests

Test multi-component flows:

```bash
# Test creator onboarding → MainAgent → Worker flow
pytest tests/integration/test_supervisor_worker_flow.py

# Test human escalation
pytest tests/integration/test_human_escalation.py
```

### End-to-End Test

Simulate complete workflow:

```python
# scripts/test_supervisor_worker_e2e.py

# 1. Deploy MainAgent
# 2. Publish creator_onboarded event
# 3. Verify workflow created
# 4. Verify tasks delegated
# 5. Simulate worker completion
# 6. Verify workflow progression
```

### Manual Testing

**Test creator onboarding:**
```bash
# Publish test event to Redpanda
python scripts/publish_test_event.py creator_onboarded
```

**Test human escalation:**
```bash
# Create test conversation
curl -X POST http://localhost:8000/conversations/{thread_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"sender_id": "test_human_uuid", "content": "Test response"}'
```

---

## Troubleshooting

### MainAgent Not Triggering

**Symptoms:** creator_onboarded event consumed but no workflow created

**Checks:**
1. Verify MainAgent deployed:
   ```bash
   curl http://localhost:8000/onboarding/agents/<any_creator_id>
   # Should include MainAgent in response
   ```

2. Check MainAgent triggers:
   ```sql
   SELECT * FROM agent_triggers WHERE agent_id = (
     SELECT id FROM agents WHERE name = 'MainAgent'
   );
   # Should have 4 triggers: creator_onboarded, workflow_metric_update, etc.
   ```

3. Check logs:
   ```bash
   docker logs creator-agents-high-priority-consumer
   # Look for: "Routing orchestration event creator_onboarded to MainAgent"
   ```

### Worker Tasks Not Executing

**Symptoms:** Tasks created but not executed

**Checks:**
1. Verify worker-task-consumer running:
   ```bash
   docker ps | grep worker-task-consumer
   ```

2. Check supervisor_tasks topic:
   ```bash
   docker exec shared-redpanda rpk topic consume supervisor_tasks
   # Should see task messages
   ```

3. Check WorkerTask records:
   ```sql
   SELECT status, COUNT(*) FROM worker_tasks GROUP BY status;
   # If many "pending", workers aren't processing
   ```

### Tools Timing Out

**Symptoms:** Actions failing with timeout errors

**Checks:**
1. Check tool execution logs:
   ```bash
   grep "Tool execution timed out" app.log
   ```

2. Increase timeout if needed:
   ```python
   class MyTool(BaseTool):
       timeout_seconds = 60  # Increase from 30
   ```

3. Check external service availability (SES, Twilio, etc.)

### Workflow Not Progressing

**Symptoms:** Workflow stuck on same stage

**Checks:**
1. Check workflow execution status:
   ```sql
   SELECT status, current_stage FROM workflow_executions WHERE id = '<execution_id>';
   ```

2. Check for paused workflows:
   ```sql
   SELECT * FROM workflow_executions WHERE status = 'paused';
   # If paused, check conversation_threads for escalations
   ```

3. Check MainAgent logs for decision logic:
   ```bash
   grep "workflow_metric_update" app.log
   ```

### Human Escalation Not Working

**Symptoms:** escalate_to_human tool succeeds but no thread created

**Checks:**
1. Verify conversation_threads table exists:
   ```sql
   SELECT * FROM conversation_threads LIMIT 1;
   ```

2. Check tool execution result:
   ```python
   # In agent logs, look for:
   # "Escalation successful" with thread_id
   ```

3. Verify API endpoint:
   ```bash
   curl http://localhost:8000/conversations
   # Should return escalated threads
   ```

---

## Migration from Old Architecture

### What to Keep

✅ **Database Tables:**
- creators
- consumers
- consumer_context
- events
- agents (but usage changes)
- agent_triggers
- agent_invocations
- actions

✅ **Domain Logic:**
- BaseAgent interface (still used by WorkerAgents)
- Agent runtime system
- Event processing
- Policy engine

### What to Remove

❌ **Deprecated Code:**
- `app/domain/onboarding/service.py` → Moved to `deprecated/`
- `app/domain/onboarding/llm_service.py` → Moved to `deprecated/`
- `app/infra/external/topmate_client.py` → Moved to `deprecated/`

❌ **Old Endpoints:**
- `POST /onboarding/` → Onboarding in external service
- `POST /onboarding/sync` → Syncing in external service
- `POST /onboarding/deploy-agent/{creator_id}` → Replaced by MainAgent

❌ **Test Scripts:**
- `scripts/test_onboarding.py` → Outdated
- `scripts/test_e2e_agent_deployment.py` → Needs updating

### Migration Steps

1. **Backup Database:**
   ```bash
   pg_dump creator_agents > backup_before_migration.sql
   ```

2. **Run Migration:**
   ```bash
   python scripts/migrate_supervisor_worker.py
   ```

3. **Deploy MainAgent:**
   ```bash
   python scripts/deploy_main_agent.py
   ```

4. **Update External Service:**
   - Ensure creator-onboarding-service publishes creator_onboarded events
   - Update agent creation to create worker agents (not sales agents)

5. **Start New Consumers:**
   ```bash
   docker-compose up -d high-priority-consumer worker-task-consumer
   ```

6. **Test:**
   - Trigger creator_onboarded event
   - Verify workflow created
   - Verify tasks delegated and executed

7. **Decommission Old Code:**
   - Stop old agent consumers (if any)
   - Archive deprecated files
   - Update documentation

### Rollback Plan

If migration fails:

1. **Stop new consumers:**
   ```bash
   docker-compose stop high-priority-consumer worker-task-consumer
   ```

2. **Disable MainAgent:**
   ```sql
   UPDATE agents SET enabled = FALSE WHERE name = 'MainAgent';
   ```

3. **Restore old endpoints:**
   - Revert `app/api/routers/onboarding.py`
   - Move deprecated files back

4. **Restore database (if needed):**
   ```bash
   psql creator_agents < backup_before_migration.sql
   ```

---

## Appendix

### Glossary

- **MainAgent**: Global supervisor agent that orchestrates workflows
- **WorkerAgent**: Specialized agent that executes delegated tasks
- **Workflow**: Multi-stage plan for achieving creator goals
- **WorkflowVersion**: Historical record of workflow changes
- **WorkflowExecution**: Runtime state of workflow execution
- **WorkerTask**: Task delegated from MainAgent to WorkerAgent
- **ConversationThread**: Escalated conversation requiring human intervention
- **Tool**: Executable capability (send email, fetch data, etc.)
- **ToolRegistry**: Central registry of available tools
- **Consumer Group**: Redpanda consumer group for event processing

### Key Files Reference

**Agents:**
- `app/agents/main_agent.py` - MainAgent (supervisor)
- `app/agents/worker_agent.py` - WorkerAgent base class

**Tools:**
- `app/domain/tools/base.py` - Tool interface
- `app/domain/tools/registry.py` - Tool registry
- `app/domain/tools/communication.py` - Communication tools
- `app/domain/tools/data.py` - Data tools

**Workflow:**
- `app/domain/workflow/models.py` - Workflow models
- `app/domain/workflow/service.py` - Workflow service

**Tasks:**
- `app/domain/tasks/models.py` - WorkerTask model
- `app/domain/tasks/service.py` - Task service

**Conversations:**
- `app/domain/conversations/models.py` - Conversation models
- `app/api/routers/conversations.py` - Conversation API

**Events:**
- `app/infra/events/schemas.py` - Event schemas
- `app/infra/events/consumer_groups.py` - Consumer configurations
- `app/services/event_consumer_service.py` - Event consumer
- `app/services/worker_task_consumer.py` - Task consumer

**API:**
- `app/api/routers/onboarding.py` - Onboarding/agent endpoints
- `app/api/routers/conversations.py` - Conversation endpoints

**Scripts:**
- `scripts/migrate_supervisor_worker.py` - Database migration
- `scripts/deploy_main_agent.py` - Deploy MainAgent

### Related Documentation

- [Tool Development Guide](TOOL_DEVELOPMENT_GUIDE.md) - How to create custom tools
- [Worker Agent Guide](WORKER_AGENT_GUIDE.md) - How to create specialized workers
- [Workflow Planning Guide](WORKFLOW_PLANNING_GUIDE.md) - How MainAgent plans workflows
- [API Documentation](API_REFERENCE.md) - Complete API reference

---

**Questions or Issues?**

1. Check [Troubleshooting](#troubleshooting) section above
2. Review logs in `/var/log/creator-agents/`
3. Open issue on GitHub
4. Contact platform team

**Version History:**
- v1.0.0 (2025-12-17): Initial supervisor-worker architecture
