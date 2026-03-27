"""
skills/trading-hours/scripts/technical_quick.py
Chế độ 2: Phân tích kỹ thuật on-demand — trả kết quả < 30 giây.
Output: outputs/{date}/analysis_{TICKER}_{HHMM}.json
"""

import sys
import json
import numpy as np
from datetime import datetime, date
from pathlib import Path

import yfinance as yf
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[4]))
from utils.logger import api_call, section, log_output
from utils.api_helpers import with_retry, cache_read, output_dir, fmt_pct, fmt_price

LOOKBACK = 60   # số phiên để tính kỹ thuật
DISCLAIMER = "⚠ Thông tin chỉ mang tính tham khảo, không phải khuyến nghị đầu tư."


# ── Tính chỉ báo kỹ thuật ────────────────────────────────────────────────────

def _sma(series: pd.Series, n: int) -> float | None:
    if len(series) < n:
        return None
    return round(float(series.tail(n).mean()), 2)


def _rsi(series: pd.Series, n: int = 14) -> float | None:
    if len(series) < n + 1:
        return None
    delta = series.diff().dropna()
    gain  = delta.where(delta > 0, 0.0).rolling(n).mean()
    loss  = (-delta.where(delta < 0, 0.0)).rolling(n).mean()
    rs    = gain / loss
    rsi   = 100 - (100 / (1 + rs))
    val   = rsi.iloc[-1]
    return round(float(val), 1) if not np.isnan(val) else None


def _macd(series: pd.Series) -> dict:
    if len(series) < 26:
        return {"macd": None, "signal": None, "hist": None}
    ema12  = series.ewm(span=12).mean()
    ema26  = series.ewm(span=26).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    return {
        "macd":   round(float(macd.iloc[-1]), 2),
        "signal": round(float(signal.iloc[-1]), 2),
        "hist":   round(float((macd - signal).iloc[-1]), 2),
    }


def _bollinger(series: pd.Series, n: int = 20, k: float = 2.0) -> dict:
    if len(series) < n:
        return {"upper": None, "lower": None, "mid": None}
    mid   = series.rolling(n).mean()
    std   = series.rolling(n).std()
    return {
        "upper": round(float((mid + k * std).iloc[-1]), 2),
        "mid":   round(float(mid.iloc[-1]), 2),
        "lower": round(float((mid - k * std).iloc[-1]), 2),
    }


def _stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k: int = 14) -> dict:
    if len(close) < k:
        return {"k": None, "d": None}
    lowest  = low.rolling(k).min()
    highest = high.rolling(k).max()
    pct_k   = 100 * (close - lowest) / (highest - lowest)
    pct_d   = pct_k.rolling(3).mean()
    return {
        "k": round(float(pct_k.iloc[-1]), 1),
        "d": round(float(pct_d.iloc[-1]), 1),
    }


def _support_resistance(close: pd.Series, lookback: int = 20) -> dict:
    """Hỗ trợ/kháng cự đơn giản từ min/max trong N phiên."""
    recent = close.tail(lookback)
    return {
        "support":    round(float(recent.min()), 2),
        "resistance": round(float(recent.max()), 2),
    }


# ── Fetch và phân tích ────────────────────────────────────────────────────────

@api_call("YahooFinance", "ticker_history")
def _fetch(ticker: str) -> pd.DataFrame:
    sym  = f"{ticker}.VN" if "." not in ticker else ticker
    hist = yf.download(sym, period=f"{LOOKBACK + 10}d", auto_adjust=True, progress=False)
    if hist.empty:
        raise ValueError(f"Không có dữ liệu cho {ticker}")
    return hist


def analyze(ticker: str) -> dict:
    ticker = ticker.upper()

    hist = with_retry(
        lambda: _fetch(ticker),
        retries=3, wait_sec=10,
        fallback=None, label=ticker,
    )

    if hist is None or len(hist) < 5:
        return {"ticker": ticker, "error": "Không đủ dữ liệu", "timestamp": datetime.now().isoformat()}

    close  = hist["Close"].squeeze()
    high   = hist["High"].squeeze()
    low    = hist["Low"].squeeze()
    volume = hist["Volume"].squeeze()

    price     = round(float(close.iloc[-1]), 2)
    prev      = round(float(close.iloc[-2]), 2)
    change    = round((price - prev) / prev * 100, 2)

    # Thay đổi 3 phiên
    chg_3d = round((price - float(close.iloc[-4])) / float(close.iloc[-4]) * 100, 2) if len(close) >= 4 else None

    # Khối lượng
    vol_today = int(volume.iloc[-1])
    vol_avg   = int(volume.tail(20).mean())
    vol_ratio = round(vol_today / vol_avg, 1) if vol_avg else None

    # Chỉ báo kỹ thuật
    ma20 = _sma(close, 20)
    ma50 = _sma(close, 50)
    rsi  = _rsi(close, 14)
    macd = _macd(close)
    bb   = _bollinger(close, 20)
    sto  = _stochastic(high, low, close, 14)
    sr   = _support_resistance(close, 20)

    # Cơ bản từ cache sáng
    fund = cache_read("fundamental")
    fund_data = {}
    if fund and fund.get("data") and ticker in fund["data"]:
        d = fund["data"][ticker]
        fund_data = {"pe": d.get("pe"), "pb": d.get("pb"), "roe": d.get("roe")}

    # Nhận định 1 câu
    narrative = _one_line(price, ma20, ma50, rsi, bb, vol_ratio)

    result = {
        "ticker":      ticker,
        "timestamp":   datetime.now().strftime("%H:%M %d/%m/%Y"),
        "price":       price,
        "change_pct":  change,
        "change_3d":   chg_3d,
        "volume_today": vol_today,
        "vol_ratio":   vol_ratio,
        "technical": {
            "ma20": ma20, "ma50": ma50,
            "rsi14": rsi,
            "macd":  macd,
            "bollinger": bb,
            "stochastic": sto,
        },
        "support":    sr["support"],
        "resistance": sr["resistance"],
        "fundamental": fund_data,
        "narrative":  narrative,
    }

    # Lưu JSON
    ds   = date.today().strftime("%Y%m%d")
    hhmm = datetime.now().strftime("%H%M")
    path = output_dir(ds) / f"analysis_{ticker}_{hhmm}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log_output(str(path), path.stat().st_size / 1024)

    return result


# ── Nhận định 1 câu ───────────────────────────────────────────────────────────

def _one_line(price, ma20, ma50, rsi, bb, vol_ratio) -> str:
    parts = []

    if rsi is not None:
        if rsi > 70:
            parts.append(f"RSI {rsi} — vùng quá mua")
        elif rsi < 30:
            parts.append(f"RSI {rsi} — vùng quá bán")
        else:
            parts.append(f"RSI {rsi} trung tính")

    if ma20 and ma50:
        if price > ma20 > ma50:
            parts.append("giá trên cả MA20 và MA50")
        elif price < ma20 < ma50:
            parts.append("giá dưới cả MA20 và MA50")
        elif price > ma20 and price < ma50:
            parts.append("giá trên MA20, dưới MA50")

    if bb.get("upper") and bb.get("lower"):
        if price >= bb["upper"]:
            parts.append("chạm dải Bollinger trên")
        elif price <= bb["lower"]:
            parts.append("chạm dải Bollinger dưới")

    if vol_ratio:
        parts.append(f"khối lượng x{vol_ratio:.1f} TB")

    return (", ".join(parts) + ".") if parts else "Chưa đủ dữ liệu để nhận định."


# ── In terminal ───────────────────────────────────────────────────────────────

def print_result(r: dict):
    if r.get("error"):
        print(f"\n  ✗ {r['ticker']}: {r['error']}")
        return

    t   = r["technical"]
    sr  = r
    sep = "═" * 50
    chg = fmt_pct(r["change_pct"])
    chg3 = fmt_pct(r["change_3d"]) if r.get("change_3d") else "—"

    print(f"\n{sep}")
    print(f"  PHÂN TÍCH NHANH: {r['ticker']}  |  {r['timestamp']}")
    print(sep)
    print(f"  GIÁ HIỆN TẠI   {fmt_price(r['price']):>10}  ({chg} hôm nay)")
    print(f"  3 phiên gần    {chg3:>10}  KL: {r['volume_today']:,} (x{r.get('vol_ratio','—')} TB)")
    print(f"\n  KỸ THUẬT")
    if t.get("rsi14") is not None:
        print(f"  ├ RSI(14)    {t['rsi14']:>7.1f}")
    if t.get("ma20"):
        above = "✓" if r["price"] > t["ma20"] else "✗"
        print(f"  ├ MA20       {fmt_price(t['ma20']):>10}  [{above} giá {'trên' if above=='✓' else 'dưới'} MA20]")
    if t.get("ma50"):
        above = "✓" if r["price"] > t["ma50"] else "✗"
        print(f"  ├ MA50       {fmt_price(t['ma50']):>10}  [{above}]")
    bb = t.get("bollinger", {})
    if bb.get("upper"):
        print(f"  └ Bollinger  {fmt_price(bb['lower'])}–{fmt_price(bb['upper'])}")
    print(f"\n  VÙNG GIÁ QUAN TRỌNG (20 phiên)")
    dist_r = (sr["resistance"] - r["price"]) / r["price"] * 100
    dist_s = (r["price"] - sr["support"]) / r["price"] * 100
    print(f"  ├ Kháng cự  {fmt_price(sr['resistance']):>10}  (+{dist_r:.1f}% từ hiện tại)")
    print(f"  └ Hỗ trợ    {fmt_price(sr['support']):>10}  (-{dist_s:.1f}% từ hiện tại)")
    if r.get("fundamental"):
        f = r["fundamental"]
        print(f"\n  CƠ BẢN   P/E {f.get('pe','N/A')}x  P/B {f.get('pb','N/A')}x  ROE {f.get('roe','N/A')}%")
    print(f"\n  → {r['narrative']}")
    print(f"\n  {DISCLAIMER}")
    print(sep + "\n")


# ── Main ─────────────────────────────────────────────────────────────────────

def run(ticker: str = None):
    if not ticker:
        ticker = input("Nhập mã cổ phiếu cần phân tích: ").strip().upper()
    if not ticker:
        print("⚠ Cần nhập mã cổ phiếu.")
        return

    section(f"Phân tích on-demand: {ticker}")
    result = analyze(ticker)
    print_result(result)
    return result


if __name__ == "__main__":
    import sys
    ticker_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run(ticker_arg)
