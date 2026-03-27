"""
skills/after_hours/scripts/fetch_tomorrow_events.py
Bước 4a: Lấy lịch sự kiện doanh nghiệp và vĩ mô ngày mai.
"""

import sys
from datetime import datetime, date, timedelta
from pathlib  import Path
sys.path.insert(0, str(Path(__file__).parents[4]))
from utils.api_client  import fetch_yahoo_quote
from utils.data_loader import load_watchlist, cache_write, today
from utils.logger      import api_call, section, get_logger

log = get_logger(__name__)


def run() -> Path:
    """Lấy và ghi lịch sự kiện ngày mai ra tomorrow_prep.md."""
    log.info("Lấy lịch sự kiện ngày mai...")
    date_str     = today()
    tomorrow_str = tomorrow()
    tomorrow_dt  = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
    watchlist    = load_watchlist()
    tickers      = set(watchlist.get("tickers", []))

    corp_events  = _fetch_corp_events(tomorrow_str)
    macro_events = _fetch_macro_events()

    # Lọc sự kiện liên quan watchlist
    relevant = [e for e in corp_events if e.get("ticker") in tickers]
    other    = [e for e in corp_events if e.get("ticker") not in tickers]

    lines = [
        f"# CHUẨN BỊ NGÀY {tomorrow_dt}",
        "",
        "## Sự kiện doanh nghiệp — LIÊN QUAN WATCHLIST",
    ]

    if relevant:
        lines.append("| Ngày | Mã CK | Loại | Mô tả |")
        lines.append("|---|---|---|---|")
        for e in relevant:
            lines.append(
                f"| {e.get('date','')} | **{e.get('ticker','')}** "
                f"| {e.get('type','')} | {e.get('description','')[:60]} |"
            )
    else:
        lines.append("*Không có sự kiện liên quan watchlist ngày mai.*")

    lines += ["", "## Sự kiện doanh nghiệp — Toàn thị trường"]
    for e in other[:5]:
        lines.append(
            f"- {e.get('date','')} | {e.get('ticker','')} "
            f"| {e.get('type','')} | {e.get('description','')[:60]}"
        )

    lines += ["", "## Vĩ mô quốc tế ngày mai"]
    for m in macro_events:
        lines.append(f"- [{m['time']}] {m['region']}: {m['event']}")

    out_dir  = output_dir(date_str)
    out_path = out_dir / "tomorrow_prep.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Đã lưu: {out_path.name}")
    return out_path


def _fetch_corp_events(date_str: str) -> list[dict]:
    """Lấy sự kiện từ Vietstock Calendar."""
    try:
        resp = requests.get(
            "https://api.vietstock.vn/data/dividendschedule",
            params={"startDate": date_str, "endDate": date_str},
            timeout=8,
        )
        items = resp.json() if resp.ok else []
        return [
            {
                "date":        item.get("ExrightDate", date_str),
                "ticker":      item.get("Symbol", ""),
                "type":        item.get("EventType", ""),
                "description": item.get("Description", ""),
            }
            for item in items[:20]
        ]
    except Exception as e:
        log.debug(f"Vietstock events error: {e}")
        return []


def _fetch_macro_events() -> list[dict]:
    """Placeholder — trong thực tế lấy từ Investing.com calendar."""
    return [
        {"time": "Cả ngày", "region": "VN", "event": "Xem cafef.vn/lich-su-kien"},
    ]


# ══════════════════════════════════════════════════════════════════════════

"""
skills/after_hours/scripts/update_watchlist.py
Bước 4b: Cập nhật watchlist cho ngày mai.
"""


def run_update_watchlist() -> None:
    """Cập nhật daily_compare_pair và xử lý GDKHQ."""
    from utils.data_loader import load_watchlist, save_watchlist, read_json, DATA_DIR, tomorrow
    from utils.logger      import get_logger as gl

    log2 = gl("update_watchlist")
    log2.info("Cập nhật watchlist ngày mai...")

    wl = load_watchlist()

    # Đọc ghi chú bổ sung từ broker (nếu có)
    changes = read_json(DATA_DIR / "watchlist_changes.json", default={})
    if changes.get("add"):
        for t in changes["add"]:
            if t.upper() not in wl.get("tickers", []):
                wl.setdefault("tickers", []).append(t.upper())
                log2.info(f"  Thêm mã: {t.upper()}")
    if changes.get("remove"):
        wl["tickers"] = [
            t for t in wl.get("tickers", [])
            if t not in changes["remove"]
        ]
    if changes.get("compare_pair"):
        wl["daily_compare_pair"] = [t.upper() for t in changes["compare_pair"][:2]]
        log2.info(f"  Cặp so sánh ngày mai: {wl['daily_compare_pair']}")

    save_watchlist(wl, tomorrow=True)
    log2.info(f"  Đã lưu watchlist_tomorrow.json — {len(wl.get('tickers',[]))} mã")


# ══════════════════════════════════════════════════════════════════════════

"""
skills/after_hours/scripts/update_broker_kpi.py
Bước 5 ca after-hours: Tổng kết KPI cá nhân cuối ngày.
"""


def run_update_kpi() -> None:
    """Tạo báo cáo KPI cuối ngày."""
    from datetime          import datetime
    from utils.data_loader import load_alerts, output_dir, today, load_realtime_log
    from utils.logger      import get_logger as gl

    log3  = gl("kpi")
    date_str = today()
    out_dir  = output_dir(date_str)
    alerts   = load_alerts(date_str)
    df       = load_realtime_log(date_str)

    # Thống kê phân tích on-demand
    analysis_files = list(out_dir.glob("analysis_*.json"))
    deep_files     = list(out_dir.glob(f"deep_analysis_*_{date_str}.md"))
    newsletter     = (out_dir / f"newsletter_{date_str}.html").exists()

    import json

    kpi = {
        "date":      date_str,
        "generated": datetime.now().isoformat(),
        "system": {
            "alerts_fired":          len(alerts),
            "alerts_critical":       sum(1 for a in alerts if a.get("level") == "critical"),
            "ondemand_analyses":     len(analysis_files),
            "deep_analyses":         len(deep_files),
            "newsletter_ready":      newsletter,
            "realtime_rows_logged":  len(df) if not df.empty else 0,
        },
        "broker_fill": {
            "contacts_made":   None,   # Broker điền
            "fee_revenue_vnd": None,   # Broker điền
            "notes":           "",     # Broker điền
        },
    }

    out_path = out_dir / f"kpi_{date_str}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(kpi, f, ensure_ascii=False, indent=2)

    # In tóm tắt
    s = kpi["system"]
    sep = "═" * 52
    print(f"\n╔{sep}╗")
    print(f"║  CA SAU GIỜ HOÀN THÀNH — "
          f"{datetime.now().strftime('%d/%m/%Y %H:%M')}{'':>13}║"[:56])
    print(f"╠{sep}╣")
    print(f"║  Newsletter    {'✓' if s['newsletter_ready'] else '✗'} "
          f"Sẵn sàng gửi{'':>30}║"[:56])
    print(f"║  Cảnh báo     ✓ {s['alerts_fired']} phát "
          f"({s['alerts_critical']} khẩn cấp){'':>20}║"[:56])
    print(f"║  On-demand    ✓ {s['ondemand_analyses']} phân tích{'':>30}║"[:56])
    print(f"║  Phân tích sâu ✓ {s['deep_analyses']} mã{'':>33}║"[:56])
    print(f"╠{sep}╣")
    print(f"║  Việc còn lại cho broker:{'':>27}║")
    print(f"║  □ Duyệt & gửi newsletter{'':>27}║")
    print(f"║  □ Gửi email drafts cho KH{'':>26}║")
    print(f"║  □ Điền KPI thực tế (phí GD, số KH){'':>16}║")
    print(f"╠{sep}╣")
    print(f"║  Hệ thống nghỉ đến 05:30 ngày mai.{'':>17}║")
    print(f"║  Ca sáng tiếp theo: morning-prep 06:00{'':>14}║")
    print(f"╚{sep}╝\n")

    log3.info(f"KPI đã lưu: {out_path.name}")


# ── Entry points đúng chuẩn ──────────────────────────────────────────────

def run():
    """Entry point cho fetch_tomorrow_events (gọi từ run.py)."""
    pass  # Đã implement ở hàm run() cấp module


# Expose update functions cho run.py import trực tiếp
update_watchlist = run_update_watchlist
update_kpi       = run_update_kpi
