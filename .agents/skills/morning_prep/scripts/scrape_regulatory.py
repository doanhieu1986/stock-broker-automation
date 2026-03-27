"""
skills/morning-prep/scripts/scrape_regulatory.py
Bước 3 ca sáng (7h00–7h30): Chính sách UBCKNN + sự kiện doanh nghiệp.
Output: data/cache/regulatory_{date}.json
"""

import sys
import re
from datetime import datetime, date, timedelta
from pathlib import Path

import requests
import feedparser

sys.path.insert(0, str(Path(__file__).parents[4]))
from utils.logger import api_call, section, Timer, log_output
from utils.api_helpers import with_retry, cache_write, load_watchlist, get_text

# ── Nguồn dữ liệu ────────────────────────────────────────────────────────────

UBCKNN_RSS   = "https://ssc.gov.vn/ubcknn/rss/tin-tuc"
VIETSTOCK_API = "https://events.vietstock.vn/data/geteventlist"  # public endpoint

PRIORITY_KEYWORDS = [
    "đình chỉ giao dịch", "hủy niêm yết", "phạt", "xử phạt",
    "phát hành thêm", "mua lại cổ phiếu quỹ", "thay đổi lãnh đạo",
    "tạm dừng", "giải thể",
]

TRACKED_EVENT_TYPES = {
    "GDKHQ":          "Ngày GD không hưởng quyền",
    "tra_co_tuc":     "Trả cổ tức",
    "hop_DHCD":       "Họp ĐHCĐ",
    "phat_hanh_them": "Phát hành thêm",
    "ket_qua_KD":     "Công bố KQKD",
}


# ── UBCKNN ────────────────────────────────────────────────────────────────────

@api_call("UBCKNN-RSS", "tin-tuc")
def _fetch_ubcknn() -> list[dict]:
    feed  = feedparser.parse(UBCKNN_RSS)
    items = []
    cutoff = datetime.now() - timedelta(hours=24)

    for entry in feed.entries[:30]:
        published = datetime(*entry.get("published_parsed", [2000,1,1,0,0,0])[:6])
        if published < cutoff:
            continue
        title = entry.get("title", "")
        link  = entry.get("link", "")
        items.append({
            "title":     title,
            "link":      link,
            "published": published.strftime("%H:%M %d/%m/%Y"),
            "priority":  any(kw in title.lower() for kw in PRIORITY_KEYWORDS),
        })
    return items


# ── Sự kiện doanh nghiệp (Vietstock) ─────────────────────────────────────────

@api_call("Vietstock", "event_calendar")
def _fetch_vietstock_events(days_ahead: int = 3) -> list[dict]:
    """Lấy sự kiện trong N ngày tới."""
    today    = date.today()
    end_date = today + timedelta(days=days_ahead)

    resp = requests.get(
        VIETSTOCK_API,
        params={
            "startDate": today.strftime("%d/%m/%Y"),
            "endDate":   end_date.strftime("%d/%m/%Y"),
            "pageSize":  50,
        },
        timeout=10,
        headers={"Referer": "https://finance.vietstock.vn/"},
    )
    resp.raise_for_status()
    data  = resp.json()
    items = []

    for ev in data.get("data", []):
        event_type = ev.get("EventType", "")
        if event_type not in TRACKED_EVENT_TYPES:
            continue
        items.append({
            "date":        ev.get("EventDate", "")[:10],
            "ticker":      ev.get("Code", ""),
            "event_type":  event_type,
            "event_label": TRACKED_EVENT_TYPES[event_type],
            "description": ev.get("EventTitle", ""),
        })
    return items


# ── Đánh dấu sự kiện liên quan watchlist ─────────────────────────────────────

def _tag_watchlist(events: list[dict], watchlist_tickers: list[str]) -> list[dict]:
    wl = set(t.upper() for t in watchlist_tickers)
    for ev in events:
        ev["in_watchlist"] = ev["ticker"].upper() in wl
    # Sắp xếp: watchlist trước, rồi theo ngày
    return sorted(events, key=lambda x: (not x["in_watchlist"], x["date"]))


# ── In terminal ───────────────────────────────────────────────────────────────

def _print(data: dict):
    section("CHÍNH SÁCH & SỰ KIỆN")

    ubck = data["ubcknn"]
    if ubck:
        print(f"  UBCKNN — {len(ubck)} thông báo mới trong 24h:")
        for item in ubck[:5]:
            flag = "⚠️ " if item["priority"] else "   "
            print(f"  {flag}{item['title'][:70]}")
            print(f"      {item['published']}  →  {item['link']}")
    else:
        print("  UBCKNN — Không có thông báo mới.")

    print()
    events = data["events"]
    if events:
        print(f"  SỰ KIỆN DOANH NGHIỆP (3 ngày tới) — {len(events)} sự kiện:")
        print(f"  {'Ngày':<12} {'Mã':<6} {'Loại':<28} {'Ghi chú'}")
        print(f"  {'─'*12} {'─'*6} {'─'*28} {'─'*20}")
        for ev in events[:10]:
            wl    = "★ " if ev["in_watchlist"] else "  "
            label = ev["event_label"][:26]
            print(f"  {wl}{ev['date']:<10} {ev['ticker']:<6} {label:<28} {ev['description'][:30]}")
    else:
        print("  Không có sự kiện doanh nghiệp đáng chú ý trong 3 ngày tới.")


# ── Main ─────────────────────────────────────────────────────────────────────

def run() -> dict:
    section("Bước 3 — Chính sách & sự kiện pháp lý")
    wl = load_watchlist()
    tickers = wl.get("tickers", [])

    with Timer("UBCKNN RSS"):
        ubck = with_retry(
            _fetch_ubcknn, retries=3, wait_sec=10,
            fallback=[], label="UBCKNN",
        )

    with Timer("Vietstock events"):
        events = with_retry(
            lambda: _fetch_vietstock_events(days_ahead=3),
            retries=3, wait_sec=10,
            fallback=[], label="Vietstock",
        )

    events = _tag_watchlist(events, tickers)

    # Đánh dấu thông báo UBCKNN liên quan watchlist
    wl_set = set(t.upper() for t in tickers)
    for item in ubck:
        item["in_watchlist"] = any(t in item["title"].upper() for t in wl_set)

    data = {
        "fetched_at": datetime.now().isoformat(),
        "ubcknn":     ubck,
        "events":     events,
        "priority_alerts": [e for e in events if e.get("in_watchlist")]
                          + [u for u in ubck if u.get("priority") or u.get("in_watchlist")],
    }

    path = cache_write("regulatory", data)
    log_output(str(path), path.stat().st_size / 1024)
    _print(data)
    return data


if __name__ == "__main__":
    run()
