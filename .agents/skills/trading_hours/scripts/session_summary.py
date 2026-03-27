"""
skills/trading_hours/scripts/session_summary.py
Tổng kết phiên giao dịch sau 15h00.
Tóm tắt cảnh báo, phân tích on-demand, và bàn giao sang ca midday/EOD.
"""

import sys
from datetime import datetime
from pathlib  import Path
sys.path.insert(0, str(Path(__file__).parents[4]))

from utils.api_client  import fetch_cafef_index
from utils.data_loader import (
    load_watchlist, load_realtime_log, load_alerts,
    save_cache, output_dir, today
)
from utils.logger      import get_logger

log = get_logger(__name__)


def run() -> dict:
    """Tổng kết phiên — gọi ngay sau khi market đóng cửa 15h00."""
    log.info("Tổng kết phiên giao dịch...")
    date_str  = today()
    out_dir   = output_dir(date_str)
    watchlist = load_watchlist()
    tickers   = watchlist.get("tickers", [])

    # ── Chỉ số đóng cửa ───────────────────────────────────────────────────
    idx = fetch_cafef_index() or {}
    vn  = idx.get("vn_index", {})
    hnx = idx.get("hnx_index", {})

    # ── Top movers từ log realtime ─────────────────────────────────────────
    df        = load_realtime_log(date_str)
    wl_summary = _summarize_watchlist(df, tickers)

    # ── Cảnh báo trong ngày ────────────────────────────────────────────────
    alerts    = load_alerts(date_str)
    n_crit    = sum(1 for a in alerts if a.get("level") == "critical")
    n_imp     = sum(1 for a in alerts if a.get("level") == "important")

    # ── Phân tích on-demand đã thực hiện ──────────────────────────────────
    analysis_files = list(out_dir.glob("analysis_*.json"))

    summary = {
        "date":       date_str,
        "close_time": datetime.now().strftime("%H:%M:%S"),
        "indices": {
            "vn_index":  vn,
            "hnx_index": hnx,
        },
        "watchlist_summary": wl_summary,
        "alerts": {
            "total":    len(alerts),
            "critical": n_crit,
            "important": n_imp,
            "list":     alerts,
        },
        "on_demand_count": len(analysis_files),
        "on_demand_tickers": [
            f.stem.replace("analysis_", "").rsplit("_", 1)[0]
            for f in analysis_files
        ],
    }

    save_cache("session_summary", summary, date_str)
    _print_session_close(summary)
    return summary


def _summarize_watchlist(df, tickers: list[str]) -> list[dict]:
    """Tính hiệu suất cuối ngày từng mã trong watchlist."""
    result = []
    if df.empty:
        return result

    for ticker in tickers:
        sub = df[df["ticker"] == ticker]
        if sub.empty:
            continue
        last = sub.iloc[-1]
        result.append({
            "ticker":     ticker,
            "close":      float(last.get("price", 0)),
            "change_pct": float(last.get("change_pct", 0)),
            "max_vol":    int(sub["volume"].max()) if "volume" in sub else 0,
        })

    result.sort(key=lambda x: x["change_pct"], reverse=True)
    return result


def _print_session_close(s: dict) -> None:
    vn  = s["indices"].get("vn_index", {})
    hnx = s["indices"].get("hnx_index", {})
    al  = s["alerts"]
    sep = "═" * 54

    chg_vn  = vn.get("change_pct", 0)
    chg_hnx = hnx.get("change_pct", 0)

    print(f"\n╔{sep}╗")
    print(f"║  PHIÊN GIAO DỊCH KẾT THÚC — {datetime.now().strftime('%d/%m/%Y')} 15:00  ║")
    print(f"╠{sep}╣")
    print(f"║  VN-Index   {vn.get('value', 'N/A')!s:>8}  ({chg_vn:+.2f}%)  "
          f"KL: {vn.get('volume_bil', 0):,.0f} tỷ{'':>5}║"[:58])
    print(f"║  HNX-Index  {hnx.get('value', 'N/A')!s:>8}  ({chg_hnx:+.2f}%){'':>22}║"[:58])
    print(f"╠{sep}╣")
    print(f"║  Cảnh báo đã phát: {al['total']}  "
          f"({al['critical']}🔴 khẩn cấp, {al['important']}🟡 quan trọng){'':>10}║"[:58])
    print(f"║  Phân tích on-demand: {s['on_demand_count']} mã  "
          f"({', '.join(s['on_demand_tickers'][:4])}){'':>5}║"[:58])
    print(f"╠{sep}╣")
    print(f"║  Dữ liệu bàn giao EOD:{'':>31}║")
    print(f"║  → data/cache/session_summary_{today()}.json{'':>9}║")
    print(f"╚{sep}╝\n")
