#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/restore.sh <backup_file>
# Restores a PostgreSQL backup

BACKUP_FILE="${1:?Usage: ./scripts/restore.sh <backup_file.sql.gz>}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: File not found: $BACKUP_FILE" >&2
    exit 1
fi

echo "WARNING: This will overwrite the current database!"
read -p "Are you sure? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo "Restoring from: $BACKUP_FILE"
gunzip -c "$BACKUP_FILE" | docker compose exec -T postgres psql -U "${POSTGRES_USER:-pulse}" "${POSTGRES_DB:-pulse}"

if [ $? -eq 0 ]; then
    echo "Restore completed successfully."
else
    echo "ERROR: Restore failed!" >&2
    exit 1
fi
