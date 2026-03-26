"""
skills/morning-prep/scripts/fetch_global_markets.py
Bước 1 ca sáng (6h00–6h30): Thu thập thị trường quốc tế.
Output: data/cache/global_{date}.json
"""

import sys
from datetime import datetime, date
from pathlib import Path

import yfinance as yf

sys.path.insert(0, str(Path(__file__).parents[3]))
from utils.logger import api_call, section, Timer, log_output
from utils.api_helpers import (
    with_retry, cache_write, cache_read_yesterday,
    get_json, fmt_pct,
)

# ── Cấu hình tickers ─────────────────────────────────────────────────────────

INDICES = {
    "dow":    ("^DJI",  "Dow Jones"),
    "sp500":  ("^GSPC", "S&P 500"),
    "nasdaq": ("^IXIC", "Nasdaq"),
    "vix":    ("^VIX",  "VIX"),
}
COMMODITIES = {
    "oil":  ("BZ=F", "Dầu Brent"),
    "gold": ("GC=F", "Vàng"),
}
FX_URL = "https://api.exchangerate-api.com/v4/latest/USD"

# ── Fetch ─────────────────────────────────────────────────────────────────────

@api_call("YahooFinance", "batch_tickers")
def _yahoo_batch(symbols: list[str]) -> dict:
    """Lấy giá + % thay đổi so với phiên trước."""
    result = {}
    data = yf.download(symbols, period="2d", auto_adjust=True, progress=False)
    closes = data["Close"]
    for sym in symbols:
        if sym in closes.columns and len(closes[sym].dropna()) >= 2:
            prev = float(closes[sym].dropna().iloc[-2])
            curr = float(closes[sym].dropna().iloc[-1])
            chg  = (curr - prev) / prev * 100
            result[sym] = {"price": round(curr, 2), "change_pct": round(chg, 2)}
        else:
            result[sym] = {"price": None, "change_pct": None}
    return result


@api_call("ExchangeRate-API", "USD→VND")
def _fetch_usdvnd() -> float | None:
    data = get_json(FX_URL, timeout=8)
    return data["rates"].get("VND")


# ── Xây dựng data object ──────────────────────────────────────────────────────

def _build(raw: dict, usdvnd: float | None) -> dict:
    out = {
        "fetched_at": datetime.now().isoformat(),
        "indices": {},
        "commodities": {},
        "fx": {},
    }
    for key, (sym, label) in INDICES.items():
        info = raw.get(sym, {})
        out["indices"][key] = {
            "label": label, "symbol": sym,
            "price": info.get("price"),
            "change_pct": info.get("change_pct"),
        }
    for key, (sym, label) in COMMODITIES.items():
        info = raw.get(sym, {})
        out["commodities"][key] = {
            "label": label, "symbol": sym,
            "price": info.get("price"),
            "change_pct": info.get("change_pct"),
        }
    out["fx"]["usdvnd"] = {"label": "USD/VND", "rate": usdvnd}
    out["narrative"] = _narrative(out)
    return out


def _narrative(data: dict) -> str:
    dow  = data["indices"].get("dow", {})
    vix  = data["indices"].get("vix", {})
    oil  = data["commodities"].get("oil", {})
    gold = data["commodities"].get("gold", {})
    usd  = data["fx"].get("usdvnd", {}).get("rate")
    parts = []

    if dow.get("change_pct") is not None:
        d = "tăng" if dow["change_pct"] >= 0 else "giảm"
        parts.append(
            f"Thị trường Mỹ phiên qua {d}, Dow Jones {fmt_pct(dow['change_pct'])}."
        )
    if vix.get("price") is not None:
        v = vix["price"]
        mood = "lạc quan" if v < 15 else ("thận trọng" if v < 25 else "lo ngại")
        parts.append(f"VIX {v:.1f} — tâm lý {mood}.")
    items = []
    if oil.get("change_pct") is not None:
        items.append(f"dầu {fmt_pct(oil['change_pct'])}")
    if gold.get("change_pct") is not None:
        items.append(f"vàng {fmt_pct(gold['change_pct'])}")
    if usd:
        items.append(f"USD/VND {usd:,.0f}")
    if items:
        parts.append(", ".join(items) + ".")
    return " ".join(parts)


# ── In terminal ───────────────────────────────────────────────────────────────

def _print(data: dict):
    section("QUỐC TẾ")
    print(f"  {'Chỉ số':<14} {'Giá':>12}  {'Δ':>8}")
    print(f"  {'─'*14} {'─'*12}  {'─'*8}")
    for info in data["indices"].values():
        p   = f"{info['price']:,.2f}" if info["price"] else "N/A"
        chg = fmt_pct(info["change_pct"]) if info["change_pct"] is not None else "N/A"
        print(f"  {info['label']:<14} {p:>12}  {chg:>8}")
    print()
    for info in data["commodities"].values():
        p   = f"${info['price']:,.1f}" if info["price"] else "N/A"
        chg = fmt_pct(info["change_pct"]) if info["change_pct"] is not None else "N/A"
        print(f"  {info['label']:<14} {p:>12}  {chg:>8}")
    usd = data["fx"].get("usdvnd", {}).get("rate")
    if usd:
        print(f"  {'USD/VND':<14} {usd:>12,.0f}")
    print(f"\n  📝 {data.get('narrative', '')}")


# ── Main ─────────────────────────────────────────────────────────────────────

def run() -> dict:
    section("Bước 1 — Thị trường quốc tế")
    symbols = [s for s, _ in list(INDICES.values()) + list(COMMODITIES.values())]

    with Timer("Yahoo Finance"):
        raw = with_retry(
            lambda: _yahoo_batch(symbols),
            retries=3, wait_sec=30,
            fallback={s: {"price": None, "change_pct": None} for s in symbols},
            label="Yahoo Finance",
        )

    # Fallback toàn bộ → dùng cache hôm qua
    if all(v["price"] is None for v in raw.values()):
        print("  ⚠ Tất cả Yahoo lỗi — dùng cache hôm qua")
        old = cache_read_yesterday("global")
        if old:
            old["note"] = "[Dữ liệu có thể chưa cập nhật — cache hôm qua]"
            return old

    with Timer("USD/VND"):
        usdvnd = with_retry(_fetch_usdvnd, retries=3, wait_sec=10, fallback=None)

    data  = _build(raw, usdvnd)
    path  = cache_write("global", data)
    log_output(str(path), path.stat().st_size / 1024)
    _print(data)
    return data


if __name__ == "__main__":
    run()
