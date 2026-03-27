"""
skills/midday_analysis/scripts/technical_deep.py
Bước 2 ca trưa: Phân tích kỹ thuật sâu tối đa 3 mã ưu tiên.
"""

import json
import sys
from datetime import datetime
from pathlib  import Path
sys.path.insert(0, str(Path(__file__).parents[4]))
from utils.api_client  import fetch_cafef_quote, fetch_yahoo_history
from utils.data_loader import load_watchlist, load_alerts, load_customers, output_dir, today
from utils.technical   import compute_all, one_liner
from utils.logger      import get_logger

log = get_logger(__name__)


def run() -> list[dict]:
    log.info("Phân tích kỹ thuật sâu...")
    date_str = today()
    tickers  = _select_tickers(date_str)
    results  = []

    for ticker in tickers[:3]:
        log.info(f"  Phân tích sâu: {ticker}")
        quote = fetch_cafef_quote(ticker) or {}
        price = quote.get("price", 0)
        vol   = quote.get("volume", 0)
        df    = fetch_yahoo_history(f"{ticker}.VN", period="6mo") or fetch_yahoo_history(ticker, period="6mo")
        r     = compute_all(df, ticker, current_price=price, vol_today=vol)

        report = {
            "ticker":    ticker,
            "timestamp": datetime.now().isoformat(),
            "price":     r.current_price,
            "change_pct": r.change_pct,
            "rsi14":     r.rsi14,
            "ma20":      r.ma20,
            "ma50":      r.ma50,
            "bb_upper":  r.bb_upper,
            "bb_lower":  r.bb_lower,
            "support1":  r.support1,
            "resistance1": r.resistance1,
            "trend_short":  r.trend_short,
            "trend_medium": r.trend_medium,
            "one_liner": one_liner(r),
        }

        # Lưu markdown
        out = output_dir(date_str) / f"deep_analysis_{ticker}_{date_str}.md"
        out.write_text(
            f"# Phân tích sâu: {ticker}\n*{datetime.now().strftime('%H:%M %d/%m/%Y')}*\n\n"
            f"**Giá:** {r.current_price:,.1f}  **Thay đổi:** {r.change_pct:+.2f}%\n\n"
            f"- RSI(14): {r.rsi14}\n- MA20: {r.ma20}\n- MA50: {r.ma50}\n"
            f"- Kháng cự: {r.resistance1}\n- Hỗ trợ: {r.support1}\n\n"
            f"**Nhận định:** {report['one_liner']}\n\n"
            "> ⚠ Chỉ mang tính tham khảo, không phải khuyến nghị đầu tư.",
            encoding="utf-8"
        )
        log.info(f"    → {out.name}")
        results.append(report)

    return results


def _select_tickers(date_str: str) -> list[str]:
    selected = []
    for c in load_customers(vip_only=True):
        for h in c.get("holdings", []):
            t = h.get("ticker", "")
            if t and t not in selected:
                selected.append(t)
    for a in load_alerts(date_str):
        if a.get("level") == "critical" and a.get("ticker") not in selected:
            selected.append(a["ticker"])
    for t in load_watchlist().get("tickers", []):
        if t not in selected:
            selected.append(t)
    return selected
