"""
skills/morning-prep/scripts/fetch_asia_markets.py
Bước 2 ca sáng (6h30–7h00): Thu thập thị trường châu Á.
Output: data/cache/asia_{date}.json
"""

import sys
from datetime import datetime
from pathlib import Path

import yfinance as yf

sys.path.insert(0, str(Path(__file__).parents[4]))
from utils.logger import api_call, section, Timer, log_output
from utils.api_helpers import with_retry, cache_write, fmt_pct

# ── Thị trường châu Á theo thứ tự ảnh hưởng đến VN ──────────────────────────

MARKETS = {
    "china":  ("000001.SS", "Shanghai (CN)",   "Ảnh hưởng lớn nhất"),
    "hk":     ("^HSI",      "Hang Seng (HK)",  "Barometer FDI châu Á"),
    "japan":  ("^N225",     "Nikkei 225 (JP)", "Tâm lý khu vực"),
    "korea":  ("^KS11",     "KOSPI (KR)",      "Cùng emerging market"),
    "thai":   ("^SET.BK",   "SET (TH)",        "So sánh Đông Nam Á"),
}

ALERT_THRESHOLD = 1.5  # % — đánh dấu biến động mạnh


# ── Fetch ─────────────────────────────────────────────────────────────────────

@api_call("YahooFinance", "asia_markets")
def _fetch(symbols: list[str]) -> dict:
    data    = yf.download(symbols, period="2d", auto_adjust=True, progress=False)
    closes  = data["Close"]
    result  = {}
    for sym in symbols:
        col = closes[sym] if sym in closes.columns else None
        if col is not None and len(col.dropna()) >= 2:
            prev = float(col.dropna().iloc[-2])
            curr = float(col.dropna().iloc[-1])
            chg  = (curr - prev) / prev * 100
            result[sym] = {
                "price":      round(curr, 2),
                "change_pct": round(chg, 2),
                "is_live":    True,
            }
        else:
            # Thị trường có thể chưa mở — chỉ có 1 ngày dữ liệu
            if col is not None and len(col.dropna()) == 1:
                result[sym] = {
                    "price":      round(float(col.dropna().iloc[-1]), 2),
                    "change_pct": None,
                    "is_live":    False,    # dữ liệu đóng cửa hôm qua
                }
            else:
                result[sym] = {"price": None, "change_pct": None, "is_live": False}
    return result


# ── Xây dựng + phân tích ─────────────────────────────────────────────────────

def _build(raw: dict) -> dict:
    out = {"fetched_at": datetime.now().isoformat(), "markets": {}, "alerts": []}

    for key, (sym, label, note) in MARKETS.items():
        info = raw.get(sym, {})
        chg  = info.get("change_pct")

        entry = {
            "label":      label,
            "symbol":     sym,
            "note":       note,
            "price":      info.get("price"),
            "change_pct": chg,
            "is_live":    info.get("is_live", False),
            "flag":       None,
        }

        # Đánh dấu biến động đáng chú ý
        if chg is not None and abs(chg) >= ALERT_THRESHOLD:
            entry["flag"] = "🟢" if chg > 0 else "🔴"
            out["alerts"].append({
                "market": label,
                "change_pct": chg,
                "direction": "tăng" if chg > 0 else "giảm",
            })

        out["markets"][key] = entry

    out["narrative"] = _narrative(out)
    return out


def _narrative(data: dict) -> str:
    """Tóm tắt 1–2 câu về diễn biến châu Á."""
    alerts = data["alerts"]
    if not alerts:
        return "Thị trường châu Á biến động trong biên độ bình thường, không có tín hiệu đột biến."

    parts = []
    for a in alerts:
        parts.append(f"{a['market']} {a['direction']} mạnh {fmt_pct(a['change_pct'])}")
    return "Đáng chú ý: " + "; ".join(parts) + "."


# ── In terminal ───────────────────────────────────────────────────────────────

def _print(data: dict):
    section("CHÂU Á")
    print(f"  {'Thị trường':<22} {'Giá':>12}  {'Δ':>8}  {'Lưu ý'}")
    print(f"  {'─'*22} {'─'*12}  {'─'*8}  {'─'*20}")
    for info in data["markets"].values():
        p    = f"{info['price']:,.2f}" if info["price"] else "N/A"
        chg  = fmt_pct(info["change_pct"]) if info["change_pct"] is not None else "—"
        flag = info.get("flag") or "  "
        note = "(đóng cửa hôm qua)" if not info["is_live"] else ""
        print(f"  {flag} {info['label']:<20} {p:>12}  {chg:>8}  {note}")
    if data["alerts"]:
        print(f"\n  📝 {data['narrative']}")


# ── Main ─────────────────────────────────────────────────────────────────────

def run() -> dict:
    section("Bước 2 — Thị trường châu Á")
    symbols = [sym for sym, _, _ in MARKETS.values()]

    with Timer("Asia markets"):
        raw = with_retry(
            lambda: _fetch(symbols),
            retries=3, wait_sec=30,
            fallback={s: {"price": None, "change_pct": None, "is_live": False} for s in symbols},
            label="Asia Yahoo",
        )

    data = _build(raw)
    path = cache_write("asia", data)
    log_output(str(path), path.stat().st_size / 1024)
    _print(data)
    return data


if __name__ == "__main__":
    run()
