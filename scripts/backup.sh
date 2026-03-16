#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/backup.sh [output_dir]
# Creates a timestamped PostgreSQL backup

OUTPUT_DIR="${1:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${OUTPUT_DIR}/pulse_backup_${TIMESTAMP}.sql.gz"

mkdir -p "$OUTPUT_DIR"

echo "Creating PostgreSQL backup..."
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-pulse}" "${POSTGRES_DB:-pulse}" | gzip > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "Backup created: $BACKUP_FILE"
    echo "Size: $(du -h "$BACKUP_FILE" | cut -f1)"

    # Keep only last 7 backups
    cd "$OUTPUT_DIR"
    ls -t pulse_backup_*.sql.gz 2>/dev/null | tail -n +8 | xargs -r rm --
    echo "Old backups cleaned (keeping last 7)"
else
    echo "ERROR: Backup failed!" >&2
    exit 1
fi
