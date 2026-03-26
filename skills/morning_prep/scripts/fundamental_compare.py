"""
skills/morning-prep/scripts/fundamental_compare.py
Bước 4 ca sáng (7h30–8h30): So sánh 8 chỉ số cơ bản giữa 2 mã cùng ngành.
Output: data/cache/fundamental_{date}.json
"""

import sys
from datetime import datetime
from pathlib import Path

import yfinance as yf

sys.path.insert(0, str(Path(__file__).parents[3]))
from utils.logger import api_call, section, Timer, log_output
from utils.api_helpers import with_retry, cache_write, load_watchlist

# ── Fetch từng mã ─────────────────────────────────────────────────────────────

@api_call("YahooFinance", "ticker_info")
def _fetch_one(ticker: str) -> dict:
    """Lấy 8 chỉ số cơ bản từ Yahoo Finance."""
    # Chuyển ticker VN sang suffix .VN cho Yahoo Finance
    sym  = f"{ticker}.VN" if "." not in ticker else ticker
    info = yf.Ticker(sym).info

    # Lấy khối lượng TB 20 phiên từ lịch sử
    hist    = yf.Ticker(sym).history(period="30d")
    vol_avg = int(hist["Volume"].tail(20).mean()) if len(hist) >= 20 else None
    price   = info.get("currentPrice") or info.get("regularMarketPrice")
    prev    = info.get("regularMarketPreviousClose")
    change  = ((price - prev) / prev * 100) if price and prev else None

    return {
        "ticker":        ticker,
        "price":         price,
        "change_pct":    round(change, 2) if change is not None else None,
        "pe":            info.get("trailingPE"),
        "pb":            info.get("priceToBook"),
        "roe":           round(info.get("returnOnEquity", 0) * 100, 2) if info.get("returnOnEquity") else None,
        "roa":           round(info.get("returnOnAssets", 0) * 100, 2) if info.get("returnOnAssets") else None,
        "eps_ttm":       info.get("trailingEps"),
        "revenue_growth": round(info.get("revenueGrowth", 0) * 100, 2) if info.get("revenueGrowth") else None,
        "debt_to_equity": round(info.get("debtToEquity", 0) / 100, 2) if info.get("debtToEquity") else None,
        "vol_avg_20d":   vol_avg,
        "market_cap_bil": round(info.get("marketCap", 0) / 1e9, 1) if info.get("marketCap") else None,
        "company_name":  info.get("longName", ticker),
    }


# ── So sánh + nhận định ───────────────────────────────────────────────────────

METRICS = [
    ("pe",            "P/E (lần)",           "{:.1f}x"),
    ("pb",            "P/B (lần)",           "{:.1f}x"),
    ("roe",           "ROE (%)",             "{:.1f}%"),
    ("roa",           "ROA (%)",             "{:.1f}%"),
    ("eps_ttm",       "EPS TTM (đ)",         "{:,.0f}"),
    ("revenue_growth","Tăng trưởng DT (%)",  "{:.1f}%"),
    ("debt_to_equity","Nợ/Vốn chủ (lần)",   "{:.2f}x"),
    ("vol_avg_20d",   "KL TB 20 phiên (K)",  "{:,.0f}K"),
]

def _narrative(a: dict, b: dict, sector: str) -> str:
    """Nhận định 3–5 câu thuần định lượng, không khuyến nghị."""
    lines = []

    # P/E
    if a.get("pe") and b.get("pe"):
        cheaper = a["ticker"] if a["pe"] < b["pe"] else b["ticker"]
        diff    = abs(a["pe"] - b["pe"]) / max(a["pe"], b["pe"]) * 100
        lines.append(
            f"Về định giá, {cheaper} giao dịch P/E thấp hơn "
            f"{abs(a['pe'] - b['pe']):.1f} lần ({diff:.0f}%) so với đối thủ cùng ngành {sector}."
        )

    # ROE
    if a.get("roe") and b.get("roe"):
        better = a["ticker"] if a["roe"] > b["roe"] else b["ticker"]
        lines.append(
            f"Về hiệu quả vốn, {better} có ROE cao hơn "
            f"({max(a['roe'], b['roe']):.1f}% vs {min(a['roe'], b['roe']):.1f}%)."
        )

    # Tăng trưởng doanh thu
    ag, bg = a.get("revenue_growth"), b.get("revenue_growth")
    if ag is not None and bg is not None:
        faster = a["ticker"] if ag > bg else b["ticker"]
        lines.append(f"Tăng trưởng doanh thu: {faster} dẫn đầu ({max(ag,bg):.1f}% YoY).")

    if not lines:
        lines.append("Chưa đủ dữ liệu để so sánh định lượng.")

    return " ".join(lines)


# ── In terminal ───────────────────────────────────────────────────────────────

def _print(a: dict, b: dict, sector: str):
    section(f"PHÂN TÍCH CƠ BẢN: {a['ticker']} vs {b['ticker']} ({sector})")
    w = 22
    print(f"  {'Chỉ số':<{w}} {a['ticker']:>10}  {b['ticker']:>10}")
    print(f"  {'─'*w} {'─'*10}  {'─'*10}")

    for field, label, fmt in METRICS:
        av = a.get(field)
        bv = b.get(field)
        try:
            as_ = fmt.format(av) if av is not None else "N/A"
            bs_ = fmt.format(bv) if bv is not None else "N/A"
        except Exception:
            as_, bs_ = str(av or "N/A"), str(bv or "N/A")
        print(f"  {label:<{w}} {as_:>10}  {bs_:>10}")


# ── Main ─────────────────────────────────────────────────────────────────────

def run(pair: list[str] = None, sector: str = None) -> dict:
    wl     = load_watchlist()
    pair   = pair or wl.get("daily_compare_pair", ["VCB", "BID"])
    sector = sector or wl.get("sector", "N/A")
    ta, tb = pair[0].upper(), pair[1].upper()

    section(f"Bước 4 — Phân tích cơ bản {ta} vs {tb}")

    with Timer(f"Fetch {ta}"):
        a = with_retry(lambda: _fetch_one(ta), retries=3, wait_sec=10,
                       fallback={"ticker": ta}, label=ta)

    with Timer(f"Fetch {tb}"):
        b = with_retry(lambda: _fetch_one(tb), retries=3, wait_sec=10,
                       fallback={"ticker": tb}, label=tb)

    _print(a, b, sector)

    data = {
        "fetched_at": datetime.now().isoformat(),
        "sector":     sector,
        "pair":       [ta, tb],
        "data":       {ta: a, tb: b},
        "narrative":  _narrative(a, b, sector),
    }
    print(f"\n  📝 {data['narrative']}")

    path = cache_write("fundamental", data)
    log_output(str(path), path.stat().st_size / 1024)
    return data


if __name__ == "__main__":
    run()
