.PHONY: help install dev test lint format clean docker-up docker-down migrate upgrade

help:
	@echo "Available commands:"
	@echo "  make install       - Install dependencies"
	@echo "  make dev          - Run development server"
	@echo "  make worker       - Run background worker"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linting"
	@echo "  make format       - Format code"
	@echo "  make clean        - Clean cache files"
	@echo "  make docker-up    - Start Docker containers"
	@echo "  make docker-down  - Stop Docker containers"
	@echo "  make migrate      - Create new migration"
	@echo "  make upgrade      - Run migrations"

install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	python -m app.infra.queues.worker

test:
	pytest tests/ -v --cov=app --cov-report=html

lint:
	ruff check app/ tests/
	mypy app/

format:
	black app/ tests/
	ruff check --fix app/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

migrate:
	alembic revision --autogenerate -m "$(message)"

upgrade:
	alembic upgrade head

downgrade:
	alembic downgrade -1

db-shell:
	docker-compose exec postgres psql -U postgres -d creator_agents

redis-cli:
	docker-compose exec redis redis-cli
