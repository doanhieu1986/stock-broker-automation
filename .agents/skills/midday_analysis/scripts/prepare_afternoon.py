"""
skills/midday_analysis/scripts/prepare_afternoon.py
Bước 4 ca trưa: In tóm tắt chuẩn bị phiên chiều 13h00.
"""

from datetime import datetime
from utils.data_loader import load_cache, load_alerts, output_dir, today
from utils.logger      import get_logger

log = get_logger(__name__)


def run() -> None:
    date_str   = today()
    morning    = load_cache("morning_session", date_str) or {}
    alerts     = load_alerts(date_str)
    out_dir    = output_dir(date_str)
    deep_files = list(out_dir.glob(f"deep_analysis_*_{date_str}.md"))
    vip_files  = list((out_dir / "private").glob(f"vip_*_{date_str}.docx"))
    watchlist  = morning.get("watchlist", [])
    notable    = [w for w in watchlist if abs(w.get("change_pct") or 0) >= 1.5]
    vn         = morning.get("vn_index", {})
    chg        = vn.get("change_pct", 0)
    crit       = sum(1 for a in alerts if a.get("level") == "critical")

    sep = "═" * 54
    print(f"\n╔{sep}╗")
    print(f"║  CHUẨN BỊ PHIÊN CHIỀU  |  "
          f"{datetime.now().strftime('%H:%M')}  |  "
          f"{datetime.now().strftime('%d/%m/%Y')}          ║")
    print(f"╠{sep}╣")
    print(f"║  PHIÊN SÁNG   VN-Index {chg:+.2f}%  "
          f"KL: {vn.get('volume_bil',0):,.0f} tỷ              ║")
    if notable:
        print(f"╠{sep}╣")
        print(f"║  WATCHLIST CẦN THEO DÕI PHIÊN CHIỀU                 ║")
        for w in notable[:3]:
            icon = "🔴" if (w.get("change_pct") or 0) < 0 else "🟢"
            c    = w.get("change_pct", 0)
            print(f"║  → {icon} {w['ticker']}: {c:+.2f}% sáng nay                        ║")
    print(f"╠{sep}╣")
    print(f"║  ✓ Phân tích sâu:   {len(deep_files)} mã hoàn thành                  ║")
    print(f"║  ✓ VIP reports:     {len(vip_files)} KH — chờ broker review          ║")
    print(f"║  ✓ Cảnh báo sáng:  {crit} cảnh báo khẩn cấp                  ║")
    print(f"╠{sep}╣")
    print(f"║  Bàn giao về trading-hours skill lúc 13:00           ║")
    print(f"╚{sep}╝\n")
