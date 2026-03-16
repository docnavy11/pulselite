import sys
import time

_start_time = time.time()


def get_uptime_seconds() -> float:
    return time.time() - _start_time


def get_python_version() -> str:
    return sys.version
