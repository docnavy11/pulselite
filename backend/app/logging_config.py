"""Structured JSON logging configuration for Pulselight."""

import json
import logging
import os
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    """Configure structured JSON logging.

    Log level is controlled by the ``LOG_LEVEL`` environment variable
    (default: ``INFO``).
    """
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    # Add JSON handler alongside existing handlers (don't clear uvicorn's)
    json_handler = logging.StreamHandler()
    json_handler.setFormatter(JSONFormatter())

    # Only attach to the pulse.* namespace to avoid double-logging
    pulse_logger = logging.getLogger("pulse")
    pulse_logger.setLevel(log_level)
    pulse_logger.addHandler(json_handler)
    pulse_logger.propagate = False

    # Also attach JSON handler to uvicorn for consistent structured logging
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        third_party = logging.getLogger(name)
        third_party.addHandler(json_handler)
        third_party.propagate = False

    # Attach in-memory ring buffer for admin log viewing
    from app.services.log_buffer import LogBuffer

    buffer_handler = LogBuffer.get_instance()
    buffer_handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(buffer_handler)

    # Security event logger — login failures, auth errors, etc.
    security_logger = logging.getLogger("security")
    security_logger.setLevel(logging.INFO)
    security_logger.addHandler(json_handler)
    security_logger.propagate = False

    # Quieten noisy third-party loggers
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
