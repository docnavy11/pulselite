"""In-memory ring buffer that captures log records for admin viewing."""

import logging
from collections import deque
from datetime import datetime, timezone


class LogBuffer(logging.Handler):
    """In-memory ring buffer that captures log records for admin viewing.

    logging.Handler.handle() acquires self.lock before calling emit(), so
    emit() must NOT re-acquire self.lock. We rely on the inherited RLock
    (set by Handler.__init__) for thread safety in emit(), and use it
    explicitly in get_entries() via self.acquire()/self.release().
    """

    _instance = None

    def __init__(self, capacity=1000):
        super().__init__()
        # Do NOT set self.lock here — logging.Handler.__init__ already sets
        # self.lock = threading.RLock(). Overwriting it with threading.Lock()
        # causes a self-deadlock because handle() acquires the lock before
        # calling emit(), and emit() would try to acquire it again.
        self.buffer: deque[dict] = deque(maxlen=capacity)

    def emit(self, record):
        # Called with self.lock already held by Handler.handle() — do not re-acquire.
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
            # formatException lives on Formatter, not Handler. Calling it on
            # self raised AttributeError inside emit(), so every
            # logger.exception() in the app blew up while handling an error —
            # and took the caller down with it.
            formatter = self.formatter or logging.Formatter()
            entry["exception"] = formatter.formatException(record.exc_info)
        self.buffer.append(entry)

    def get_entries(self, limit=100, level=None, logger_name=None):
        self.acquire()
        try:
            entries = list(self.buffer)
        finally:
            self.release()
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
