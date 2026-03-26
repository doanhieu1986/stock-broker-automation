"""
skills/trading_hours/scripts/alert_engine.py
Engine phát hiện và phân loại cảnh báo biến động giá và khối lượng.
"""

from datetime import datetime, time as dtime
from collections import defaultdict

from utils.api_client  import fetch_cafef_index
from utils.data_loader import today
from utils.logger      import get_logger

log = get_logger(__name__)

PRICE_CRITICAL  = 3.0
PRICE_IMPORTANT = 2.0
INDEX_CRITICAL  = 1.5
VOL_HIGH        = 1.5
VOL_SPIKE       = 2.5
COOLDOWN_MIN    = 10

ATO_START, ATO_END = dtime(9, 0),  dtime(9, 15)
ATC_START, ATC_END = dtime(14, 30), dtime(15, 0)


class AlertEngine:
    def __init__(self, tickers: list[str]):
        self.tickers   = tickers
        self._last_alert: dict[str, dict[str, datetime]] = defaultdict(dict)
        self._vol_avg  = {t: 1000 for t in tickers}   # default 1,000K cp

    def check_price(self, ticker: str, current: dict, previous: dict | None) -> list[dict]:
        alerts = []
        chg    = current.get("change_pct", 0)
        level  = ("critical"  if abs(chg) >= PRICE_CRITICAL  else
                  "important" if abs(chg) >= PRICE_IMPORTANT else None)
        if level and self._can_alert(ticker, level):
            alerts.append({
                "type":    "price",
                "level":   level,
                "ticker":  ticker,
                "value":   chg,
                "message": (f"{'CẢNH BÁO' if level=='critical' else 'QUAN TÂM'}: "
                            f"{ticker} {chg:+.2f}% | "
                            f"Giá: {current.get('price',0):,.1f} | "
                            f"KL: {current.get('volume',0):,}K cp"),
                "time": datetime.now().strftime("%H:%M:%S"),
            })
            self._mark_alerted(ticker, level)
        return alerts

    def check_volume(self, ticker: str, quote: dict) -> dict | None:
        if self._is_ato_atc():
            return None
        vol = quote.get("volume", 0)
        avg = self._vol_avg.get(ticker, 0)
        if not avg:
            return None
        ratio = vol / avg
        if ratio >= VOL_SPIKE and self._can_alert(ticker, "vol_spike"):
            self._mark_alerted(ticker, "vol_spike")
            return {"type": "volume", "level": "critical", "ticker": ticker,
                    "value": ratio,
                    "message": f"KL ĐỘT BIẾN: {ticker} — {ratio:.1f}x TB | {vol:,}K cp",
                    "time": datetime.now().strftime("%H:%M:%S")}
        if ratio >= VOL_HIGH and self._can_alert(ticker, "vol_high"):
            self._mark_alerted(ticker, "vol_high")
            return {"type": "volume", "level": "important", "ticker": ticker,
                    "value": ratio,
                    "message": f"KL tăng: {ticker} — {ratio:.1f}x TB | {vol:,}K cp",
                    "time": datetime.now().strftime("%H:%M:%S")}
        return None

    def check_index(self) -> dict | None:
        idx = fetch_cafef_index()
        if not idx:
            return None
        vn  = idx.get("vn_index", {})
        chg = vn.get("change_pct", 0)
        if abs(chg) >= INDEX_CRITICAL and self._can_alert("VNINDEX", "index"):
            self._mark_alerted("VNINDEX", "index")
            return {"type": "index", "level": "critical", "ticker": "VNINDEX",
                    "value": chg,
                    "message": (f"VN-Index {chg:+.2f}% so với đóng cửa hôm qua | "
                                f"Điểm: {vn.get('value','N/A')}"),
                    "time": datetime.now().strftime("%H:%M:%S")}
        return None

    def _can_alert(self, ticker: str, level: str) -> bool:
        last = self._last_alert[ticker].get(level)
        if not last:
            return True
        return (datetime.now() - last).total_seconds() / 60 >= COOLDOWN_MIN

    def _mark_alerted(self, ticker: str, level: str) -> None:
        self._last_alert[ticker][level] = datetime.now()

    def _is_ato_atc(self) -> bool:
        t = datetime.now().time()
        return (ATO_START <= t <= ATO_END) or (ATC_START <= t <= ATC_END)
