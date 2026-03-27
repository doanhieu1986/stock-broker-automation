"""
utils/data_loader.py
Đọc/ghi JSON, watchlist, customer list, cache, alerts, CSV log.
Interface thống nhất cho toàn bộ project.
"""

import json, csv
from datetime import datetime, timedelta
from pathlib  import Path
from typing   import Any
from utils.logger import get_logger

log      = get_logger(__name__)
DATA_DIR = Path("data")
LOGS_DIR = Path("logs")
OUT_DIR  = Path("outputs")
CACHE_DIR = DATA_DIR / "cache"


def _mk(*dirs):
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)


def today()    -> str: return datetime.now().strftime("%Y%m%d")
def tomorrow() -> str: return (datetime.now()+timedelta(days=1)).strftime("%Y%m%d")


def output_dir(date_str: str | None = None) -> Path:
    d = OUT_DIR / (date_str or today())
    _mk(d, d/"private")
    return d


# ── JSON helpers ──────────────────────────────────────────────────────────

def read_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        log.error(f"read_json {p}: {e}")
        return default


def write_json(path, data, indent=2) -> bool:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
        return True
    except Exception as e:
        log.error(f"write_json {p}: {e}")
        return False


# ── Watchlist ─────────────────────────────────────────────────────────────

def load_watchlist(use_tomorrow=False) -> dict:
    fname = "watchlist_tomorrow.json" if use_tomorrow else "watchlist.json"
    data  = read_json(DATA_DIR/fname, default={})
    if not data:
        log.warning("watchlist rỗng — dùng mặc định")
        return {"tickers":["VCB","BID","VHM","HPG","VIC"],
                "daily_compare_pair":["VCB","BID"],"sector":"Ngân hàng"}
    return data


def save_watchlist(data, tomorrow=False) -> bool:
    fname = "watchlist_tomorrow.json" if tomorrow else "watchlist.json"
    return write_json(DATA_DIR/fname, data)


# ── Customers ─────────────────────────────────────────────────────────────

def load_customers(vip_only=False) -> list:
    data = read_json(DATA_DIR/"customer_list.json", default=[])
    return [c for c in data if c.get("vip")] if vip_only else data


# ── Cache ─────────────────────────────────────────────────────────────────

def load_cache(key: str, date_str: str | None = None):
    _mk(CACHE_DIR)
    return read_json(CACHE_DIR/f"{key}_{date_str or today()}.json")


def save_cache(key: str, data, date_str: str | None = None) -> Path:
    _mk(CACHE_DIR)
    path = CACHE_DIR/f"{key}_{date_str or today()}.json"
    write_json(path, data)
    return path


# ── Alerts ────────────────────────────────────────────────────────────────

def append_alert(alert: dict, date_str: str | None = None):
    path   = output_dir(date_str)/f"alerts_{date_str or today()}.json"
    alerts = read_json(path, default=[])
    alert.setdefault("time", datetime.now().strftime("%H:%M:%S"))
    alerts.append(alert)
    write_json(path, alerts)


def load_alerts(date_str: str | None = None) -> list:
    return read_json(output_dir(date_str)/f"alerts_{date_str or today()}.json", default=[])


# ── Realtime CSV ──────────────────────────────────────────────────────────

def append_realtime_row(row: dict, date_str: str | None = None):
    _mk(LOGS_DIR)
    path        = LOGS_DIR/f"realtime_{date_str or today()}.csv"
    write_header = not path.exists()
    with open(path,"a",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        if write_header: w.writeheader()
        w.writerow(row)


def load_realtime_log(date_str: str | None = None):
    import pandas as pd
    path = LOGS_DIR/f"realtime_{date_str or today()}.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return df
    except Exception as e:
        log.error(f"load realtime log: {e}")
        return pd.DataFrame()


# ── EOD Summary ───────────────────────────────────────────────────────────

def load_eod_summary(date_str: str | None = None) -> dict:
    data = read_json(DATA_DIR/f"eod_summary_{date_str or today()}.json", default={})
    if not data:
        log.warning("eod_summary không tìm thấy")
    return data


def save_eod_summary(data, date_str: str | None = None) -> Path:
    path = DATA_DIR/f"eod_summary_{date_str or today()}.json"
    write_json(path, data)
    return path
