.PHONY: setup setup-check up down build migrate seed test test-unit test-integration test-isolation test-security test-all test-fast lint test-frontend test-frontend-coverage test-e2e test-e2e-headed lint-bandit lint-semgrep lint-security-static test-schema-public test-schema-auth test-schema perf-smoke perf-auth perf-widget perf-all test-coverage-gate

setup:
	python3 scripts/setup-env.py

setup-check:
	python3 scripts/setup-env.py --check

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

migrate:
	docker compose exec backend bash -c "PYTHONPATH=/app alembic upgrade head"

migrate-create:
	docker compose exec backend alembic revision --autogenerate -m "$(msg)"

test:
	docker compose exec backend pytest -v

test-coverage:
	docker compose exec backend pytest --cov=app --cov-report=html

test-unit:
	docker compose exec backend pytest tests/unit/ -v

test-integration:
	docker compose exec backend pytest tests/integration/ -v

test-isolation:
	docker compose exec backend pytest tests/integration/test_tenant_isolation.py -v

test-security:
	docker compose exec backend pytest tests/security/ -v

test-all:
	docker compose exec backend pytest tests/ --cov=app --cov-report=html --cov-fail-under=80

test-fast:
	docker compose exec backend pytest tests/unit/ -n auto

lint:
	docker compose exec backend ruff check app/
	docker compose exec backend ruff format --check app/

format:
	docker compose exec backend ruff format app/

logs:
	docker compose logs -f

shell-backend:
	docker compose exec backend bash

shell-db:
	docker compose exec postgres psql -U pulse -d pulse

seed:
	docker compose exec backend python scripts/seed.py

reset-db:
	docker compose down -v
	docker compose up -d postgres redis
	sleep 3
	$(MAKE) migrate
	$(MAKE) seed

test-frontend:
	docker compose exec frontend npx vitest run

test-frontend-coverage:
	docker compose exec frontend npx vitest run --coverage

test-e2e:
	cd frontend && npx playwright test

test-e2e-headed:
	cd frontend && npx playwright test --headed

lint-bandit:
	docker compose exec backend bandit -r app/ --configfile .bandit -ll

lint-semgrep:
	cd backend && semgrep scan \
	  --config=p/python \
	  --config=p/owasp-top-ten \
	  --config=p/secrets \
	  app/ \
	  --error

lint-security-static: lint-bandit lint-semgrep

test-schema-public:
	st run http://localhost:8000/openapi.json \
	  --checks not_a_server_error \
	  --exclude-path-regex "/auth/google|/auth/sso|/oauth|/shopify|/whatsapp|/messenger|/instagram|/slack" \
	  --exclude-path-regex "/public/chat|/share/|/chat$$|/chat/completions|/workspaces/" \
	  -n 10

test-schema-auth:
	@TOKEN=$$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
	  -H 'Content-Type: application/json' \
	  -d '{"email":"test@pulse.dev","password":"test"}' \
	  | python3 -c "import sys,json; print(json.load(sys.stdin)['tokens']['access_token'])") && \
	st run http://localhost:8000/openapi.json \
	  --checks not_a_server_error \
	  -H "Authorization: Bearer $$TOKEN" \
	  --exclude-path-regex "/auth/google|/auth/sso|/oauth|/shopify|/whatsapp|/messenger|/instagram|/slack" \
	  --exclude-path-regex "/public/chat|/share/|/chat$$|/chat/completions" \
	  -n 10

test-schema:
	@TOKEN=$$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
	  -H 'Content-Type: application/json' \
	  -d '{"email":"test@pulse.dev","password":"test"}' \
	  | python3 -c "import sys,json; print(json.load(sys.stdin)['tokens']['access_token'])") && \
	$(MAKE) test-schema-public && \
	sleep 65 && \
	st run http://localhost:8000/openapi.json \
	  --checks not_a_server_error \
	  -H "Authorization: Bearer $$TOKEN" \
	  --exclude-path-regex "/auth/google|/auth/sso|/oauth|/shopify|/whatsapp|/messenger|/instagram|/slack" \
	  --exclude-path-regex "/public/chat|/share/|/chat$$|/chat/completions" \
	  -n 10

test-coverage-gate:
	docker compose exec backend pytest tests/ \
	  --cov=app \
	  --cov-config=pyproject.toml \
	  --cov-report=term-missing \
	  --cov-fail-under=45 \
	  -q

perf-smoke:
	k6 run k6/smoke.js

perf-auth:
	k6 run k6/auth-read.js

perf-widget:
	k6 run k6/widget.js

perf-all: perf-smoke perf-auth perf-widget

# ── Backup / Restore ──────────────────────────────
backup:                          ## Create a database backup
	@bash scripts/backup.sh

restore:                         ## Restore from a backup file (usage: make restore FILE=backups/pulse_backup_xxx.sql.gz)
	@bash scripts/restore.sh $(FILE)

backup-list:                     ## List available backups
	@ls -lh backups/pulse_backup_*.sql.gz 2>/dev/null || echo "No backups found in ./backups/"
