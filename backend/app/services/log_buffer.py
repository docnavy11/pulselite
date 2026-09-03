"""In-memory ring buffer that captures log records for admin viewing."""

import logging
import threading
from collections import deque
from datetime import datetime, timezone


_formatter = logging.Formatter()


class LogBuffer(logging.Handler):
    """In-memory ring buffer that captures log records for admin viewing."""

    _instance = None

    def __init__(self, capacity=1000):
        super().__init__()
        self.buffer: deque[dict] = deque(maxlen=capacity)
        self.lock = threading.Lock()

    def emit(self, record):
        try:
            entry = {
                "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }
            if record.exc_info and record.exc_info[0] is not None:
                entry["exception"] = _formatter.formatException(record.exc_info)
            with self.lock:
                self.buffer.append(entry)
        except Exception:
            pass

    def get_entries(self, limit=100, level=None, logger_name=None):
        with self.lock:
            entries = list(self.buffer)
        if level:
            entries = [e for e in entries if e["level"] == level.upper()]
        if logger_name:
            entries = [e for e in entries if logger_name in e["logger"]]
        return entries[-limit:]

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
