"""
skills/midday_analysis/scripts/summarize_morning_session.py
Bước 1 ca trưa: Tóm tắt phiên sáng từ log realtime.
"""

import sys
from datetime import datetime
from pathlib  import Path
sys.path.insert(0, str(Path(__file__).parents[4]))
from utils.api_client  import fetch_cafef_index
from utils.data_loader import load_watchlist, load_realtime_log, load_alerts, save_cache, today
from utils.logger      import get_logger

log = get_logger(__name__)


def run() -> dict:
    log.info("Tóm tắt phiên sáng...")
    date_str  = today()
    watchlist = load_watchlist()
    tickers   = watchlist.get("tickers", [])
    df        = load_realtime_log(date_str)
    alerts    = load_alerts(date_str)
    idx       = fetch_cafef_index() or {}
    vn        = idx.get("vn_index", {})
    hnx       = idx.get("hnx_index", {})

    morning_df = df[df["timestamp"].dt.hour < 12] if (not df.empty and "timestamp" in df.columns) else df

    wl_perf = []
    for ticker in tickers:
        sub = morning_df[morning_df["ticker"] == ticker] if not morning_df.empty else morning_df
        if sub.empty:
            wl_perf.append({"ticker": ticker, "change_pct": None, "morning_vol": None, "alerts_am": 0})
            continue
        last_row    = sub.iloc[-1]
        morning_vol = int(sub["volume"].max()) if "volume" in sub.columns else 0
        alerts_am   = sum(1 for a in alerts if a.get("ticker") == ticker)
        wl_perf.append({
            "ticker":      ticker,
            "price":       float(last_row.get("price", 0)),
            "change_pct":  float(last_row.get("change_pct", 0)),
            "morning_vol": morning_vol,
            "alerts_am":   alerts_am,
        })

    wl_perf.sort(key=lambda x: (x["change_pct"] or 0), reverse=True)
    chg = vn.get("change_pct", 0)
    vol = vn.get("volume_bil", 0)
    direction = "tăng điểm" if chg >= 0 else "giảm điểm"

    commentary = f"Phiên sáng VN-Index {direction} {chg:+.2f}%, thanh khoản {vol:,.0f} tỷ VNĐ."
    if wl_perf:
        best = wl_perf[0]
        if best.get("change_pct") and best["change_pct"] > 0:
            commentary += f" {best['ticker']} dẫn đầu watchlist với {best['change_pct']:+.2f}%."

    summary = {
        "period": "09:00–11:30", "timestamp": datetime.now().isoformat(),
        "vn_index": vn, "hnx_index": hnx,
        "watchlist": wl_perf, "commentary": commentary,
    }

    save_cache("morning_session", summary, date_str)

    sep = "─" * 52
    print(f"\n{sep}\n  TÓM TẮT PHIÊN SÁNG — 9h00–11h30\n{sep}")
    print(f"  VN-Index  {vn.get('value','N/A')!s:>8}  ({chg:+.2f}%)")
    for p in wl_perf:
        c = p.get("change_pct")
        print(f"    {p['ticker']:6s} {f'{c:+.2f}%' if c is not None else 'N/A':>8}")
    print(f"\n  {commentary}\n{sep}\n")
    return summary
