# Creator Agents Platform - Quick Start

## 🚀 One-Command Startup

```bash
cd /Users/dharsankumar/Documents/GitHub/creator-agents-platform && docker-compose up -d
```

**Note:** Uses existing shared PostgreSQL container
- No database container created
- Data persists in shared database
- All tables auto-created on first run

Then wait 20 seconds and open:
- Frontend: http://localhost:3000
- API Docs: http://localhost:8001/docs

## 📋 Status Check

```bash
docker-compose ps
```

Should show 4 services:
- ✅ redis (Up)
- ✅ api (Up)
- ✅ worker (Up)
- ✅ frontend (Up)

## 🧪 Quick Test

1. Go to http://localhost:3000
2. Click "Onboard Creator"
3. Enter username: `ajay_shenoy`
4. Wait for profile generation
5. Check stats update ✓

## 📚 Common Commands

| Command | Purpose |
|---------|---------|
| `docker-compose up -d` | Start all services |
| `docker-compose down` | Stop services |
| `docker-compose ps` | Show status |
| `docker-compose logs -f` | View logs |
| `docker-compose logs -f api` | View API logs only |
| `docker-compose restart api` | Restart API |

## 🔧 Troubleshooting

**Port 3000 already in use:**
```bash
# Kill what's using it
lsof -i :3000 | grep -v COMMAND | awk '{print $2}' | xargs kill -9
```

**Docker daemon not running:**
- On macOS: Open Docker Desktop from Applications folder

**Services not starting:**
```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

## 📍 Service Ports

- Frontend: 3000
- API: 8001
- Database: 5433
- Redis: 6379

## 📖 Documentation

- `DOCKER_STARTUP.md` - Full Docker guide
- `STARTUP_GUIDE.md` - Local development setup
- `CLAUDE.md` - Architecture overview
- `docs/AGENT_DEPLOYMENT_GUIDE.md` - Advanced features

## ⚡ First Steps After Starting

1. **Onboard a creator** (generates LLM profile)
2. **Deploy an agent** (adds sales agent to creator)
3. **Send an event** (triggers agent execution)
4. **View results** (see events in dashboard)

That's it! 🎉
