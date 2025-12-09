# Creator Agents Platform

An event-driven, AI-powered automation framework that enables creators to manage leads through intelligent agents operating within safety guardrails.

## Overview

The Creator Agents Platform is a comprehensive system that provides:

- **Event-Driven Architecture**: Unified timeline tracking all consumer interactions (page views, bookings, payments, messages)
- **AI-Powered Agents**: LangGraph-based agents that autonomously decide on actions based on consumer context
- **Policy Guardrails**: Rate limits, quiet hours, and consent enforcement to prevent spam
- **Multi-Channel Execution**: Email, WhatsApp, calls, and payment link generation
- **Consumer Context Engine**: Materialized views of consumer state for intelligent decision-making

## Architecture

### Technology Stack

- **Backend**: Python + FastAPI
- **ORM**: SQLModel (SQLAlchemy + Pydantic integration)
- **Database**: PostgreSQL
- **Queue**: Redis + RQ
- **AI Framework**: LangGraph + OpenAI
- **Migrations**: Alembic

### Key Components

```
app/
├── api/              # HTTP endpoints and routers
├── domain/           # Business logic
│   ├── creators/     # Creator management
│   ├── consumers/    # Lead management
│   ├── products/     # Product offerings
│   ├── events/       # Event handling
│   ├── context/      # Consumer context engine
│   ├── agents/       # Agent orchestration
│   ├── policy/       # Guardrails and policies
│   └── channels/     # Communication channels
├── infra/            # Infrastructure concerns
│   ├── db/           # Database models
│   ├── queues/       # Background workers
│   └── external/     # External integrations
└── agents/           # LangGraph agent implementations
```

## Getting Started

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- PostgreSQL 15+
- Redis 7+
- OpenAI API key
- AWS SES credentials (for email)
- Twilio credentials (for WhatsApp)

### Installation

1. **Clone the repository**
   ```bash
   cd creator-agents
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```

3. **Configure environment variables**

   Edit `.env` and add your credentials:
   ```
   OPENAI_API_KEY=sk-your-key-here
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret-key
   SES_SENDER_EMAIL=noreply@yourdomain.com
   TWILIO_ACCOUNT_SID=your-account-sid
   TWILIO_AUTH_TOKEN=your-auth-token
   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   SECRET_KEY=your-secret-key-here
   ```

4. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```

   This will start:
   - PostgreSQL on port 5432
   - Redis on port 6379
   - FastAPI application on port 8000
   - RQ worker for background jobs

5. **Run database migrations**
   ```bash
   docker-compose exec api alembic upgrade head
   ```

6. **Access the API**
   - API: http://localhost:8000
   - Documentation: http://localhost:8000/docs
   - Health check: http://localhost:8000/health

### Local Development (without Docker)

1. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start PostgreSQL and Redis**
   ```bash
   # Using Docker for just database and Redis
   docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:15
   docker run -d -p 6379:6379 redis:7-alpine
   ```

4. **Run migrations**
   ```bash
   alembic upgrade head
   ```

5. **Start the API server**
   ```bash
   python -m app.main
   ```

6. **Start the worker (in another terminal)**
   ```bash
   python -m app.infra.queues.worker
   ```

## Usage

### 1. Create a Creator

```bash
curl -X POST http://localhost:8000/creators \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "settings": {
      "brand_voice": "friendly",
      "quiet_hours": {"start": 21, "end": 9}
    }
  }'
```

### 2. Create a Consumer (Lead)

```bash
curl -X POST http://localhost:8000/consumers \
  -H "Content-Type: application/json" \
  -H "X-Creator-ID: <creator-id>" \
  -d '{
    "email": "lead@example.com",
    "whatsapp": "+1234567890",
    "name": "Jane Smith",
    "timezone": "America/New_York",
    "consent": {
      "email": true,
      "whatsapp": true
    }
  }'
```

### 3. Create a Product

```bash
curl -X POST http://localhost:8000/products \
  -H "Content-Type: application/json" \
  -H "X-Creator-ID: <creator-id>" \
  -d '{
    "name": "Cohort Program",
    "type": "cohort",
    "price_cents": 50000,
    "currency": "USD",
    "meta": {
      "duration_weeks": 8,
      "max_participants": 50
    }
  }'
```

### 4. Create an Agent

```bash
curl -X POST http://localhost:8000/agents \
  -H "Content-Type: application/json" \
  -H "X-Creator-ID: <creator-id>" \
  -d '{
    "name": "Cohort Sales Agent",
    "implementation": "langgraph",
    "config": {
      "graph_path": "app.agents.cohort_sales:graph"
    },
    "enabled": true,
    "triggers": [
      {
        "event_type": "page_view",
        "filter": {}
      },
      {
        "event_type": "whatsapp_message_received",
        "filter": {}
      }
    ]
  }'
```

### 5. Record Events

```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -H "X-Creator-ID: <creator-id>" \
  -d '{
    "consumer_id": "<consumer-id>",
    "type": "page_view",
    "source": "api",
    "payload": {
      "page_url": "https://example.com/cohort",
      "referrer": "google",
      "product_id": "<product-id>"
    }
  }'
```

When an event is recorded:
1. Event is persisted to database
2. Consumer context is updated
3. Matching agents are triggered (background job)
4. Agents generate planned actions
5. Actions are validated through policy engine
6. Approved actions are executed through channels

## API Reference

### Endpoints

- **Creators**: `/creators`
  - `POST /creators` - Create creator
  - `GET /creators/me` - Get current creator
  - `PATCH /creators/me/settings` - Update settings

- **Consumers**: `/consumers`
  - `POST /consumers` - Create consumer
  - `GET /consumers/{id}` - Get consumer
  - `GET /consumers/{id}/context` - Get consumer context
  - `PATCH /consumers/{id}` - Update consumer

- **Products**: `/products`
  - `POST /products` - Create product
  - `GET /products` - List products
  - `GET /products/{id}` - Get product
  - `PATCH /products/{id}` - Update product
  - `DELETE /products/{id}` - Delete product

- **Events**: `/events`
  - `POST /events` - Record event
  - `GET /events` - List events
  - `GET /events/{id}` - Get event
  - `GET /events/consumer/{id}/timeline` - Get consumer timeline

- **Agents**: `/agents`
  - `POST /agents` - Create agent
  - `GET /agents` - List agents
  - `GET /agents/{id}` - Get agent
  - `POST /agents/{id}/enable` - Enable agent
  - `POST /agents/{id}/disable` - Disable agent

### Authentication

Currently uses `X-Creator-ID` header for creator identification. In production, implement proper JWT authentication.

## Agent Development

### Simple Agent Interface (Recommended for Beginners)

The easiest way to create an agent is using the `BaseAgent` interface. Just implement two methods:

1. **`should_act()`** - Decide when to act
2. **`plan_actions()`** - Decide what to do

**Example:**

```python
from app.domain.agents.base_agent import BaseAgent
from app.infra.db.models import Event, ConsumerContext

class WelcomeAgent(BaseAgent):
    def should_act(self, context: ConsumerContext, event: Event) -> bool:
        """Act on first page view for new leads."""
        return (
            event.type == "page_view" and
            self.get_page_views(context) == 1 and
            self.is_new_lead(context)
        )

    def plan_actions(self, context: ConsumerContext, event: Event):
        """Send welcome message."""
        return [
            self.send_whatsapp(
                to=self.get_event_payload(event, "whatsapp"),
                message="Hey! 👋 Welcome! I'm here if you have questions.",
                delay_minutes=2,
            )
        ]
```

**Register it:**

```bash
curl -X POST http://localhost:8000/agents \
  -H "Content-Type: application/json" \
  -H "X-Creator-ID: <creator-id>" \
  -d '{
    "name": "Welcome Agent",
    "implementation": "simple",
    "config": {
      "agent_class": "app.agents.welcome_agent:WelcomeAgent"
    },
    "enabled": true,
    "triggers": [{"event_type": "page_view", "filter": {}}]
  }'
```

**📖 See [AGENT_GUIDE.md](./AGENT_GUIDE.md) for a complete tutorial with examples!**

### Advanced: LangGraph Agents

For complex multi-step reasoning, you can use LangGraph:

1. Create a new file in `app/agents/`:

```python
from langgraph.graph import StateGraph, END
from app.domain.types import ActionType, Channel

# Define state
class AgentState(TypedDict):
    creator_id: str
    consumer_id: str
    event: dict
    context: dict
    actions: list[dict]
    reasoning: str

# Define nodes
def analyze(state: AgentState) -> AgentState:
    # Your analysis logic
    return state

def plan(state: AgentState) -> AgentState:
    # Your planning logic
    state["actions"] = [
        {
            "action_type": ActionType.SEND_EMAIL.value,
            "channel": Channel.EMAIL.value,
            "payload": {...},
            "send_at": datetime.utcnow().isoformat(),
            "priority": 1.0,
        }
    ]
    return state

# Build graph
workflow = StateGraph(AgentState)
workflow.add_node("analyze", analyze)
workflow.add_node("plan", plan)
workflow.set_entry_point("analyze")
workflow.add_edge("analyze", "plan")
workflow.add_edge("plan", END)

graph = workflow.compile()
```

2. Register agent via API with `graph_path: "app.agents.your_agent:graph"`

### External HTTP Agents

You can also create agents as external HTTP services:

```json
{
  "name": "External Agent",
  "implementation": "external_http",
  "config": {
    "endpoint": "https://your-service.com/agent"
  }
}
```

Your endpoint should accept:
```json
{
  "creator_id": "uuid",
  "consumer_id": "uuid",
  "event": {...},
  "context": {...},
  "tools": ["email", "whatsapp", "call", "payment"]
}
```

And return:
```json
{
  "actions": [
    {
      "action_type": "send_email",
      "channel": "email",
      "payload": {...},
      "send_at": "2024-01-01T00:00:00Z",
      "priority": 1.0
    }
  ],
  "reasoning": "Why these actions were chosen",
  "metadata": {}
}
```

## Policy Configuration

Policies can be configured per creator:

```python
from app.domain.types import PolicyKey

# Set email rate limit
policy_service.set_policy_value(
    creator_id,
    PolicyKey.RATE_LIMIT_EMAIL_WEEKLY,
    3  # Max 3 emails per week
)

# Set quiet hours
policy_service.set_policy_value(
    creator_id,
    PolicyKey.QUIET_HOURS_START,
    21  # 9 PM
)

policy_service.set_policy_value(
    creator_id,
    PolicyKey.QUIET_HOURS_END,
    9  # 9 AM
)
```

## Testing

Run tests with pytest:

```bash
pytest tests/
```

## Monitoring

Structured logging with correlation IDs is built-in. All logs include:
- `correlation_id` - Request correlation ID
- `creator_id` - Creator context
- `consumer_id` - Consumer context
- `event_id` - Event being processed
- `invocation_id` - Agent invocation ID

## Deployment

### Production Checklist

1. Set strong `SECRET_KEY` in environment
2. Configure proper CORS origins
3. Set up SSL/TLS for API
4. Configure production database with connection pooling
5. Set up monitoring and alerting
6. Configure log aggregation (e.g., DataDog, CloudWatch)
7. Set up scheduled jobs for `execute_scheduled_actions`
8. Implement proper authentication/authorization
9. Set up database backups
10. Configure rate limiting at API gateway level

## Roadmap

- [ ] Multi-agent orchestration with dependencies
- [ ] Agent marketplace for custom agents
- [ ] Lead timeline UI
- [ ] A/B testing framework for agents
- [ ] Predictive lead scoring
- [ ] Voice cloning for personalized messages
- [ ] Microservices extraction (Events, Agents, Channels)
- [ ] Real-time webhooks for external systems

## License

MIT

## Support

For issues and questions, please open an issue on GitHub.
