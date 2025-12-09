# Technical Decisions & Rationale

This document captures key technical decisions made during development, the reasoning behind them, and important context for future work.

---

## 1. Generic Agent Pattern (Critical Decision)

### Decision
Use a single `GenericSalesAgent` that receives creator profile as configuration context, rather than creating separate agent classes per creator.

### Rationale
- **Scalability**: One agent works with ANY creator without code changes
- **Maintainability**: Single codebase to update, not N creator-specific agents
- **Flexibility**: Profile updates don't require code changes or redeployment
- **DRY Principle**: No duplication of agent logic

### Implementation
```python
# Agent config stores creator profile
config = {
    "agent_class": "app.agents.generic_sales_agent:GenericSalesAgent",
    "creator_profile": {
        "creator_name": "Ajay Shenoy",
        "sales_pitch": "...",
        "services": [...],
        # ... full profile data
    }
}

# Agent accesses profile at runtime
class GenericSalesAgent(BaseAgent):
    def plan_actions(self, context, event):
        profile = self.config["creator_profile"]
        sales_pitch = profile["sales_pitch"]
        # Use profile data for personalization
```

### Alternative Rejected
Creating per-creator agents (e.g., `AjaySalesAgent`, `PriyaSalesAgent`) would require:
- Code changes for each new creator
- Separate deployments
- Duplicated logic across agents
- Manual maintenance

### Impact
- ✅ Onboard any creator in seconds
- ✅ Deploy agent automatically via API
- ✅ Update profile without touching code
- ✅ Scale to thousands of creators easily

---

## 2. LLM-Generated Creator Profiles

### Decision
Use OpenAI to analyze raw creator data and generate comprehensive, sales-optimized documentation.

### Rationale
- **Quality**: LLM generates better copy than templates
- **Consistency**: Structured output (pitch, instructions, objections)
- **Adaptability**: Handles varied creator data formats
- **Automation**: No manual copywriting needed

### Implementation
```python
# Prompt engineering for structured output
system_prompt = """You are an expert at analyzing creator profiles
and generating sales-optimized documentation for AI agents.

Return JSON with these fields:
- llm_summary: Comprehensive 3-4 paragraph summary
- sales_pitch: Compelling 2-3 paragraph pitch
- target_audience_description: Ideal customer description
- value_propositions: Array of 5-7 value props
- services: Structured service data
- agent_instructions: How agents should sell
- objection_handling: Objection → Response map
"""

# Model selection
model = "gpt-5-nano-2025-08-07"  # Cheap, fast, sufficient quality
temperature = 1.0  # Only supported value for this model
```

### Challenges Overcome
1. **Temperature restriction**: gpt-5-nano only supports 1.0
2. **JSON parsing issues**: Control characters, trailing commas, array/string confusion
3. **Post-processing required**: Clean JSON, convert arrays to strings

### Post-Processing Pipeline
```python
# 1. Remove control characters
content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)

# 2. Remove trailing commas
content = re.sub(r',(\s*[}\]])', r'\1', content)

# 3. Parse JSON (lenient mode)
result = json.loads(content, strict=False)

# 4. Convert arrays to strings
for field in ["llm_summary", "sales_pitch", ...]:
    if isinstance(result[field], list):
        result[field] = "\n\n".join(result[field])
```

### Alternative Considered
Template-based profiles - rejected because:
- Lower quality output
- Rigid structure
- Manual field mapping
- Less adaptability

### Cost & Performance
- Cost: ~$0.001 per profile (gpt-5-nano)
- Latency: 10-15 seconds
- Quality: High enough for MVP
- Future: Consider caching, background processing

---

## 3. Event-Driven Architecture

### Decision
Events trigger agents via background jobs (RQ), with synchronous context updates.

### Rationale
- **Decoupling**: Event ingestion separate from agent execution
- **Reliability**: Background jobs can retry failures
- **Performance**: API responds immediately (non-blocking)
- **Scalability**: Horizontal scaling via worker pool

### Flow
```
POST /events
    ↓
Store Event (DB)
    ↓
Update Context (synchronous, same transaction)
    ↓
Enqueue Agent Job (RQ)
    ↓
Return 201 Created
    ↓
[Background] RQ Worker
    ↓
Execute Agent
    ↓
Plan Actions
    ↓
Schedule Actions
```

### Why Synchronous Context Update?
- **Consistency**: Context always up-to-date before agent runs
- **Simplicity**: No eventual consistency issues
- **Transactional**: Event + context update in single DB transaction
- **Fast enough**: Simple JSON update, < 10ms

### Why Asynchronous Agent Execution?
- **Non-blocking**: API returns immediately
- **Retries**: Failed agents can retry
- **Isolation**: Agent errors don't affect API
- **Scalability**: Can scale workers independently

### Technology Choice: RQ (Redis Queue)
**Pros:**
- Simple Python API
- Built-in retry logic
- Job persistence via Redis
- Good observability

**Alternatives Considered:**
- Celery: Too complex for MVP
- AWS SQS/Lambda: Vendor lock-in
- Kafka: Overkill for scale

---

## 4. Consumer Context Aggregation

### Decision
Maintain aggregate behavioral view in `consumer_context` table (stage + metrics), rather than querying all events.

### Rationale
- **Performance**: Single row lookup vs aggregating all events
- **Simplicity**: Agents query one record
- **Flexibility**: JSONB metrics allow arbitrary tracking
- **Real-time**: Updated on every event

### Schema
```sql
CREATE TABLE consumer_context (
    creator_id UUID,
    consumer_id UUID,
    PRIMARY KEY (creator_id, consumer_id),
    stage VARCHAR,  -- new, interested, engaged, converted
    last_seen_at TIMESTAMP,
    metrics JSONB,  -- {page_views: 5, emails_sent: 2, ...}
    attributes JSONB,  -- Custom data
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Metrics Stored
```json
{
  "page_views": 5,
  "service_clicks": 2,
  "emails_sent": 3,
  "emails_opened": 1,
  "whatsapp_messages_sent": 2,
  "enrolled": false,
  "name": "John Doe",
  "email": "john@example.com",
  "whatsapp": "+1234567890"
}
```

### Why Include Contact Info in Metrics?
- **Agent Access**: Agents need contact info to send messages
- **Convenience**: Single query gets behavior + contact
- **Flexibility**: Easy to add/update fields

### Trade-off
- **Duplication**: Contact info also in `consumers` table
- **Acceptable**: Metrics is already denormalized for performance
- **Benefit**: Agents don't need JOIN queries

### Alternative Rejected
Querying events table:
```sql
-- Would need this query for every agent invocation
SELECT type, COUNT(*)
FROM events
WHERE consumer_id = ?
GROUP BY type;
```
- Too slow at scale
- More complex agent code
- No aggregate "stage" field

---

## 5. BaseAgent Interface Design

### Decision
Simple 2-method interface with 40+ helper methods.

### Interface
```python
class BaseAgent(ABC):
    @abstractmethod
    def should_act(self, context, event) -> bool:
        """Decide if agent should act on this event"""
        pass

    @abstractmethod
    def plan_actions(self, context, event):
        """Generate list of PlannedAction"""
        pass

    # 40+ helper methods provided
    def get_page_views(self, context): ...
    def get_metric(self, context, key, default): ...
    def send_whatsapp(self, to, message, **kwargs): ...
    # etc.
```

### Rationale
**Simplicity:**
- Only 2 methods required
- Clear separation: decision vs action
- Easy to understand

**Flexibility:**
- Agents control all logic
- No framework constraints
- Can access config, session, etc.

**Utilities:**
- Helper methods handle boilerplate
- Consistent patterns across agents
- Less code duplication

### Why Not Framework-Heavy?
Alternatives like LangChain AgentExecutor:
- More complex
- Less transparent
- Harder to debug
- Unnecessary for this use case

### Extension Pattern
Agents can override default behavior:
```python
class MyAgent(BaseAgent):
    def analyze(self, context, event):
        # Optional: add custom analysis
        return {"score": self.calculate_score(context)}

    def should_act(self, context, event):
        analysis = self.analyze(context, event)
        return analysis["score"] > 10
```

---

## 6. Multi-Runtime Support

### Decision
Support 3 agent runtime types: Simple, LangGraph, External HTTP.

### Implementation
```python
class AgentRuntimeFactory:
    @staticmethod
    def create(implementation: AgentImplementation, session):
        if implementation == SIMPLE:
            return SimpleAgentRuntime(session)
        elif implementation == LANGGRAPH:
            return LangGraphRuntime()
        elif implementation == EXTERNAL_HTTP:
            return ExternalHttpRuntime()
```

### Why Multiple Runtimes?
1. **Simple**: For straightforward logic (current use case)
2. **LangGraph**: For complex reasoning, tool use, multi-step
3. **External HTTP**: For microservices, external teams

### Current Usage
- GenericSalesAgent uses `SIMPLE`
- LangGraph runtime exists but unused
- HTTP runtime exists but unused

### Future Use Cases
**LangGraph:**
- Multi-turn conversations
- Tool use (search, calculations)
- Complex decision trees

**External HTTP:**
- Third-party agents
- Microservices architecture
- Polyglot teams (non-Python)

### Trade-off
- Additional complexity
- More code to maintain
- Benefit: Flexibility for future needs

---

## 7. Database Technology: SQLModel + PostgreSQL

### Decision
Use SQLModel (SQLAlchemy + Pydantic) with PostgreSQL.

### Rationale
**SQLModel:**
- Type safety (Pydantic)
- ORM convenience (SQLAlchemy)
- FastAPI integration
- Modern Python patterns

**PostgreSQL:**
- JSONB for flexible data (metrics, payloads)
- Strong consistency (ACID)
- Rich indexes
- Proven at scale

### JSONB Usage
Used for:
- `consumer_context.metrics` - Behavioral metrics
- `events.payload` - Event-specific data
- `agents.config` - Agent configuration
- `creator_profiles.services` - Service arrays

Why JSONB?
- Schema flexibility
- No migrations for new fields
- Query with SQL (e.g., `metrics->>'page_views'`)
- Index support

### Alternative Considered
MongoDB - Rejected because:
- Need strong consistency
- Relational queries important
- JSONB gives flexibility anyway

---

## 8. Action Scheduling

### Decision
Actions have `send_at` timestamp, scheduled execution via periodic job.

### Implementation
```python
# Agent creates action with future send_at
action = PlannedAction(
    channel="whatsapp",
    payload={"to": "+1234", "message": "Hi!"},
    send_at=datetime.utcnow() + timedelta(minutes=5),
    priority=1.0
)

# Periodic job executes due actions
def execute_scheduled_actions():
    actions = get_actions_due_now()  # WHERE send_at <= NOW()
    for action in actions:
        execute_action(action)
```

### Why Not Immediate Execution?
- **Timing**: Respect optimal send times
- **Rate Limiting**: Space out communications
- **User Experience**: Not too eager (5 min delay feels natural)

### Scheduler Options
**Current:** Manual periodic job (cron/scheduler calls endpoint)
**Future:** APScheduler or Celery Beat for built-in scheduling

### Priority Field
- Higher priority = execute first if multiple actions due
- Example: Booking confirmation (2.0) > Follow-up email (0.5)

---

## 9. Error Handling Strategy

### Decision
Record errors but don't fail loudly; retry automatically.

### Implementation
```python
try:
    output = agent.execute(...)
    invocation.status = "completed"
    invocation.result = output
except Exception as e:
    invocation.status = "failed"
    invocation.error = str(e)
    # Don't re-raise - job marked as failed but doesn't retry infinitely
```

### Rationale
- **Resilience**: One failing agent doesn't break system
- **Observability**: Errors logged to invocations table
- **Recovery**: Can manually retry failed invocations

### Retry Logic
RQ provides automatic retries (configurable):
```python
job = queue.enqueue(
    process_agent_invocations,
    ...,
    retry=Retry(max=3, interval=60),  # 3 retries, 60s apart
)
```

### Future Improvements
- Dead letter queue for persistent failures
- Alert on repeated failures
- Circuit breaker pattern

---

## 10. Security & Privacy Decisions

### Current State
- ⚠️ No authentication (API publicly accessible)
- ⚠️ No authorization (creator isolation not enforced)
- ⚠️ API keys in environment variables
- ⚠️ No encryption at rest
- ✅ JSONB prevents SQL injection
- ✅ Pydantic validates input

### Required for Production
1. **Authentication**: JWT tokens, API keys
2. **Authorization**: Row-level security, creator isolation
3. **Secrets Management**: AWS Secrets Manager / Vault
4. **Encryption**: Database encryption, TLS everywhere
5. **Consent**: GDPR, TCPA compliance
6. **Rate Limiting**: Prevent abuse
7. **Audit Logging**: Track all actions

### Design for Privacy
```python
# Future: Add creator_id checks everywhere
def get_event(event_id, creator_id):
    event = session.get(Event, event_id)
    if event.creator_id != creator_id:
        raise Forbidden("Not your event")
    return event
```

---

## 11. Testing Strategy

### Current Approach
**Integration Tests:**
- `test_onboarding.py` - Test full onboarding flow
- `test_generic_sales_agent.py` - Test agent logic
- `test_e2e_agent_deployment.py` - Test complete system

**Why Integration Over Unit?**
- Complex interactions between components
- Database state important
- Real LLM calls needed for profile quality
- End-to-end flows are what matter

### Test Data
- Use real external API (ajay_shenoy)
- Consistent test user across tests
- Database state persists (not reset between runs)

### Future Improvements
- Unit tests for individual functions
- Mock external APIs
- Test database isolation
- Property-based testing (Hypothesis)
- Load testing

---

## 12. Logging & Observability

### Current Implementation
```python
import logging
logger = logging.getLogger(__name__)

logger.info("Processing event", extra={"event_id": event.id})
logger.error("Agent failed", exc_info=True)
```

### Structured Logging
- Use `extra` dict for structured data
- Include IDs (event_id, agent_id, invocation_id)
- Log levels: DEBUG, INFO, WARNING, ERROR

### Database as Audit Log
- `onboarding_logs` - Onboarding history
- `agent_invocations` - Agent execution history
- `actions` - Action execution history

### Future: APM
- Sentry for error tracking
- DataDog/New Relic for metrics
- Distributed tracing (OpenTelemetry)

---

## 13. Performance Optimizations

### Database Indexes
```sql
-- Critical for performance
CREATE INDEX idx_events_creator_consumer ON events(creator_id, consumer_id);
CREATE INDEX idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX idx_consumer_context_pk ON consumer_context(creator_id, consumer_id);
CREATE INDEX idx_actions_send_at ON actions(send_at) WHERE status = 'planned';
```

### Query Patterns
- Use `select().where()` for type safety
- Avoid N+1 queries (use joins or eager loading)
- Limit results with `.limit()`

### Caching Strategy (Future)
- Cache creator profiles in Redis (change rarely)
- Cache agent configs (change rarely)
- Don't cache context (changes frequently)

### Scaling Checklist
- [ ] Connection pooling (SQLAlchemy default)
- [ ] Read replicas for queries
- [ ] Redis cluster for job queue
- [ ] Horizontal scaling (stateless API)
- [ ] CDN for static assets
- [ ] Database partitioning (by creator_id)

---

## Summary of Key Patterns

1. **Generic over Specific**: One GenericSalesAgent vs many creator-specific agents
2. **LLM-Generated Content**: Automate profile creation, handle parsing edge cases
3. **Event-Driven**: Async processing via background jobs
4. **Context Aggregation**: Maintain behavioral summary for fast agent queries
5. **Simple Interfaces**: 2-method agent interface, clear abstractions
6. **Multi-Runtime**: Support future complexity without rewrite
7. **JSONB Flexibility**: Schema-less data where appropriate
8. **Action Scheduling**: Deferred execution for timing and rate limiting
9. **Graceful Degradation**: Record errors, don't crash
10. **Integration Testing**: Test realistic flows end-to-end

---

## When to Revisit These Decisions

### GenericSalesAgent Pattern
**Revisit if:**
- Need agent-specific behavior that can't be configured
- Profile data structure becomes too complex
- Performance issues with profile in config

### LLM Profile Generation
**Revisit if:**
- Cost becomes prohibitive at scale
- Quality issues with current model
- Need real-time profile updates

### Event-Driven Architecture
**Revisit if:**
- Need sub-second latency (real-time chat)
- Event volume exceeds RQ capacity (>10k/sec)
- Need exactly-once delivery guarantees

### Database Schema
**Revisit if:**
- JSONB queries become slow (missing indexes)
- Need complex joins (consider normalization)
- Data warehouse needs (consider OLAP)

---

*This document should be updated as new decisions are made or existing ones are revisited.*
