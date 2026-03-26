"""
utils/technical.py
Tính chỉ báo kỹ thuật từ lịch sử giá — chỉ dùng pandas + numpy.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass


@dataclass
class TechnicalResult:
    ticker:        str
    current_price: float
    change_pct:    float
    ma20:          float | None = None
    ma50:          float | None = None
    ma200:         float | None = None
    bb_upper:      float | None = None
    bb_middle:     float | None = None
    bb_lower:      float | None = None
    rsi14:         float | None = None
    macd:          float | None = None
    macd_signal:   float | None = None
    macd_hist:     float | None = None
    stoch_k:       float | None = None
    stoch_d:       float | None = None
    vol_today:     int   | None = None
    vol_avg20:     int   | None = None
    vol_ratio:     float | None = None
    support1:      float | None = None
    resistance1:   float | None = None
    support2:      float | None = None
    trend_short:   str = ""
    trend_medium:  str = ""
    trend_long:    str = ""


def compute_all(df, ticker: str, current_price: float | None = None,
                vol_today: int = 0) -> TechnicalResult:
    if df is None or df.empty or len(df) < 5:
        return TechnicalResult(ticker=ticker, current_price=current_price or 0, change_pct=0)

    close  = df["Close"].dropna()
    high   = df["High"].dropna()
    low    = df["Low"].dropna()
    volume = df["Volume"].dropna()

    price = current_price or float(close.iloc[-1])
    prev  = float(close.iloc[-2]) if len(close) >= 2 else price
    chg   = round((price - prev) / prev * 100, 2) if prev else 0.0

    r = TechnicalResult(ticker=ticker, current_price=round(price,2), change_pct=chg)

    for n, attr in [(20,"ma20"),(50,"ma50"),(200,"ma200")]:
        if len(close) >= n:
            setattr(r, attr, round(float(close.rolling(n).mean().iloc[-1]), 2))

    if len(close) >= 20:
        ma, std    = close.rolling(20).mean(), close.rolling(20).std()
        r.bb_middle = round(float(ma.iloc[-1]),2)
        r.bb_upper  = round(float((ma+2*std).iloc[-1]),2)
        r.bb_lower  = round(float((ma-2*std).iloc[-1]),2)

    if len(close) >= 15:
        r.rsi14 = round(_rsi(close,14),1)

    if len(close) >= 35:
        ema12  = close.ewm(span=12,adjust=False).mean()
        ema26  = close.ewm(span=26,adjust=False).mean()
        macd   = ema12 - ema26
        signal = macd.ewm(span=9,adjust=False).mean()
        r.macd        = round(float(macd.iloc[-1]),3)
        r.macd_signal = round(float(signal.iloc[-1]),3)
        r.macd_hist   = round(float((macd-signal).iloc[-1]),3)

    if len(close) >= 17:
        lo14 = low.rolling(14).min()
        hi14 = high.rolling(14).max()
        k    = (100*(close-lo14)/(hi14-lo14+1e-9)).rolling(3).mean()
        d    = k.rolling(3).mean()
        r.stoch_k = round(float(k.iloc[-1]),1)
        r.stoch_d = round(float(d.iloc[-1]),1)

    if len(volume) >= 20:
        avg = float(volume.rolling(20).mean().iloc[-1])
        r.vol_avg20 = int(avg)
        vt  = vol_today or int(volume.iloc[-1])
        r.vol_today = vt
        r.vol_ratio = round(vt/avg,2) if avg else None

    if len(close) >= 20:
        highs = sorted(high.tail(20).unique(), reverse=True)
        lows  = sorted(low.tail(20).unique())
        res   = [h for h in highs if h > price*1.001]
        sup   = [l for l in lows  if l < price*0.999]
        r.resistance1 = round(res[0],2) if res else round(max(highs),2)
        r.support1    = round(sup[0],2) if len(sup)>=1 else None
        r.support2    = round(sup[1],2) if len(sup)>=2 else None

    r.trend_short  = _trend(close,5)
    r.trend_medium = _trend(close,20)
    r.trend_long   = _trend(close,60) if len(close)>=60 else "N/A"
    return r


def _rsi(series, period=14) -> float:
    delta    = series.diff()
    avg_gain = delta.clip(lower=0).ewm(com=period-1,min_periods=period).mean()
    avg_loss = (-delta).clip(lower=0).ewm(com=period-1,min_periods=period).mean()
    rs = avg_gain/(avg_loss+1e-9)
    return float(100 - 100/(1+rs.iloc[-1]))


def _trend(close, n) -> str:
    if len(close) < n: return "N/A"
    seg   = close.tail(n).reset_index(drop=True)
    slope = np.polyfit(np.arange(n), seg.values.astype(float), 1)[0]
    pct   = slope/float(seg.iloc[0])*100
    if pct > 0.15:  return "tăng"
    if pct < -0.15: return "giảm"
    return "đi ngang"


def one_liner(r: TechnicalResult) -> str:
    """1 câu nhận định thuần kỹ thuật — KHÔNG khuyến nghị mua/bán."""
    parts = []
    if r.rsi14 is not None:
        if r.rsi14 > 70:   parts.append(f"RSI {r.rsi14:.0f} vùng quá mua")
        elif r.rsi14 < 30: parts.append(f"RSI {r.rsi14:.0f} vùng quá bán")
        else:              parts.append(f"RSI {r.rsi14:.0f} trung tính")
    if r.ma20 and r.current_price:
        pos = "trên" if r.current_price > r.ma20 else "dưới"
        parts.append(f"giá {pos} MA20 ({r.ma20:,.0f})")
    if r.vol_ratio and r.vol_ratio > 1.5:
        parts.append(f"KL gấp {r.vol_ratio:.1f}x TB 20 phiên")
    return (", ".join(parts)+".").capitalize() if parts else "Không đủ dữ liệu."
