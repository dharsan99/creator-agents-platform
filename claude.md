# Creator Agents Platform - Project Overview

## Project Summary

**Creator Agents Platform** - An event-driven agentic system that helps creators automatically engage with and convert leads using AI agents. The platform onboards creators, generates LLM-optimized sales profiles, and deploys personalized sales agents that respond to consumer behavior in real-time.

**Status:** ✅ MVP Complete - Onboarding, agent deployment, and event processing fully functional

**Last Updated:** 2025-12-08

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- PostgreSQL 15+
- OpenAI API key (gpt-5-nano-2025-08-07)

### Running the System

```bash
# 1. Start database
docker-compose up -d postgres

# 2. Create tables
docker run --rm --network host -v "$PWD:/app" -w /app --env-file .env \
  -e DATABASE_URL="postgresql://postgres:postgres@localhost:5432/creator_agents" \
  creator-agents-api python scripts/create_tables.py

# 3. Onboard a creator
docker run --rm --network host -v "$PWD:/app" -w /app --env-file .env \
  -e DATABASE_URL="postgresql://postgres:postgres@localhost:5432/creator_agents" \
  creator-agents-api python scripts/test_onboarding.py

# 4. Test full integration
docker run --rm --network host -v "$PWD:/app" -w /app --env-file .env \
  -e DATABASE_URL="postgresql://postgres:postgres@localhost:5432/creator_agents" \
  creator-agents-api python scripts/test_e2e_agent_deployment.py
```

---

## Architecture Overview

### Core Concepts

1. **Event-Driven Architecture**
   - Events trigger agents (page_view, service_click, booking_created, etc.)
   - Events update consumer context (behavior tracking)
   - Agent invocations queued via RQ background jobs

2. **Creator Profiles**
   - External data fetched from Topmate API
   - LLM generates comprehensive, sales-optimized documentation
   - Profile includes: sales pitch, agent instructions, value propositions, objection handling
   - Stored in `creator_profiles` table

3. **Generic Agent Pattern**
   - Single GenericSalesAgent works with ANY creator
   - Creator profile passed as configuration context
   - Agent adapts behavior based on profile data
   - No hard-coding per creator needed

4. **Consumer Context**
   - Tracks each consumer's journey with creator
   - Metrics: page_views, service_clicks, enrolled status
   - Stage: new → interested → engaged → converted
   - Used by agents to make decisions

### System Flow

```
External API (Topmate)
         ↓
    Onboarding Service
         ↓
   LLM Profile Generation (OpenAI)
         ↓
   Creator Profile (Database)
         ↓
   Agent Deployment Service
         ↓
   GenericSalesAgent (configured with profile)
         ↓
   Event Ingestion (POST /events)
         ↓
   Consumer Context Update
         ↓
   Agent Triggers (RQ background job)
         ↓
   Agent Execution (should_act + plan_actions)
         ↓
   Planned Actions (scheduled for execution)
         ↓
   Action Execution (Twilio, SES, etc.)
```

---

## Key Files & Directories

### Core Domain Logic
- **`app/domain/onboarding/`** - Creator onboarding with LLM profile generation
  - `service.py` - OnboardingService (fetch → LLM → store)
  - `llm_service.py` - CreatorProfileLLMService (OpenAI integration)
  - `agent_deployment.py` - AgentDeploymentService (deploy agents for creators)

- **`app/agents/`** - Agent implementations
  - `generic_sales_agent.py` - **GenericSalesAgent** (main sales agent)
  - Uses BaseAgent interface: `should_act()` + `plan_actions()`

- **`app/domain/agents/`** - Agent framework
  - `base_agent.py` - BaseAgent interface with 40+ helper methods
  - `runtime.py` - AgentRuntime (SimpleAgentRuntime, LangGraphRuntime, ExternalHttpRuntime)
  - `service.py` - AgentService (create, list, execute agents)
  - `orchestrator.py` - Orchestrator (coordinates agent invocations)

- **`app/domain/events/`** - Event processing
  - `service.py` - EventService (create, list events)
  - `handlers.py` - EventHandler (context update + agent triggers)

- **`app/domain/context/`** - Consumer context management
  - `service.py` - ConsumerContextService (track consumer behavior)

### Infrastructure
- **`app/infra/db/`** - Database models (SQLModel)
  - `models.py` - Core models (Creator, Consumer, Event, Agent, etc.)
  - `creator_profile_models.py` - CreatorProfile, OnboardingLog
  - `connection.py` - Database connection

- **`app/infra/external/`** - External integrations
  - `topmate_client.py` - TopmateClient (fetch creator data)
  - `twilio_client.py` - TwilioClient (WhatsApp)
  - `ses_client.py` - SESClient (Email)

- **`app/infra/queues/`** - Background jobs (RQ)
  - `tasks.py` - Background tasks (process_agent_invocations, execute_scheduled_actions)
  - `worker.py` - RQ worker
  - `connection.py` - Redis connection

### API Layer
- **`app/api/routers/`** - FastAPI routers
  - `onboarding.py` - Onboarding + agent deployment endpoints
  - `events.py` - Event ingestion endpoint
  - `agents.py` - Agent management endpoints
  - `creators.py`, `consumers.py`, `products.py` - CRUD endpoints

### Configuration
- **`app/config.py`** - Settings (database URL, API keys, etc.)
- **`.env`** - Environment variables (not in git)
- **`requirements.txt`** - Python dependencies

### Testing
- **`scripts/test_onboarding.py`** - Test creator onboarding
- **`scripts/test_generic_sales_agent.py`** - Test agent logic
- **`scripts/test_e2e_agent_deployment.py`** - **Full integration test**
- **`scripts/create_tables.py`** - Database setup

### Documentation
- **`docs/AGENT_DEPLOYMENT_GUIDE.md`** - Complete agent deployment guide
- **`docs/PRD.md`** - Product requirements document
- **`docs/TECH_ARCHITECTURE.md`** - Technical architecture
- **`claude.md`** - **This file** (project overview for AI context)

---

## Database Schema

### Core Tables

**`creators`** - Creator accounts
```sql
id: UUID PRIMARY KEY
name: VARCHAR
email: VARCHAR UNIQUE
settings: JSONB
created_at: TIMESTAMP
```

**`creator_profiles`** - LLM-generated creator profiles
```sql
id: UUID PRIMARY KEY
creator_id: UUID REFERENCES creators(id)
external_user_id: INTEGER
external_username: VARCHAR
raw_data: JSONB                          -- Original API response
llm_summary: TEXT                        -- LLM-generated summary
sales_pitch: TEXT                        -- Sales pitch for agents
target_audience_description: TEXT        -- Who should buy
value_propositions: JSONB[]              -- List of value props
services: JSONB[]                        -- Service offerings
agent_instructions: TEXT                 -- How agents should sell
objection_handling: JSONB                -- Objection → Response map
pricing_info: JSONB                      -- Pricing data
ratings: JSONB                           -- Reviews, ratings
social_proof: JSONB                      -- Testimonials, bookings
last_synced_at: TIMESTAMP
created_at: TIMESTAMP
```

**`consumers`** - Leads/customers
```sql
id: UUID PRIMARY KEY
creator_id: UUID REFERENCES creators(id)
name: VARCHAR
email: VARCHAR
whatsapp: VARCHAR
created_at: TIMESTAMP
```

**`consumer_context`** - Behavior tracking
```sql
creator_id: UUID REFERENCES creators(id)
consumer_id: UUID REFERENCES consumers(id)
PRIMARY KEY (creator_id, consumer_id)
stage: VARCHAR                           -- new, interested, engaged, converted
last_seen_at: TIMESTAMP
metrics: JSONB                           -- page_views, service_clicks, etc.
attributes: JSONB                        -- Custom attributes
created_at: TIMESTAMP
updated_at: TIMESTAMP
```

**`events`** - Consumer events
```sql
id: UUID PRIMARY KEY
creator_id: UUID REFERENCES creators(id)
consumer_id: UUID REFERENCES consumers(id)
type: VARCHAR                            -- page_view, service_click, etc.
source: VARCHAR                          -- api, webhook, system
timestamp: TIMESTAMP
payload: JSONB                           -- Event-specific data
```

**`agents`** - Agent configurations
```sql
id: UUID PRIMARY KEY
creator_id: UUID REFERENCES creators(id) -- NULL for global agents
name: VARCHAR
implementation: VARCHAR                   -- simple, langgraph, external_http
config: JSONB                            -- Agent-specific config (includes creator_profile)
enabled: BOOLEAN
created_at: TIMESTAMP
```

**`agent_triggers`** - Agent trigger rules
```sql
id: UUID PRIMARY KEY
agent_id: UUID REFERENCES agents(id)
event_type: VARCHAR                      -- page_view, service_click, etc.
filter: JSONB                            -- Optional filter conditions
```

**`agent_invocations`** - Agent execution logs
```sql
id: UUID PRIMARY KEY
agent_id: UUID REFERENCES agents(id)
creator_id: UUID
consumer_id: UUID
event_id: UUID REFERENCES events(id)
status: VARCHAR                          -- pending, running, completed, failed
result: JSONB                            -- Execution result
error: TEXT
created_at: TIMESTAMP
```

**`actions`** - Planned actions
```sql
id: UUID PRIMARY KEY
invocation_id: UUID REFERENCES agent_invocations(id)
channel: VARCHAR                         -- email, whatsapp, call, payment
type: VARCHAR                            -- send_email, send_whatsapp, etc.
status: VARCHAR                          -- planned, approved, executing, executed, failed
payload: JSONB                           -- Action-specific data (message, to, etc.)
send_at: TIMESTAMP                       -- When to execute
priority: FLOAT
result: JSONB                            -- Execution result
error: TEXT
```

**`onboarding_logs`** - Onboarding audit trail
```sql
id: UUID PRIMARY KEY
creator_id: UUID
external_username: VARCHAR
status: VARCHAR                          -- processing, completed, failed
external_api_response: JSONB
llm_response: JSONB
processing_time_seconds: FLOAT
error_message: TEXT
created_at: TIMESTAMP
completed_at: TIMESTAMP
```

---

## How It Works: End-to-End Flow

### 1. Creator Onboarding

**Endpoint:** `POST /onboarding/`

```json
{
  "username": "ajay_shenoy",
  "name": "Ajay Shenoy",
  "email": "ajay@example.com"
}
```

**Process:**
1. `OnboardingService.onboard_creator()` called
2. `TopmateClient.fetch_creator_by_username()` fetches raw data
3. `CreatorProfileLLMService.generate_profile_document()` sends to OpenAI
4. LLM analyzes data and generates:
   - Sales pitch optimized for conversions
   - Agent instructions (tone, approach, timing)
   - Value propositions list
   - Objection handling responses
   - Target audience description
5. Creator + CreatorProfile saved to database
6. OnboardingLog records the process

**Result:** Creator profile ready for agent deployment

### 2. Agent Deployment

**Endpoint:** `POST /onboarding/deploy-agent/{creator_id}`

**Process:**
1. `AgentDeploymentService.deploy_sales_agent()` called
2. Loads CreatorProfile from database
3. Prepares agent config with creator profile data:
   ```python
   {
     "agent_class": "app.agents.generic_sales_agent:GenericSalesAgent",
     "creator_profile": {
       "creator_name": "Ajay Shenoy",
       "sales_pitch": "...",
       "agent_instructions": "...",
       "services": [...],
       "objection_handling": {...}
     }
   }
   ```
4. Creates Agent record with config
5. Creates AgentTriggers for page_view and service_click events
6. Agent is enabled and ready

**Result:** GenericSalesAgent deployed for creator

### 3. Event Ingestion & Processing

**Endpoint:** `POST /events`

```json
{
  "consumer_id": "5e890826-ce64-41d8-8e3d-7d0aed0a1c2d",
  "type": "service_click",
  "source": "api",
  "payload": {
    "service_id": "abc123"
  }
}
```

**Process:**
1. `EventService.create_event()` stores event
2. `handle_event()` called synchronously:
   - `ConsumerContextService.update_context_from_event()` updates context metrics
   - `enqueue_agent_invocations()` queues background job
3. RQ worker picks up job:
   - `process_agent_invocations()` runs
   - `Orchestrator.process_event_agents()` finds matching agents
   - For each agent:
     - Creates AgentInvocation record
     - `AgentService.execute_agent()` runs agent
     - `SimpleAgentRuntime.execute()` loads agent class
     - Agent's `should_act(context, event)` evaluates
     - If true, agent's `plan_actions(context, event)` generates actions
     - Actions saved with scheduled send_at time
4. Scheduler periodically calls `execute_scheduled_actions()`
   - Finds actions where send_at <= now
   - Executes via TwilioClient, SESClient, etc.

**Result:** Consumer receives personalized message

### 4. Agent Decision Logic

**GenericSalesAgent.should_act():**

```python
# Scenario 1: New lead - first page view
if event.type == "page_view" and context.metrics["page_views"] == 1:
    return True

# Scenario 2: Returning lead - came back after 24+ hours
if event.type == "page_view":
    hours_since = (now - context.last_seen_at).hours
    if hours_since >= 24 and context.metrics["page_views"] > 1:
        return True

# Scenario 3: Service click - showed interest but not enrolled
if event.type == "service_click" and not context.metrics["enrolled"]:
    return True

return False
```

**GenericSalesAgent.plan_actions():**

Uses creator's profile to generate personalized messages:

```python
# Get profile from config
creator_profile = self.config["creator_profile"]
sales_pitch = creator_profile["sales_pitch"]
services = creator_profile["services"]
agent_instructions = creator_profile["agent_instructions"]

# Get consumer info from context
consumer_name = context.metrics.get("name", "there")
consumer_whatsapp = context.metrics.get("whatsapp")

# Generate message using creator's sales pitch
message = f"""Hi {consumer_name}! 👋

I noticed you checked out {creator_name}'s page.

{sales_pitch[:400]}...

{service_name} is available for {service_price}.

Would you like to learn more?"""

# Schedule WhatsApp message
return [
    PlannedAction(
        channel="whatsapp",
        type="send_whatsapp",
        payload={"to": consumer_whatsapp, "message": message},
        send_at=datetime.utcnow() + timedelta(minutes=5),
        priority=1.0
    )
]
```

---

## Key Design Decisions

### 1. Generic Agent Pattern

**Decision:** Single GenericSalesAgent that receives creator profile as context

**Why:**
- Scalability: Works with ANY creator without code changes
- Maintainability: One agent to update, not N agents
- Flexibility: Creator profile can be updated without redeploying agent
- DRY: No duplication of agent logic

**Alternative Rejected:** Creator-specific agents (e.g., AjaySalesAgent)
- Would require code changes per creator
- Doesn't scale
- Maintenance nightmare

### 2. LLM-Generated Profiles

**Decision:** Use LLM to analyze creator data and generate optimized documentation

**Why:**
- Quality: LLM generates better sales copy than templates
- Consistency: Structured output (sales_pitch, instructions, objections)
- Adaptability: Works with varied creator data
- Scalability: Automated - no manual copywriting needed

**Implementation:**
- Model: gpt-5-nano-2025-08-07 (cheap, fast)
- Temperature: 1.0 (only supported value for this model)
- Prompt engineering: System prompt guides structured output
- Post-processing: JSON parsing, array→string conversion, control char cleaning

### 3. Event-Driven Architecture

**Decision:** Events trigger agents via background jobs

**Why:**
- Decoupling: Event ingestion separate from agent execution
- Reliability: Background jobs can retry on failure
- Performance: Non-blocking - API responds immediately
- Scalability: Can add workers to handle load

**Implementation:**
- RQ (Redis Queue) for background jobs
- Synchronous context update (within transaction)
- Asynchronous agent invocations (background)

### 4. Consumer Context Tracking

**Decision:** Maintain aggregate view of consumer behavior in consumer_context table

**Why:**
- Performance: Agents don't query all events
- Simplicity: Single record per consumer-creator pair
- Flexibility: Metrics JSONB allows arbitrary tracking

**Metrics Tracked:**
- page_views, service_clicks, enrolled
- Consumer contact info (name, email, whatsapp)
- Custom attributes

### 5. BaseAgent Interface

**Decision:** Simple 2-method interface: should_act() + plan_actions()

**Why:**
- Simplicity: Easy to understand and implement
- Flexibility: Agents have full control over logic
- Utility: 40+ helper methods for common operations
- Testing: Easy to unit test

**Methods:**
```python
class BaseAgent:
    def should_act(self, context, event) -> bool:
        """Decide if agent should act"""
        pass

    def plan_actions(self, context, event) -> list[PlannedAction]:
        """Generate actions to take"""
        pass

    # 40+ helper methods:
    # get_page_views(), get_metric(), send_whatsapp(), etc.
```

---

## Environment Variables

Required in `.env`:

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/creator_agents

# Redis
REDIS_URL=redis://redis:6379/0

# OpenAI
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-5-nano-2025-08-07

# Twilio (WhatsApp)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# AWS SES (Email)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
SES_SENDER_EMAIL=noreply@example.com

# Security
SECRET_KEY=your-secret-key-change-in-production

# Application
ENV=development
LOG_LEVEL=INFO
```

---

## Known Issues & Gotchas

### 1. OpenAI Model Restrictions

**Issue:** gpt-5-nano-2025-08-07 only supports temperature=1.0

**Solution:** Set `temperature=1.0` explicitly in CreatorProfileLLMService

**Context:** Initially tried 0.3, then default (0.7), both failed. Model requires exactly 1.0.

### 2. LLM JSON Parsing

**Issue:** LLM sometimes returns:
- Control characters in JSON
- Trailing commas
- Arrays instead of strings

**Solution:** Post-processing in `generate_profile_document()`:
```python
# Remove control characters
content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)

# Remove trailing commas
content = re.sub(r',(\s*[}\]])', r'\1', content)

# Convert arrays to strings
for field in ["llm_summary", "sales_pitch", ...]:
    if isinstance(result[field], list):
        result[field] = "\n\n".join(result[field])
```

### 3. EventSource Enum Validation

**Issue:** Event source must be one of: system, webhook, api, agent

**Context:** Initially used "website" which failed validation

**Solution:** Use "api" for API-submitted events, store original source in payload

### 4. Consumer Contact Info Access

**Issue:** Agents need consumer name/email/whatsapp to send messages

**Solution:** Store in ConsumerContext.metrics:
```python
context.metrics = {
    "page_views": 0,
    "name": consumer.name,
    "email": consumer.email,
    "whatsapp": consumer.whatsapp,
}
```

Agent accesses via: `self.get_metric(context, "whatsapp")`

### 5. Docker Networking

**Issue:** Container can't access localhost services

**Solution:** Use `--network host` when running containers locally:
```bash
docker run --rm --network host ...
```

Or use service names in docker-compose: `postgres` instead of `localhost`

---

## Testing Guide

### Test Hierarchy

1. **Unit Tests** - Test individual components
   - Agent logic: `test_generic_sales_agent.py`
   - Services: Test OnboardingService, AgentService, etc.

2. **Integration Tests** - Test multiple components
   - Onboarding flow: `test_onboarding.py`
   - Agent deployment: `test_e2e_agent_deployment.py`

3. **End-to-End Tests** - Test complete flows
   - **`test_e2e_agent_deployment.py`** - Full system test

### Running Tests

**Test Onboarding:**
```bash
docker run --rm --network host -v "$PWD:/app" -w /app --env-file .env \
  -e DATABASE_URL="postgresql://postgres:postgres@localhost:5432/creator_agents" \
  creator-agents-api python scripts/test_onboarding.py
```

**Test Agent Logic:**
```bash
docker run --rm --network host -v "$PWD:/app" -w /app --env-file .env \
  -e DATABASE_URL="postgresql://postgres:postgres@localhost:5432/creator_agents" \
  creator-agents-api python scripts/test_generic_sales_agent.py
```

**Test End-to-End:**
```bash
docker run --rm --network host -v "$PWD:/app" -w /app --env-file .env \
  -e DATABASE_URL="postgresql://postgres:postgres@localhost:5432/creator_agents" \
  creator-agents-api python scripts/test_e2e_agent_deployment.py
```

### Test Data

**Test Creator:** ajay_shenoy (username from Topmate API)
- Real data fetched from https://gcp.galactus.run/fetchByUsernameAdditionalDetails/?username=ajay_shenoy
- Used in all tests for consistency

**Test Consumer:** Test Lead (test_lead@example.com)
- Created in tests
- WhatsApp: +919876543210

---

## API Endpoints Reference

### Onboarding

**POST /onboarding/**
- Onboard creator, generate LLM profile
- Body: `{username, name?, email?}`
- Returns: Creator + profile highlights

**GET /onboarding/profile/{creator_id}**
- Get creator profile by ID
- Returns: Full CreatorProfile object

**POST /onboarding/sync**
- Re-sync profile from external API
- Body: `{creator_id}`
- Returns: Updated profile

**POST /onboarding/deploy-agent/{creator_id}**
- Deploy GenericSalesAgent for creator
- Returns: Agent configuration

**GET /onboarding/agents/{creator_id}**
- List all agents for creator
- Returns: Array of agents

### Events

**POST /events**
- Ingest event, trigger agents
- Body: `{consumer_id, type, source, payload}`
- Returns: Event object

**GET /events**
- List events with filters
- Query: `consumer_id, event_type, start_time, end_time, limit`

**GET /events/{event_id}**
- Get specific event

**GET /events/consumer/{consumer_id}/timeline**
- Get consumer's event timeline

### Agents

**POST /agents**
- Create custom agent
- Body: `{name, implementation, config, triggers}`

**GET /agents**
- List agents
- Query: `enabled_only`

**GET /agents/{agent_id}**
- Get specific agent

**POST /agents/{agent_id}/enable**
- Enable agent

**POST /agents/{agent_id}/disable**
- Disable agent

### Creators, Consumers, Products

Standard CRUD endpoints - see `app/api/routers/`

---

## Future Work & TODOs

### High Priority

1. **Multi-Channel Support**
   - Email channel (SES integration exists but not used)
   - SMS channel (Twilio integration needed)
   - In-app notifications

2. **Human-in-Loop**
   - Approval workflow for high-value actions
   - Creator dashboard to review/approve messages
   - Override agent decisions

3. **Analytics & Monitoring**
   - Conversion tracking (actions → bookings)
   - Agent performance metrics
   - A/B testing framework

4. **Rate Limiting & Policies**
   - PolicyEngine exists but not fully integrated
   - Enforce communication limits
   - Quiet hours
   - Consent management

### Medium Priority

5. **More Agent Scenarios**
   - Booking confirmations
   - Payment reminders
   - Re-engagement campaigns
   - Churn prevention

6. **LangGraph Agents**
   - Complex multi-step reasoning
   - Tool use (search, calculations)
   - State machines for conversations

7. **External HTTP Agents**
   - Integration with external services
   - Custom agent endpoints
   - Microservices architecture

8. **Consumer Intelligence**
   - Lead scoring
   - Intent detection
   - Persona classification

### Low Priority

9. **Admin Dashboard**
   - Creator management
   - Agent configuration UI
   - Event monitoring
   - Action approval queue

10. **Testing**
    - Pytest test suite
    - Integration tests
    - Load testing
    - Mock external services

11. **Documentation**
    - API documentation (OpenAPI)
    - Agent development guide
    - Deployment guide
    - Runbooks

---

## Development Workflow

### Adding a New Agent

1. Create agent class in `app/agents/`:
   ```python
   from app.domain.agents.base_agent import BaseAgent

   class MyAgent(BaseAgent):
       def should_act(self, context, event) -> bool:
           # Decision logic
           return True

       def plan_actions(self, context, event):
           # Generate actions
           return [self.send_whatsapp(...)]
   ```

2. Deploy via API or directly in database:
   ```python
   agent = Agent(
       creator_id=creator_id,
       name="My Agent",
       implementation="simple",
       config={
           "agent_class": "app.agents.my_agent:MyAgent",
           # Custom config
       },
       enabled=True
   )
   ```

3. Create triggers:
   ```python
   trigger = AgentTrigger(
       agent_id=agent.id,
       event_type="page_view",
       filter={}
   )
   ```

### Adding a New Event Type

1. Add to EventType enum in `app/domain/types.py`:
   ```python
   class EventType(str, Enum):
       # ...
       MY_EVENT = "my_event"
   ```

2. Update context service if needed:
   ```python
   # app/domain/context/service.py
   def update_context_from_event(self, event):
       if event.type == "my_event":
           context.metrics["my_event_count"] += 1
   ```

3. Use in events:
   ```python
   event = Event(
       creator_id=creator_id,
       consumer_id=consumer_id,
       type="my_event",
       source="api",
       payload={...}
   )
   ```

### Database Migration

1. Modify models in `app/infra/db/models.py` or `creator_profile_models.py`

2. Generate migration:
   ```bash
   alembic revision --autogenerate -m "Add new column"
   ```

3. Review and apply:
   ```bash
   alembic upgrade head
   ```

### Running Locally

**Without Docker:**
```bash
# Install dependencies
pip install -r requirements.txt

# Start services
docker-compose up -d postgres redis

# Run API
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/creator_agents
export REDIS_URL=redis://localhost:6379/0
# ... other env vars
uvicorn app.main:app --reload
```

**With Docker:**
```bash
# Build
docker-compose build

# Start all services
docker-compose up

# Or start individually
docker-compose up postgres redis
docker-compose up api
docker-compose up worker
```

---

## Troubleshooting

### "Agent not triggering"

**Check:**
1. Agent is enabled: `SELECT enabled FROM agents WHERE id = ?`
2. Triggers exist: `SELECT * FROM agent_triggers WHERE agent_id = ?`
3. Event type matches trigger: `SELECT event_type FROM agent_triggers`
4. Consumer context exists: `SELECT * FROM consumer_context`
5. should_act() returns True (add logging)

### "No actions generated"

**Check:**
1. Consumer has contact info in metrics
2. Event payload has required fields
3. Creator profile has services
4. Agent logic in plan_actions()

### "LLM returns invalid JSON"

**Check:**
1. OpenAI API key is valid
2. Model supports structured output
3. Post-processing catches common issues
4. Log raw LLM response

### "Database connection error"

**Check:**
1. PostgreSQL is running: `docker ps`
2. DATABASE_URL is correct
3. Database exists: `psql -l`
4. Tables created: `python scripts/create_tables.py`

### "Import errors"

**Check:**
1. Dependencies installed: `pip install -r requirements.txt`
2. Python path includes project root
3. Circular imports (common in SQLModel)

---

## Performance Considerations

### Current Bottlenecks

1. **LLM Profile Generation**
   - Takes 10-15 seconds per creator
   - Synchronous (blocks onboarding request)
   - Solution: Background job for onboarding

2. **Agent Execution**
   - Each event spawns background job
   - Multiple agents = multiple jobs
   - Solution: Batch agent invocations

3. **Context Queries**
   - Agents load full context each time
   - Solution: Cache context in Redis

### Scaling Recommendations

**100 creators, 1000 consumers:**
- Current setup sufficient
- Single API instance + 2 workers

**1000 creators, 100k consumers:**
- Horizontal scaling: 5-10 API instances
- Worker pool: 20-50 workers
- Redis cluster for queue
- Read replicas for database

**10k+ creators:**
- Event streaming (Kafka/Kinesis)
- Separate agent execution service
- Distributed caching (Redis cluster)
- Event sourcing architecture

---

## Security & Compliance

### Current State

- Basic authentication (not implemented)
- No RBAC (future work)
- API keys in environment variables
- No encryption at rest
- HTTPS required in production

### Required for Production

1. **Authentication & Authorization**
   - JWT tokens for API access
   - Role-based access control
   - Creator isolation (can't see other creators' data)

2. **Data Privacy**
   - GDPR compliance (right to delete, export)
   - Consent management (TCPA for SMS/calls)
   - Encryption at rest (database)
   - Encryption in transit (HTTPS, TLS)

3. **Rate Limiting**
   - API rate limits (per creator/IP)
   - Communication limits (PolicyEngine)
   - Abuse prevention

4. **Audit Logging**
   - Track all API calls
   - Agent actions audit trail
   - Admin actions logging

5. **Secrets Management**
   - Use AWS Secrets Manager / Vault
   - Rotate API keys regularly
   - No secrets in git

---

## Deployment

### Production Checklist

- [ ] Environment variables configured (all required keys)
- [ ] Database migrations applied
- [ ] Database backups scheduled
- [ ] Redis persistence enabled
- [ ] SSL certificates installed
- [ ] Monitoring & alerting configured
- [ ] Log aggregation (CloudWatch, Datadog, etc.)
- [ ] Error tracking (Sentry)
- [ ] Load balancer configured
- [ ] Auto-scaling enabled
- [ ] Health checks configured
- [ ] Rate limiting enabled
- [ ] Security audit completed
- [ ] Documentation updated

### Recommended Infrastructure

**AWS:**
- ECS/Fargate for API & workers
- RDS PostgreSQL (Multi-AZ)
- ElastiCache Redis (cluster mode)
- ALB for load balancing
- CloudWatch for monitoring
- S3 for backups
- SES for email
- Secrets Manager for keys

**GCP:**
- Cloud Run for API & workers
- Cloud SQL PostgreSQL
- Memorystore Redis
- Cloud Load Balancing
- Cloud Monitoring
- Cloud Storage for backups
- SendGrid for email
- Secret Manager

---

## Contact & Support

**Project Owner:** Dinesh Singh

**Repository:** /Users/dineshsingh/dev/topmate/creator-agents

**Key Documentation:**
- This file: `claude.md`
- Agent guide: `docs/AGENT_DEPLOYMENT_GUIDE.md`
- PRD: `docs/PRD.md`
- Architecture: `docs/TECH_ARCHITECTURE.md`

**Getting Help:**
- Check test scripts for examples
- Review agent implementations in `app/agents/`
- Consult API routers for endpoint usage
- Database schema in this file

---

## Version History

**v1.0 (2025-12-08)** - MVP Complete
- ✅ Creator onboarding with LLM profiles
- ✅ GenericSalesAgent implementation
- ✅ Agent deployment service
- ✅ Event ingestion & processing
- ✅ Background job execution
- ✅ End-to-end integration tests
- ✅ Comprehensive documentation

**Next:** v1.1 - Multi-channel support, human-in-loop, analytics
