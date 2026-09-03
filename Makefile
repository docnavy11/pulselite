.PHONY: up down logs migrate migrate-create seed reset-db shell-backend shell-db test test-unit lint format

# Docker
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

# Database
migrate:
	docker compose exec backend alembic upgrade head

migrate-create:
	docker compose exec backend alembic revision --autogenerate -m "$(msg)"

seed:
	docker compose exec backend python scripts/seed.py

reset-db:
	docker compose down -v
	docker compose up -d postgres
	sleep 3
	docker compose up -d backend
	sleep 5
	$(MAKE) migrate
	$(MAKE) seed

# Shell access
shell-backend:
	docker compose exec backend bash

shell-db:
	docker compose exec postgres psql -U pulse -d pulse

# Testing
test:
	docker compose exec backend pytest tests/ -v

test-unit:
	docker compose exec backend pytest tests/unit/ -v

# Linting
lint:
	docker compose exec backend ruff check . && docker compose exec backend ruff format --check .

format:
	docker compose exec backend ruff format .

# Restart backend after code changes
restart:
	docker compose restart backend
