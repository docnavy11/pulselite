#!/usr/bin/env bash
set -e

# Run database migrations automatically on startup
echo "Running database migrations..."
python -m alembic upgrade head 2>&1 || {
    echo "WARNING: Migration failed. Database may not be ready yet. Retrying in 5s..."
    sleep 5
    python -m alembic upgrade head || echo "ERROR: Migration failed. Please run 'make migrate' manually."
}

# Execute the original command
exec "$@"
