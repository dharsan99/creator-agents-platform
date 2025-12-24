# Creator Agents Platform - Startup Guide

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (running locally or via Docker)
- Redis 7+ (running locally or via Docker)
- OpenAI API Key (for LLM agent profiles)

## Quick Start (Local Development)

### Option 1: Docker Compose (Recommended)

If Docker daemon is running:

```bash
# Start all services (PostgreSQL, Redis, API, Worker)
docker-compose up -d

# Or start with logs visible
docker-compose up
```

### Option 2: Local Python Environment

#### 1. Start PostgreSQL and Redis

```bash
# Using Docker for just the database and Redis
docker-compose up -d postgres redis

# Or install locally and start services
# PostgreSQL: brew install postgresql && brew services start postgresql
# Redis: brew install redis && brew services start redis
```

#### 2. Start Backend API

```bash
# Activate virtual environment
source venv_local/bin/activate

# Set up environment variables
export DATABASE_URL="postgresql://user:password@localhost:5432/creator_agents"
export REDIS_URL="redis://localhost:6379/0"
export OPENAI_API_KEY="sk-your-api-key-here"

# Create database tables
python scripts/create_tables.py

# Start API server (in one terminal)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 3. Start Background Worker (Optional)

```bash
# In another terminal
source venv_local/bin/activate
python -m app.infra.queues.worker
```

#### 4. Start Frontend Server

```bash
# In another terminal
npm start
# Frontend will be available at http://localhost:3000
```

## Verification

### Check API Health

```bash
curl http://localhost:8000/health
```

Should return:
```json
{
  "status": "ok",
  "service": "creator-agents-api",
  "timestamp": "2025-12-16T..."
}
```

### Access Frontend

Open browser and go to: **http://localhost:3000**

You should see the Creator Agents Platform dashboard.

## API Endpoints

### Onboarding
- `POST /onboarding/` - Onboard a new creator
- `GET /onboarding/profile/{creator_id}` - Get creator profile
- `POST /onboarding/deploy-agent/{creator_id}` - Deploy sales agent

### Events
- `POST /events` - Send an event (triggers agents)
- `GET /events` - List events with pagination
- `GET /events/{event_id}` - Get event details

### Agents
- `GET /agents` - List all agents
- `POST /agents` - Create custom agent
- `GET /agents/{agent_id}` - Get agent details
- `POST /agents/{agent_id}/enable` - Enable agent
- `POST /agents/{agent_id}/disable` - Disable agent

### Creators
- `GET /creators` - List creators
- `POST /creators` - Create creator
- `GET /creators/{creator_id}` - Get creator details

### Consumers
- `GET /consumers` - List consumers
- `POST /consumers` - Create consumer
- `GET /consumers/{consumer_id}` - Get consumer details

## Frontend Features

The dashboard provides:

1. **Onboard Creator** - Add new creators from Topmate
2. **Deploy Agent** - Deploy GenericSalesAgent for creators
3. **Send Event** - Trigger events for consumers (page_view, service_click, etc.)
4. **View Events** - Browse processed events with pagination
5. **View Creators** - See all onboarded creators and their agents
6. **Dashboard Stats** - See real-time counts of creators, agents, consumers, events

## Testing the Full Flow

1. **Onboard a Creator**
   - Go to "Onboard Creator" tab
   - Enter username: `ajay_shenoy`
   - Click "Onboard Creator"
   - Wait for LLM profile generation

2. **Deploy Agent**
   - Go to "Deploy Agent" tab
   - Select the creator you just onboarded
   - Click "Deploy Agent"

3. **Send Event**
   - Go to "Send Event" tab
   - Select creator and event type
   - Enter consumer email
   - Click "Send Event"

4. **View Results**
   - Go to "View Events" tab
   - See the events that triggered agents
   - Check "Creators" to see agent deployment status

## Environment Variables

Required `.env` file:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/creator_agents

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI (for LLM agents)
OPENAI_API_KEY=sk-your-api-key-here

# AWS SES (Email) - Optional
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
SES_SENDER_EMAIL=noreply@yourdomain.com

# Twilio (WhatsApp) - Optional
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# Application
ENV=development
LOG_LEVEL=INFO
SECRET_KEY=your-secret-key
```

## Troubleshooting

### "Cannot connect to database"
- Make sure PostgreSQL is running
- Check DATABASE_URL is correct
- Verify database exists: `createdb creator_agents`

### "Redis connection failed"
- Make sure Redis is running
- Check REDIS_URL is correct
- Test: `redis-cli ping` should return "PONG"

### "API port 8000 already in use"
- Kill existing process: `lsof -i :8000` then `kill -9 <PID>`
- Or use different port: `--port 8001`

### "OpenAI API errors"
- Verify OPENAI_API_KEY is set correctly
- Check you have credits on your OpenAI account
- Ensure gpt-5-nano model is available in your region

### "Frontend not connecting to API"
- Check API is running: `curl http://localhost:8000/health`
- Frontend defaults to `http://localhost:8000`
- If API is on different port, edit `frontend/js/dashboard.js` line 10

## Development

### Make changes to frontend:
- Edit files in `frontend/` directory
- Restart frontend server: `npm start`
- Browser will auto-refresh

### Make changes to backend:
- Edit files in `app/` directory
- API server runs with `--reload` flag
- Changes auto-reload automatically

### Database schema changes:
- Edit `app/infra/db/models.py`
- Create migration: `alembic revision --autogenerate -m "description"`
- Apply migration: `alembic upgrade head`

## Next Steps

- Explore agent implementations in `app/agents/`
- Check `CLAUDE.md` for architecture overview
- Read `docs/AGENT_DEPLOYMENT_GUIDE.md` for advanced agent customization
- Review test scripts in `scripts/` for usage examples
