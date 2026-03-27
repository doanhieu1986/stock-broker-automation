"""
skills/eod_report/scripts/eod_handoff.py
Bước 4 ca EOD: Tạo file JSON bàn giao sạch cho ca after-hours.
"""

from datetime import datetime

from utils.data_loader import (
    load_cache, load_alerts, save_eod_summary, output_dir, today
)
from utils.logger import get_logger

log = get_logger(__name__)


def run() -> dict:
    """Đóng gói dữ liệu sạch → data/eod_summary_{date}.json."""
    log.info("Chuẩn bị dữ liệu bàn giao after-hours...")
    date_str = today()
    eod      = load_cache("eod_raw", date_str) or {}
    alerts   = load_alerts(date_str)
    out_dir  = output_dir(date_str)

    idx      = eod.get("indices", {})
    vn       = idx.get("vn_index", {})
    hnx      = idx.get("hnx_index", {})
    gainers  = eod.get("top_gainers", [])
    losers   = eod.get("top_losers",  [])
    wl       = eod.get("watchlist_eod", [])
    foreign  = eod.get("foreign_flow", {})

    # Notable events tự động
    notable = []
    net = foreign.get("net_bil", 0)
    if abs(net) > 50:
        action = "mua ròng" if net > 0 else "bán ròng"
        notable.append(f"Khối ngoại {action} {abs(net):,.0f} tỷ hôm nay")
    for w in wl:
        if abs(w.get("change_pct", 0)) >= 3:
            notable.append(
                f"{w['ticker']} {w['change_pct']:+.2f}% — "
                f"KL {w['volume']:,}K cp"
            )

    # One-liner thị trường
    chg = vn.get("change_pct", 0)
    vol = vn.get("volume_bil", 0)
    direction = "tăng" if chg >= 0 else "giảm"
    one_liner = (
        f"Thị trường {direction} {chg:+.2f}%, "
        f"thanh khoản {vol:,.0f} tỷ"
        + (f", khối ngoại {'mua' if net >= 0 else 'bán'} ròng {abs(net):,.0f} tỷ." if net else ".")
    )

    summary = {
        "date": date_str,
        "market": {
            "vn_index":    vn,
            "hnx_index":   hnx,
            "foreign_flow": foreign,
        },
        "top_gainers":     gainers[:5],
        "top_losers":      losers[:5],
        "watchlist_summary": [
            {k: w[k] for k in ("ticker","close","change_pct","volume") if k in w}
            for w in wl
        ],
        "notable_events":  notable,
        "session_one_liner": one_liner,
        "alerts_count":   len(alerts),
        "files": {
            "eod_report":     str(out_dir / f"eod_report_{date_str}.docx"),
            "customer_notes": str(out_dir / f"private/customer_notes_{date_str}.md"),
        },
    }

    save_eod_summary(summary, date_str)
    _print_handoff(summary, out_dir)
    return summary


def _print_handoff(s: dict, out_dir) -> None:
    vn  = s["market"].get("vn_index", {})
    chg = vn.get("change_pct", 0)
    sep = "═" * 54
    al  = s["alerts_count"]

    print(f"\n╔{sep}╗")
    print(f"║  CA TỔNG KẾT HOÀN THÀNH — "
          f"{datetime.now().strftime('%d/%m/%Y %H:%M')}{'':>14}║"[:58])
    print(f"╠{sep}╣")
    print(f"║  Báo cáo EOD   ✓ Chờ broker review & ký duyệt{'':>7}║")
    print(f"║  VN-Index      ✓ {chg:+.2f}% | {vn.get('value','?')} điểm{'':>22}║"[:58])
    print(f"║  Cảnh báo      ✓ {al} cảnh báo trong ngày{'':>22}║"[:58])
    print(f"║  Data bàn giao ✓ data/eod_summary_{s['date']}.json{'':>5}║"[:58])
    print(f"╠{sep}╣")
    print(f"║  Việc còn lại cho broker:{'':>29}║")
    print(f"║  □ Điền Section 4 (khuyến nghị) vào EOD report{'':>6}║")
    print(f"║  □ Gọi điện nhóm A khách hàng{'':>24}║")
    print(f"║  □ Duyệt newsletter trước khi gửi (18h30–19h30){'':>5}║")
    print(f"╠{sep}╣")
    print(f"║  Bàn giao after-hours skill — Newsletter 18:00{'':>7}║")
    print(f"╚{sep}╝\n")
