# Agent Deployment Guide

## Overview

This guide explains how to deploy GenericSalesAgent for creators in the Creator Agents Platform. The GenericSalesAgent is a versatile, profile-driven agent that works with ANY creator by using their LLM-generated profile as context.

## Architecture

```
┌─────────────────┐
│  Creator Data   │
│  (Topmate API)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Onboarding    │◄─── POST /onboarding/
│   Service       │
│  + LLM Profile  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Creator Profile │
│  (Database)     │
│ • sales_pitch   │
│ • instructions  │
│ • services      │
│ • objections    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     Deploy      │◄─── POST /onboarding/deploy-agent/{creator_id}
│ GenericSalesAgent
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Agent Engine   │◄─── POST /events
│ • Triggers      │
│ • Execution     │
│ • Actions       │
└─────────────────┘
```

## Step-by-Step Deployment

### 1. Onboard a Creator

First, onboard the creator to generate their LLM-optimized profile:

**API Request:**
```bash
POST /onboarding/
Content-Type: application/json

{
  "username": "ajay_shenoy",
  "name": "Ajay Shenoy",
  "email": "ajay@example.com"
}
```

**What Happens:**
1. Fetches creator data from external API (Topmate)
2. LLM analyzes the data and generates:
   - Comprehensive sales pitch
   - Agent instructions (tone, approach)
   - Value propositions
   - Objection handling responses
   - Target audience description
3. Stores everything in `creator_profiles` table

**Response:**
```json
{
  "success": true,
  "creator_id": "fe5099b5-db6d-4d4b-b363-46a172d4c7d7",
  "profile_id": "038eebcc-1ad9-4c4b-a594-efdbc874e8ed",
  "external_username": "ajay_shenoy",
  "processing_time_seconds": 12.45,
  "llm_summary": "Ajay Shenoy is an experienced...",
  "sales_pitch": "Transform your enterprise with...",
  "services": [...],
  "value_propositions": [...]
}
```

### 2. Deploy Sales Agent

Deploy a GenericSalesAgent for the creator:

**API Request:**
```bash
POST /onboarding/deploy-agent/{creator_id}
```

**What Happens:**
1. Loads creator's profile from database
2. Creates an Agent with:
   - Implementation: `simple`
   - Agent Class: `app.agents.generic_sales_agent:GenericSalesAgent`
   - Config: Contains full creator profile data
3. Creates triggers for:
   - `page_view` events
   - `service_click` events
4. Agent is enabled and ready to process events

**Response:**
```json
{
  "id": "1a0d68b3-c456-4766-bb6e-6a7b7d0dc05f",
  "creator_id": "fe5099b5-db6d-4d4b-b363-46a172d4c7d7",
  "name": "ajay_shenoy - Sales Agent",
  "implementation": "simple",
  "config": {
    "agent_class": "app.agents.generic_sales_agent:GenericSalesAgent",
    "creator_profile": {
      "creator_name": "ajay_shenoy",
      "creator_id": "fe5099b5-db6d-4d4b-b363-46a172d4c7d7",
      "sales_pitch": "...",
      "agent_instructions": "...",
      "services": [...],
      "value_propositions": [...],
      "objection_handling": {...}
    }
  },
  "enabled": true
}
```

### 3. Events Automatically Trigger Agent

Once deployed, the agent automatically processes events:

**When an event occurs:**
```bash
POST /events
Content-Type: application/json

{
  "consumer_id": "5e890826-ce64-41d8-8e3d-7d0aed0a1c2d",
  "type": "page_view",
  "source": "api",
  "payload": {
    "page": "creator_profile",
    "url": "https://topmate.io/ajay_shenoy"
  }
}
```

**Processing Flow:**
1. Event is stored in database
2. Consumer context is updated
3. `handle_event()` finds matching agents
4. Background job is queued via RQ
5. Agent's `should_act()` evaluates event + context
6. If true, `plan_actions()` generates personalized messages
7. Actions are scheduled for execution

## How GenericSalesAgent Works

### Decision Logic (`should_act`)

The agent decides to act when:

1. **New Lead** - First page view
   ```python
   if event.type == "page_view" and page_views == 1:
       return True
   ```

2. **Returning Lead** - Comes back after 24+ hours
   ```python
   if event.type == "page_view" and hours_since_last_seen >= 24:
       return True
   ```

3. **Service Interest** - Clicks on service but hasn't enrolled
   ```python
   if event.type == "service_click" and not enrolled:
       return True
   ```

### Message Generation (`plan_actions`)

The agent creates personalized messages using the creator's profile:

**Scenario 1: New Lead (First Page View)**
```python
message = f"""Hi {consumer_name}! 👋

I noticed you checked out {creator_name}'s page.

{sales_pitch[:400]}...

{service_name} is available for {service_price}.

Would you like to learn more?"""
```

**Scenario 2: Returning Lead**
```python
message = f"""Hey {consumer_name},

I saw you came back to check out {service_name}. That's great!

📅 Schedule: {schedule}
💰 Investment: {price}
👥 {current_enrollment} people already enrolled

What questions can I answer for you?"""
```

**Scenario 3: Service Click**
```python
message = f"""Perfect timing, {consumer_name}! ✨

{service_name} is exactly what you need.

{service_description}

💳 Investment: {price}

Ready to enroll? Just reply "YES"! 🚀"""
```

## Key Features

### 1. Profile-Driven Context
- Agent receives creator's **complete profile** in config
- Uses LLM-generated content for personalization
- No hard-coding - works with any creator

### 2. Intelligent Decision Making
- Evaluates consumer behavior patterns
- Respects timing (24-hour windows)
- Avoids spam (checks enrollment status)

### 3. Personalized Messaging
- Uses creator's sales pitch
- Adapts to creator's tone and style
- Includes specific service details
- Handles objections with pre-generated responses

### 4. Multi-Scenario Support
- New lead outreach
- Re-engagement campaigns
- Service-specific enrollment pushes

## Testing

### End-to-End Test

Run the complete integration test:

```bash
python scripts/test_e2e_agent_deployment.py
```

This test:
1. ✅ Onboards a creator (ajay_shenoy)
2. ✅ Deploys GenericSalesAgent
3. ✅ Simulates page_view event
4. ✅ Simulates service_click event
5. ✅ Verifies agent generates personalized messages

**Expected Output:**
```
================================================================================
✅ END-TO-END TEST COMPLETE!
================================================================================

📊 Summary:
   • Creator: ajay_shenoy
   • Profile: Generated with 1 service(s)
   • Agent: ajay_shenoy - Sales Agent
   • Events Processed: 2 (page_view, service_click)
   • Total Actions Planned: 1

💡 What This Demonstrates:
   ✓ Creator onboarding with LLM profile generation
   ✓ Automatic agent deployment with creator's profile as context
   ✓ Agent responds to events (page_view, service_click)
   ✓ Agent uses creator's sales_pitch, instructions, and services
   ✓ Personalized messages tailored to each creator
```

### Isolated Agent Test

Test just the agent logic without deployment:

```bash
python scripts/test_generic_sales_agent.py
```

## Production Deployment Checklist

- [ ] Database tables created (`creator_profiles`, `onboarding_logs`)
- [ ] OpenAI API key configured (`OPENAI_API_KEY`)
- [ ] External API access (Topmate API)
- [ ] RQ workers running for background jobs
- [ ] Event ingestion endpoint available
- [ ] Agent triggers configured
- [ ] Rate limiting policies set
- [ ] Monitoring and logging enabled

## API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/onboarding/` | POST | Onboard creator, generate profile |
| `/onboarding/profile/{creator_id}` | GET | Get creator profile |
| `/onboarding/sync` | POST | Re-sync profile from external API |
| `/onboarding/deploy-agent/{creator_id}` | POST | Deploy sales agent |
| `/onboarding/agents/{creator_id}` | GET | List creator's agents |
| `/events` | POST | Ingest event, trigger agents |

## Database Schema

### `creator_profiles`
```sql
- id: UUID (PK)
- creator_id: UUID (FK to creators)
- external_user_id: INTEGER
- external_username: VARCHAR
- llm_summary: TEXT
- sales_pitch: TEXT
- target_audience_description: TEXT
- value_propositions: JSONB[]
- services: JSONB[]
- agent_instructions: TEXT
- objection_handling: JSONB
- pricing_info: JSONB
- ratings: JSONB
- social_proof: JSONB
- last_synced_at: TIMESTAMP
```

### `agents`
```sql
- id: UUID (PK)
- creator_id: UUID (FK to creators)
- name: VARCHAR
- implementation: VARCHAR (simple, langgraph, external_http)
- config: JSONB (contains creator_profile data)
- enabled: BOOLEAN
```

### `agent_triggers`
```sql
- id: UUID (PK)
- agent_id: UUID (FK to agents)
- event_type: VARCHAR (page_view, service_click, etc.)
- filter: JSONB
```

## Extending the Agent

To add new scenarios to GenericSalesAgent:

1. **Add decision logic** to `should_act()`:
   ```python
   # Example: Act on email opens
   if event.type == "email_opened" and not context.metrics.get("replied"):
       return True
   ```

2. **Add message generation** to `plan_actions()`:
   ```python
   # Example: Follow up after email open
   elif event.type == "email_opened":
       message = self._create_email_followup(...)
       actions.append(self.send_whatsapp(...))
   ```

3. **Add helper method** for message creation:
   ```python
   def _create_email_followup(self, consumer_name, creator_name, ...):
       return f"""Hi {consumer_name}, I saw you opened my email..."""
   ```

## Troubleshooting

### Agent Not Triggering
- Check agent is `enabled=True`
- Verify triggers exist for event type
- Check `should_act()` logic with consumer context
- Review consumer metrics in context

### No Actions Generated
- Verify consumer contact info in context metrics
- Check event payload has required fields
- Review agent logs for errors
- Ensure services exist in creator profile

### Wrong Messages
- Re-sync creator profile: `POST /onboarding/sync`
- Update agent with new profile: Agent auto-loads from config
- Check LLM-generated content quality

## Next Steps

1. **Add More Scenarios**: Booking confirmations, payment reminders, etc.
2. **A/B Testing**: Test different message variations
3. **Analytics**: Track conversion rates by agent
4. **Multi-Channel**: Add email, SMS channels
5. **Human-in-Loop**: Approval workflow for high-value actions

## Support

For issues or questions:
- Check logs: `docker-compose logs api`
- Review test output: `python scripts/test_e2e_agent_deployment.py`
- Inspect database: `psql creator_agents`
