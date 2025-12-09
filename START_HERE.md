# START HERE - Future AI Assistant Guide

Welcome! This is the **Creator Agents Platform** - an event-driven system that helps creators automatically engage and convert leads using AI agents.

**Status:** ✅ MVP Complete (v1.0, 2025-12-08)

---

## 🎯 What This Project Does

1. **Onboards Creators** - Fetches data from external API, generates LLM-optimized sales profiles
2. **Deploys Agents** - Automatically configures GenericSalesAgent with creator's profile
3. **Processes Events** - Consumer actions (page views, clicks) trigger agents
4. **Sends Messages** - Agents generate personalized WhatsApp/Email messages

**Key Innovation:** Single **GenericSalesAgent** works with ANY creator by receiving their profile as configuration context. No hard-coding needed.

---

## 📚 Essential Documentation

Read these files in order:

### 1. **claude.md** - MAIN DOCUMENTATION
**Read this first!** Complete project overview:
- Architecture & system flow
- Database schema
- Key files & their purposes
- How everything works together
- Testing, deployment, troubleshooting

### 2. **TECHNICAL_DECISIONS.md** - Design Rationale
Why we made specific technical choices:
- Generic agent pattern
- LLM profile generation
- Event-driven architecture
- Database design

### 3. **docs/AGENT_DEPLOYMENT_GUIDE.md** - Agent Guide
How to deploy and use agents:
- API endpoints
- Step-by-step deployment
- Agent scenarios
- Customization

### 4. **QUICK_REFERENCE.md** - Common Patterns
Quick lookup for:
- Code snippets
- Database queries
- Docker commands
- Debugging tips

---

## 🚀 Quick Start

### Run Tests (Verify Everything Works)

```bash
# 1. Start database
docker-compose up -d postgres

# 2. Build image
docker-compose build api

# 3. Run end-to-end test (tests everything)
docker run --rm --network host -v "$PWD:/app" -w /app --env-file .env \
  -e DATABASE_URL="postgresql://postgres:postgres@localhost:5432/creator_agents" \
  creator-agents-api python scripts/test_e2e_agent_deployment.py
```

**Expected output:**
```
✅ END-TO-END TEST COMPLETE!
📊 Summary:
   • Creator: ajay_shenoy
   • Agent: ajay_shenoy - Sales Agent
   • Events Processed: 2
   • Total Actions Planned: 1
```

---

## 🏗️ Architecture in 30 Seconds

```
External API → Onboarding → LLM Profile → Database
                                            ↓
                                    Deploy GenericSalesAgent
                                            ↓
Event (page_view) → Context Update → Agent Trigger → Background Job
                                                            ↓
                                                    Agent Execution
                                                            ↓
                                                    Planned Actions
                                                            ↓
                                                    Send Messages
```

---

## 📁 Key Files

### Core Logic
- `app/agents/generic_sales_agent.py` - Main sales agent (THE agent)
- `app/domain/onboarding/service.py` - Creator onboarding
- `app/domain/onboarding/llm_service.py` - LLM profile generation
- `app/domain/onboarding/agent_deployment.py` - Deploy agents
- `app/domain/agents/base_agent.py` - Agent interface
- `app/domain/agents/runtime.py` - Agent execution

### Database
- `app/infra/db/models.py` - Core models (Creator, Event, Agent, etc.)
- `app/infra/db/creator_profile_models.py` - CreatorProfile

### API
- `app/api/routers/onboarding.py` - Onboarding + deployment endpoints
- `app/api/routers/events.py` - Event ingestion
- `app/main.py` - FastAPI app

### Testing
- `scripts/test_e2e_agent_deployment.py` - **Run this first!**
- `scripts/test_onboarding.py` - Test onboarding
- `scripts/test_generic_sales_agent.py` - Test agent logic

---

## 🔑 Key Concepts

### 1. Generic Agent Pattern
One agent (`GenericSalesAgent`) works with ALL creators by receiving their profile as config:
```python
config = {
    "agent_class": "app.agents.generic_sales_agent:GenericSalesAgent",
    "creator_profile": {
        "creator_name": "Ajay",
        "sales_pitch": "...",
        "services": [...],
        # Full profile data
    }
}
```

### 2. Creator Profiles
LLM analyzes creator data and generates:
- Sales pitch
- Agent instructions
- Value propositions
- Objection handling
- Target audience

### 3. Event-Driven Flow
```python
POST /events → Event stored → Context updated → Agent job queued
→ RQ worker → Agent executes → Actions planned → Actions executed
```

### 4. Consumer Context
Aggregate view of consumer behavior:
```json
{
  "stage": "interested",
  "metrics": {
    "page_views": 5,
    "service_clicks": 2,
    "email": "user@example.com",
    "whatsapp": "+1234567890"
  }
}
```

### 5. Agent Interface
Simple 2-method interface:
```python
class MyAgent(BaseAgent):
    def should_act(self, context, event) -> bool:
        return event.type == "page_view"

    def plan_actions(self, context, event):
        return [self.send_whatsapp(...)]
```

---

## 🛠️ Common Tasks

### Onboard a New Creator
```bash
curl -X POST http://localhost:8000/onboarding/ \
  -H "Content-Type: application/json" \
  -d '{"username": "creator_username"}'
```

### Deploy Agent
```bash
curl -X POST http://localhost:8000/onboarding/deploy-agent/{creator_id}
```

### Ingest Event
```bash
curl -X POST http://localhost:8000/events \
  -H "X-Creator-Id: {creator_id}" \
  -d '{
    "consumer_id": "{consumer_id}",
    "type": "page_view",
    "source": "api",
    "payload": {"page": "profile"}
  }'
```

### Query Database
```sql
-- Get creator with profile
SELECT c.name, cp.sales_pitch
FROM creators c
JOIN creator_profiles cp ON c.id = cp.creator_id;

-- Get agent invocations
SELECT * FROM agent_invocations
ORDER BY created_at DESC
LIMIT 10;
```

---

## ⚠️ Known Issues & Gotchas

### 1. OpenAI Temperature
**Issue:** gpt-5-nano-2025-08-07 only supports `temperature=1.0`
**Fix:** Already set in code

### 2. LLM JSON Parsing
**Issue:** LLM returns invalid JSON (control chars, trailing commas)
**Fix:** Post-processing in `llm_service.py` handles this

### 3. Event Source Validation
**Issue:** Event source must be: system, webhook, api, or agent
**Fix:** Use "api" for API-submitted events

### 4. Consumer Contact Info
**Issue:** Agents need consumer contact to send messages
**Fix:** Stored in `consumer_context.metrics` dict

---

## 🐛 Troubleshooting

### Agent Not Triggering
```sql
-- Check agent is enabled
SELECT id, name, enabled FROM agents;

-- Check triggers exist
SELECT * FROM agent_triggers WHERE agent_id = ?;

-- Check events being created
SELECT COUNT(*) FROM events;
```

### No Actions Generated
- Check consumer has contact info in `consumer_context.metrics`
- Verify agent's `should_act()` returns True
- Check agent logs

### Database Connection Error
```bash
# Start PostgreSQL
docker-compose up -d postgres

# Create tables
python scripts/create_tables.py
```

### LLM API Error
```bash
# Check API key
echo $OPENAI_API_KEY

# Verify in .env
cat .env | grep OPENAI_API_KEY
```

---

## 🎓 Learning Path

**Day 1: Understand the system**
1. Read claude.md sections: "Quick Start", "Architecture Overview", "How It Works"
2. Run test_e2e_agent_deployment.py and observe output
3. Review GenericSalesAgent code (`app/agents/generic_sales_agent.py`)

**Day 2: Explore the database**
1. Connect to database and explore schema
2. Run test_onboarding.py and see profile data
3. Query `creator_profiles`, `agents`, `agent_invocations` tables

**Day 3: Understand the flow**
1. Trace event ingestion: API → handler → context → queue
2. Review agent runtime code (`app/domain/agents/runtime.py`)
3. See how actions are scheduled and executed

**Day 4: Extend the system**
1. Read TECHNICAL_DECISIONS.md
2. Try adding a new agent scenario
3. Test your changes

---

## 📊 Project Status

### ✅ Completed (v1.0)
- Creator onboarding with LLM profiles
- GenericSalesAgent implementation
- Agent deployment service
- Event ingestion & processing
- Background job execution
- End-to-end integration tests
- Comprehensive documentation

### 🚧 Future Work
- Multi-channel support (Email, SMS)
- Human-in-loop approval
- Analytics & conversion tracking
- Rate limiting enforcement
- Admin dashboard
- Production deployment

---

## 🆘 Need Help?

1. **Read claude.md first** - Most answers are there
2. **Check TECHNICAL_DECISIONS.md** - Explains the "why"
3. **Run tests** - See working examples
4. **Review code** - Start with GenericSalesAgent
5. **Query database** - Inspect actual data

---

## 📝 When Making Changes

### Before Coding
- Read relevant sections in claude.md
- Check if pattern exists in codebase
- Review TECHNICAL_DECISIONS.md for context

### After Coding
- Run tests: `python scripts/test_e2e_agent_deployment.py`
- Update documentation if adding features
- Add entry to TECHNICAL_DECISIONS.md if making architectural changes

### Common Patterns
- Adding event type → Update `app/domain/types.py`
- Adding agent scenario → Extend `GenericSalesAgent`
- Adding API endpoint → Add router in `app/api/routers/`
- Database changes → Create migration, update models

---

## 🎯 Success Criteria

**You understand the project when you can:**
1. Explain how GenericSalesAgent works with any creator
2. Trace an event from POST /events to WhatsApp message
3. Deploy a new agent for a creator
4. Debug why an agent didn't trigger
5. Add a new event type and agent scenario

---

**Welcome to the team! Start with claude.md and you'll be productive quickly. The code is well-structured and extensively documented.**

*Last Updated: 2025-12-08*
