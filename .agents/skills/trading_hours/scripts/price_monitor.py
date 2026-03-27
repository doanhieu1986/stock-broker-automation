"""
skills/trading-hours/scripts/price_monitor.py
Chế độ 1: Monitor nền — Poll giá mỗi 30 giây, phát cảnh báo.
Output: logs/realtime_{date}.csv  +  outputs/{date}/alerts_{date}.json
"""

import sys
import csv
import json
import time
import signal
import threading
from datetime import datetime, date, time as dtime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parents[4]))
from utils.logger import section, log_output, print_box
from utils.api_helpers import (
    with_retry, output_dir, load_watchlist, load_customers,
    get_json, fmt_pct, fmt_price, fmt_volume,
)

# ── Cấu hình ─────────────────────────────────────────────────────────────────

POLL_INTERVAL   = 30        # giây
PRICE_ALERT_WL  = 2.0       # % — watchlist thường
PRICE_ALERT_KH  = 3.0       # % — cổ phiếu khách hàng
INDEX_ALERT     = 1.5       # % VN-Index từ đóng cửa hôm qua
VOL_WARN_MULT   = 1.5       # x TB 20 phiên
VOL_CRIT_MULT   = 2.5       # x TB 20 phiên
COOLDOWN_SEC    = 600       # 10 phút không báo lại cùng mã + cùng cấp

MARKET_OPEN  = dtime(9, 0)
LUNCH_START  = dtime(11, 30)
LUNCH_END    = dtime(13, 0)
MARKET_CLOSE = dtime(15, 0)
ATO_END      = dtime(9, 15)
ATC_START    = dtime(14, 30)

CAFEF_PRICE_URL  = "https://s.cafef.vn/LiveChartDatas/GetDataChartTheoThoiGian"
VNDIRECT_URL     = "https://finfo-api.vndirect.com.vn/v4/stocks"


# ── Trạng thái toàn cục ───────────────────────────────────────────────────────

class MonitorState:
    def __init__(self):
        self.running       = True
        self.alerts        = []           # list[dict]
        self.last_alert_ts = {}           # {(ticker, level): timestamp}
        self.prev_prices   = {}           # {ticker: price}
        self.vol_avg_20    = {}           # {ticker: volume}
        self.lock          = threading.Lock()

    def record_alert(self, alert: dict):
        with self.lock:
            self.alerts.append(alert)

    def in_cooldown(self, ticker: str, level: str) -> bool:
        key = (ticker, level)
        last = self.last_alert_ts.get(key, 0)
        return (time.time() - last) < COOLDOWN_SEC

    def set_alerted(self, ticker: str, level: str):
        self.last_alert_ts[(ticker, level)] = time.time()


STATE = MonitorState()


# ── Helpers thời gian ─────────────────────────────────────────────────────────

def market_is_open() -> bool:
    now = datetime.now().time()
    if now < MARKET_OPEN or now >= MARKET_CLOSE:
        return False
    if LUNCH_START <= now < LUNCH_END:
        return False
    return True


def is_ato() -> bool:
    return MARKET_OPEN <= datetime.now().time() < ATO_END


def is_atc() -> bool:
    return datetime.now().time() >= ATC_START


# ── Fetch giá realtime ────────────────────────────────────────────────────────

def _fetch_cafef(tickers: list[str]) -> dict:
    """Lấy giá realtime từ CafeF."""
    result = {}
    for ticker in tickers:
        try:
            resp = requests.get(
                CAFEF_PRICE_URL,
                params={"Symbol": ticker, "StartDate": "", "EndDate": "", "Resolution": "1"},
                timeout=8,
                headers={"Referer": "https://cafef.vn/"},
            )
            resp.raise_for_status()
            data = resp.json()
            if data and data.get("Data"):
                last = data["Data"][-1]
                result[ticker] = {
                    "price":  last.get("Close", None),
                    "volume": last.get("Volume", 0),
                    "high":   last.get("High"),
                    "low":    last.get("Low"),
                }
        except Exception:
            result[ticker] = {"price": None, "volume": 0}
    return result


def _fetch_vndirect(tickers: list[str]) -> dict:
    """Fallback: VNDirect API."""
    result = {}
    try:
        codes = ",".join(tickers)
        data  = get_json(
            VNDIRECT_URL,
            params={"q": f"code:{codes}", "fields": "code,matchPrice,matchVolume", "size": 100},
            timeout=10,
        )
        for item in data.get("data", []):
            result[item["code"]] = {
                "price":  item.get("matchPrice"),
                "volume": item.get("matchVolume", 0),
            }
    except Exception:
        pass
    return result


def fetch_prices(tickers: list[str]) -> dict:
    data = with_retry(
        lambda: _fetch_cafef(tickers),
        retries=2, wait_sec=5,
        fallback={},
        label="CafeF",
    )
    # Bổ sung mã thiếu từ VNDirect
    missing = [t for t in tickers if t not in data or data[t]["price"] is None]
    if missing:
        backup = with_retry(
            lambda: _fetch_vndirect(missing),
            retries=2, wait_sec=5,
            fallback={},
            label="VNDirect fallback",
        )
        data.update(backup)
    return data


# ── Ghi CSV realtime ──────────────────────────────────────────────────────────

_csv_path: Path = None
_csv_writer     = None
_csv_file       = None

def _init_csv():
    global _csv_path, _csv_writer, _csv_file
    ds        = date.today().strftime("%Y%m%d")
    log_dir   = Path("logs")
    log_dir.mkdir(exist_ok=True)
    _csv_path = log_dir / f"realtime_{ds}.csv"
    _csv_file = open(_csv_path, "a", newline="", encoding="utf-8")
    _csv_writer = csv.writer(_csv_file)
    if _csv_path.stat().st_size == 0:
        _csv_writer.writerow(["timestamp", "ticker", "price", "volume", "change_pct"])


def _log_prices(prices: dict, prev_prices: dict):
    ts = datetime.now().strftime("%H:%M:%S")
    for ticker, info in prices.items():
        price = info.get("price")
        vol   = info.get("volume", 0)
        prev  = prev_prices.get(ticker)
        chg   = ((price - prev) / prev * 100) if price and prev else None
        _csv_writer.writerow([ts, ticker, price, vol, round(chg, 4) if chg else ""])
    _csv_file.flush()


# ── Logic cảnh báo ────────────────────────────────────────────────────────────

def _check_price_alerts(prices: dict, prev_prices: dict, kh_tickers: set):
    for ticker, info in prices.items():
        price = info.get("price")
        prev  = prev_prices.get(ticker)
        if not price or not prev:
            continue

        chg_15m = (price - prev) / prev * 100    # xấp xỉ 15 phút nếu poll 30s
        threshold = PRICE_ALERT_KH if ticker in kh_tickers else PRICE_ALERT_WL

        if abs(chg_15m) < threshold:
            continue

        level = "🔴" if ticker in kh_tickers else "🟡"
        if STATE.in_cooldown(ticker, level):
            continue

        alert = {
            "time":   datetime.now().strftime("%H:%M"),
            "ticker": ticker,
            "price":  price,
            "change_pct": round(chg_15m, 2),
            "volume": info.get("volume", 0),
            "level":  level,
            "type":   "price",
        }
        STATE.record_alert(alert)
        STATE.set_alerted(ticker, level)
        _print_alert(alert)


def _check_volume_alerts(prices: dict):
    if is_ato() or is_atc():
        return    # tắt cảnh báo volume trong ATO/ATC

    for ticker, info in prices.items():
        vol     = info.get("volume", 0)
        avg     = STATE.vol_avg_20.get(ticker)
        if not avg or avg == 0:
            continue

        ratio = vol / avg
        if ratio >= VOL_CRIT_MULT:
            level = "🔴"
        elif ratio >= VOL_WARN_MULT:
            level = "🟡"
        else:
            continue

        if STATE.in_cooldown(ticker, f"vol_{level}"):
            continue

        alert = {
            "time":       datetime.now().strftime("%H:%M"),
            "ticker":     ticker,
            "volume":     vol,
            "vol_ratio":  round(ratio, 1),
            "level":      level,
            "type":       "volume",
        }
        STATE.record_alert(alert)
        STATE.set_alerted(ticker, f"vol_{level}")
        _print_alert(alert)


def _print_alert(alert: dict):
    ts = alert["time"]
    if alert["type"] == "price":
        chg = fmt_pct(alert["change_pct"])
        vol = fmt_volume(alert["volume"] / 1000) if alert["volume"] else "—"
        print(f"[{ts}] {alert['level']} {alert['ticker']:6} {chg:>8}  "
              f"Giá: {fmt_price(alert['price'])}  KL: {vol}")
    else:
        print(f"[{ts}] {alert['level']} {alert['ticker']:6} KL đột biến "
              f"x{alert['vol_ratio']:.1f} TB")


# ── Lưu alerts JSON ───────────────────────────────────────────────────────────

def _save_alerts():
    ds   = date.today().strftime("%Y%m%d")
    path = output_dir(ds) / f"alerts_{ds}.json"
    with STATE.lock:
        data = {"date": ds, "total": len(STATE.alerts), "alerts": STATE.alerts}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log_output(str(path), path.stat().st_size / 1024)
    return path


# ── Vòng lặp chính ───────────────────────────────────────────────────────────

def run():
    wl      = load_watchlist()
    tickers = wl.get("tickers", [])
    if not tickers:
        print("⚠ Watchlist trống — thêm mã vào data/watchlist.json")
        return

    # Tập mã của khách hàng
    customers  = load_customers()
    kh_tickers = set()
    for c in customers:
        for h in c.get("holdings", []):
            kh_tickers.add(h["ticker"].upper())

    ds = date.today().strftime("%Y%m%d")
    section(f"Monitor khởi động — {len(tickers)} mã  |  {len(kh_tickers)} mã KH")
    _init_csv()

    def _stop(sig, frame):
        STATE.running = False
        print("\n[Monitor] Đang dừng...")

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    # Lần poll đầu tiên để lấy giá baseline
    prices = fetch_prices(tickers)
    STATE.prev_prices = {t: i.get("price") for t, i in prices.items()}

    while STATE.running:
        if not market_is_open():
            phase = "Nghỉ trưa" if LUNCH_START <= datetime.now().time() < LUNCH_END else "Ngoài giờ GD"
            print(f"[{datetime.now():%H:%M}] {phase} — monitor tạm dừng")
            time.sleep(60)
            continue

        prices = fetch_prices(tickers)
        _log_prices(prices, STATE.prev_prices)
        _check_price_alerts(prices, STATE.prev_prices, kh_tickers)
        _check_volume_alerts(prices)

        # Cập nhật prev
        for t, i in prices.items():
            if i.get("price"):
                STATE.prev_prices[t] = i["price"]

        # Lưu alerts định kỳ
        if len(STATE.alerts) % 5 == 0 and STATE.alerts:
            _save_alerts()

        time.sleep(POLL_INTERVAL)

    # Kết thúc phiên
    if _csv_file:
        _csv_file.close()
    alerts_path = _save_alerts()

    print_box(
        f"PHIÊN KẾT THÚC — {date.today().strftime('%d/%m/%Y')}",
        [
            f"Tổng cảnh báo: {len(STATE.alerts)}",
            f"  🔴 khẩn cấp: {sum(1 for a in STATE.alerts if a['level']=='🔴')}",
            f"  🟡 quan trọng: {sum(1 for a in STATE.alerts if a['level']=='🟡')}",
            f"Log: logs/realtime_{ds}.csv",
            f"Alerts: {alerts_path}",
        ]
    )


if __name__ == "__main__":
    run()
