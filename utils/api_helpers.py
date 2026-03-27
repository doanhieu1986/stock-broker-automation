"""
utils/api_helpers.py
Tiện ích bổ trợ cho API: retry, format, cache alias.
"""

import time
from datetime import datetime, timedelta
from pathlib  import Path
from utils.data_loader import (
    load_cache, save_cache, load_watchlist, load_customers, output_dir, today,
    read_json, write_json
)

def get_json(path, default=None):
    return read_json(path, default)

def with_retry(func, retries=3, wait_sec=5, fallback=None, label=""):
    """Wrapper retry cho các hàm nghiệp vụ."""
    for i in range(retries):
        try:
            return func()
        except Exception as e:
            if i < retries - 1:
                time.sleep(wait_sec)
            else:
                if label:
                    print(f"  [Retry Error] {label}: {e}")
    return fallback

def cache_write(key: str, data: any, date_str: str | None = None) -> Path:
    return save_cache(key, data, date_str)

def cache_read(key: str, date_str: str | None = None):
    return load_cache(key, date_str)

def cache_read_yesterday(key: str):
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    return load_cache(key, yesterday)

def fmt_pct(val) -> str:
    if val is None: return "0.00%"
    return f"{val:+.2f}%"

def fmt_price(val) -> str:
    if val is None: return "0.0"
    return f"{val:,.1f}"

def get_text(obj) -> str:
    """Stub cho get_text nếu cần extract từ html."""
    if hasattr(obj, 'get_text'):
        return obj.get_text().strip()
    return str(obj).strip()
