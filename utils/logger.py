"""
utils/logger.py
Hệ thống logging chuẩn — format: [HH:MM:SS] SOURCE | ENDPOINT | STATUS | ms
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from functools import wraps

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_today = datetime.now().strftime("%Y%m%d")


def _make_logger(name: str, filename: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler(LOG_DIR / filename, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(message)s"))
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(fh)
        logger.addHandler(sh)
    return logger


api_logger    = _make_logger("api",    f"api_{_today}.log")
output_logger = _make_logger("output", f"output_{_today}.log")


def get_logger(name: str) -> logging.Logger:
    return _make_logger(name, f"system_{_today}.log")


def log_api(source: str, endpoint: str, status: str, ms: int):
    ts = datetime.now().strftime("%H:%M:%S")
    api_logger.info(f"[{ts}] {source:<14} | {endpoint:<30} | {status:<8} | {ms}ms")


def log_output(filepath: str, size_kb: float = 0):
    ts = datetime.now().strftime("%H:%M:%S")
    output_logger.info(f"[{ts}] OUTPUT | {filepath} | {size_kb:.1f}KB")


def log_api_call(logger_obj, source: str, endpoint: str, status: str, ms: int):
    log_api(source, endpoint, status, ms)

def api_call(source: str, endpoint: str):
    """Decorator tự động log thời gian + status cho mọi API call."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                log_api(source, endpoint, "OK", int((time.time() - start) * 1000))
                return result
            except Exception as e:
                log_api(source, endpoint, f"ERR:{type(e).__name__}", int((time.time() - start) * 1000))
                raise
        return wrapper
    return decorator


def print_box(title: str, rows: list[str], width: int = 58):
    bar = "═" * width
    print(f"\n╔{bar}╗")
    print(f"║  {title:<{width-2}}║")
    print(f"╠{bar}╣")
    for row in rows:
        print(f"║  {row:<{width-2}}║")
    print(f"╚{bar}╝\n")


def section(label: str):
    ts = datetime.now().strftime("%H:%M")
    print(f"\n[{ts}] ── {label} ──")


class Timer:
    def __init__(self, label: str):
        self.label = label
    def __enter__(self):
        self._t = time.time()
        return self
    def __exit__(self, *_):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] ✓ {self.label} ({time.time()-self._t:.1f}s)")
