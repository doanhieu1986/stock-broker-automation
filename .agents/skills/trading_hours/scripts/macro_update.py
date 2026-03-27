"""
skills/trading_hours/scripts/macro_update.py
Chế độ 3 — Cập nhật vĩ mô mỗi 2 tiếng: 9h30, 11h30, 13h30, 15h00.
Gọi độc lập hoặc qua scheduler trong price_monitor.
"""

import sys
from datetime import datetime
from pathlib  import Path
sys.path.insert(0, str(Path(__file__).parents[4]))
from utils.api_client  import fetch_yahoo_quote, fetch_usd_vnd, fetch_rss
from utils.data_loader import load_realtime_log, save_cache, today
from utils.logger      import get_logger

log = get_logger(__name__)

MACRO_NEWS_SOURCES = {
    "vnexpress": "https://vnexpress.net/kinh-doanh/rss",
    "cafef":     "https://cafef.vn/tai-chinh-quoc-te.rss",
}

MACRO_KEYWORDS = [
    "lãi suất", "tỷ giá", "Fed", "NHNN", "GDP", "lạm phát",
    "xuất khẩu", "FDI", "trái phiếu", "room tín dụng", "tăng trưởng",
]


def run() -> dict:
    """
    Cập nhật vĩ mô và in ra terminal.
    Được gọi vào: 9h30, 11h30, 13h30, 15h00.
    """
    now      = datetime.now()
    slot     = _get_slot(now)
    date_str = today()

    log.info(f"── Macro Update {slot} ──────────────────────────────")

    result = {
        "slot":       slot,
        "timestamp":  now.isoformat(),
        "fx": {},
        "commodities": {},
        "news": [],
    }

    # ── Hàng hóa & ngoại tệ ───────────────────────────────────────────────
    oil  = fetch_yahoo_quote("BZ=F")
    gold = fetch_yahoo_quote("GC=F")
    usd  = fetch_usd_vnd()

    if oil:
        result["commodities"]["oil_brent"] = oil
        log.info(f"  Dầu Brent  ${oil['price']:,.1f}  ({oil['change_pct']:+.2f}% từ đầu phiên)")
    if gold:
        result["commodities"]["gold"] = gold
        log.info(f"  Vàng       ${gold['price']:,.0f}  ({gold['change_pct']:+.2f}% từ đầu phiên)")
    if usd:
        result["fx"]["usd_vnd"] = usd
        log.info(f"  USD/VND    {usd:,.0f}")

    # ── Tin tức vĩ mô mới ─────────────────────────────────────────────────
    all_news = []
    for src, url in MACRO_NEWS_SOURCES.items():
        items = fetch_rss(url, max_items=20)
        for item in items:
            text = f"{item['title']} {item['summary']}".lower()
            if any(kw in text for kw in MACRO_KEYWORDS):
                item["source"] = src
                all_news.append(item)

    # Bỏ trùng theo title, lấy tối đa 3 tin
    seen   = set()
    unique = []
    for n in all_news:
        if n["title"] not in seen:
            seen.add(n["title"])
            unique.append(n)
    result["news"] = unique[:3]

    # ── Bổ sung: tóm tắt phiên sáng nếu slot = 13h30 ─────────────────────
    if slot == "13:30":
        result["morning_recap"] = _morning_recap(date_str)

    # ── In ra terminal ────────────────────────────────────────────────────
    _print_update(result, slot)

    save_cache(f"macro_{slot.replace(':', '')}", result, date_str)
    return result


def _get_slot(dt: datetime) -> str:
    hour, minute = dt.hour, dt.minute
    if   hour == 9:  return "09:30"
    elif hour == 11: return "11:30"
    elif hour == 13: return "13:30"
    else:            return "15:00"


def _morning_recap(date_str: str) -> dict:
    """Tóm tắt nhanh phiên sáng 9h-11h30 cho update 13h30."""
    df = load_realtime_log(date_str)
    if df.empty:
        return {}

    morning = df[df["timestamp"].dt.hour < 12] if "timestamp" in df.columns else df
    if morning.empty:
        return {}

    try:
        return {
            "avg_change": round(float(morning["change_pct"].mean()), 2),
            "max_change": round(float(morning["change_pct"].max()), 2),
            "min_change": round(float(morning["change_pct"].min()), 2),
            "total_tickers": morning["ticker"].nunique(),
        }
    except Exception:
        return {}


def _print_update(data: dict, slot: str) -> None:
    sep = "─" * 48
    print(f"\n{sep}")
    print(f"  MACRO UPDATE  |  {slot}  |  {datetime.now().strftime('%d/%m/%Y')}")
    print(sep)

    # Hàng hóa
    oil  = data["commodities"].get("oil_brent", {})
    gold = data["commodities"].get("gold", {})
    usd  = data["fx"].get("usd_vnd")

    if oil or gold:
        print("  HÀNG HÓA & NGOẠI TỆ")
        if oil:
            print(f"  Dầu Brent   ${oil['price']:>7,.1f}  ({oil['change_pct']:+.2f}% từ đầu phiên)")
        if gold:
            print(f"  Vàng        ${gold['price']:>7,.0f}  ({gold['change_pct']:+.2f}% từ đầu phiên)")
        if usd:
            print(f"  USD/VND      {usd:>9,.0f}")

    # Tin tức
    news = data.get("news", [])
    if news:
        print(f"\n  TIN TỨC VĨ MÔ ({len(news)} tin từ 2 tiếng qua)")
        for n in news:
            src   = n.get("source", "").upper()
            title = n.get("title", "")[:60]
            pub   = n.get("published", "")[:16]
            print(f"  • [{src}] {title}")
            if pub:
                print(f"    {pub}")
    else:
        print("\n  → Không có tin vĩ mô mới đáng chú ý trong khung này.")

    # Tóm tắt phiên sáng (slot 13:30)
    recap = data.get("morning_recap", {})
    if recap:
        print(f"\n  TÓM TẮT PHIÊN SÁNG")
        print(f"  TB change watchlist: {recap.get('avg_change', 0):+.2f}%  "
              f"Max: {recap.get('max_change', 0):+.2f}%  "
              f"Min: {recap.get('min_change', 0):+.2f}%")

    print(sep + "\n")
