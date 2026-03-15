#!/usr/bin/env bash
set -e

echo "[entrypoint] Waiting for PostgreSQL..."

attempts=0
max_attempts=30
until pg_isready -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:-pulse}" -q; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge "$max_attempts" ]; then
        echo "[entrypoint] ERROR: PostgreSQL not reachable after $max_attempts attempts"
        exit 1
    fi
    echo "[entrypoint] Postgres not ready yet (attempt $attempts/$max_attempts)..."
    sleep 1
done

echo "[entrypoint] PostgreSQL is ready. Running migrations..."
cd /app/backend
alembic upgrade head

echo "[entrypoint] Migrations complete. Starting services..."
exec supervisord -c /app/infra/light/supervisord.conf
