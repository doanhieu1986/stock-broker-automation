"""
utils/api_client.py
HTTP client tập trung: retry, timeout, fallback.
Mọi script đều import từ đây thay vì gọi requests trực tiếp.
"""

import time, os
from datetime import datetime
from typing import Any
import requests
from dotenv import load_dotenv
from utils.logger import get_logger, log_api_call

load_dotenv()
log = get_logger(__name__)

DEFAULT_TIMEOUT = 10
MAX_RETRIES     = 3
RETRY_WAIT      = 5

CAFEF_API_KEY    = os.getenv("CAFEF_API_KEY", "")
EXCHANGE_API_KEY = os.getenv("EXCHANGE_RATE_API_KEY", "")
CAFEF_BASE       = "https://s.cafef.vn/Ajax"


def _get(url: str, params: dict | None = None, source: str = "HTTP") -> dict | None:
    for attempt in range(1, MAX_RETRIES + 1):
        t0 = time.time()
        try:
            resp = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT)
            elapsed = int((time.time() - t0) * 1000)
            resp.raise_for_status()
            log_api_call(log, source, url[:60], "OK", elapsed)
            return resp.json()
        except requests.exceptions.Timeout:
            log_api_call(log, source, url[:60], "TIMEOUT", int((time.time()-t0)*1000))
        except requests.exceptions.HTTPError as e:
            log_api_call(log, source, url[:60], f"HTTP{e.response.status_code}", int((time.time()-t0)*1000))
        except Exception as e:
            log_api_call(log, source, url[:60], "ERROR", int((time.time()-t0)*1000))
            log.debug(f"  {e}")
        if attempt < MAX_RETRIES:
            log.warning(f"  Retry {attempt+1}/{MAX_RETRIES} sau {RETRY_WAIT}s...")
            time.sleep(RETRY_WAIT)
    log.error(f"  [{source}] Thất bại sau {MAX_RETRIES} lần: {url[:60]}")
    return None


def fetch_yahoo_quote(ticker: str) -> dict | None:
    import yfinance as yf
    try:
        t0   = time.time()
        info = yf.Ticker(ticker).fast_info
        elapsed = int((time.time()-t0)*1000)
        price = float(info.last_price or 0)
        prev  = float(info.previous_close or price)
        chg   = price - prev
        chg_p = (chg / prev * 100) if prev else 0.0
        log_api_call(log, "Yahoo", ticker, "OK", elapsed)
        return {"symbol": ticker, "price": round(price,2),
                "change": round(chg,2), "change_pct": round(chg_p,2),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    except Exception as e:
        log_api_call(log, "Yahoo", ticker, "ERROR", 0)
        log.debug(f"  {e}")
        return None


def fetch_yahoo_history(ticker: str, period: str = "3mo"):
    import yfinance as yf
    try:
        df = yf.Ticker(ticker).history(period=period)
        return df if not df.empty else None
    except Exception as e:
        log.debug(f"yf history {ticker}: {e}")
        return None


def fetch_cafef_quote(ticker: str) -> dict | None:
    data = _get(f"{CAFEF_BASE}/GiaCK.ashx",
                params={"Symbol": ticker, "Type": "json"}, source="CafeF")
    if not data:
        return None
    try:
        item = data if isinstance(data, dict) else data[0]
        return {
            "ticker":     ticker,
            "price":      float(item.get("GiaDongCua", 0)) / 1000,
            "change_pct": float(item.get("ThayDoiPhanTram", 0)),
            "volume":     int(item.get("KhoiLuongKhopLenh", 0)),
            "reference":  float(item.get("GiaThamChieu", 0)) / 1000,
            "ceiling":    float(item.get("GiaTran", 0)) / 1000,
            "floor":      float(item.get("GiaSan", 0)) / 1000,
        }
    except Exception as e:
        log.debug(f"CafeF parse {ticker}: {e}")
        return None


def fetch_cafef_index() -> dict | None:
    data = _get(f"{CAFEF_BASE}/ChiSo.ashx", source="CafeF/Index")
    if not data:
        return None
    key_map = {"VNINDEX":"vn_index","HNX-INDEX":"hnx_index",
               "VN30":"vn30","UPCOM":"upcom_index"}
    result = {}
    try:
        for item in data:
            sym = item.get("IndexID","")
            if sym in key_map:
                result[key_map[sym]] = {
                    "value":      round(float(item.get("IndexValue",0)),2),
                    "change_pt":  round(float(item.get("Change",0)),2),
                    "change_pct": round(float(item.get("PercentChange",0)),2),
                    "volume_bil": round(float(item.get("TotalDeal",0))/1e9,1),
                }
        return result or None
    except Exception as e:
        log.debug(f"CafeF index parse: {e}")
        return None


def fetch_cafef_top_movers(exchange: str = "HOSE", top: int = 5) -> dict | None:
    data = _get(f"{CAFEF_BASE}/TopGainersLosers.ashx",
                params={"exchange": exchange, "top": top},
                source="CafeF/TopMovers")
    if not data:
        return None
    def parse(items):
        return [{"ticker": i.get("Symbol",""),
                 "price":  round(float(i.get("Price",0))/1000,1),
                 "change_pct": round(float(i.get("PercentChange",0)),2),
                 "volume_bil": round(float(i.get("TotalDeal",0))/1e9,2)}
                for i in items]
    try:
        return {"gainers": parse(data.get("Gainers",[])[:top]),
                "losers":  parse(data.get("Losers", [])[:top])}
    except Exception as e:
        log.debug(f"Top movers parse: {e}")
        return None


def fetch_cafef_foreign_flow() -> dict | None:
    data = _get(f"{CAFEF_BASE}/KhoiNgoai.ashx", source="CafeF/Foreign")
    if not data:
        return None
    try:
        return {"buy_bil":  round(float(data.get("MuaRong",0))/1e9,1),
                "sell_bil": round(float(data.get("BanRong",0))/1e9,1),
                "net_bil":  round(float(data.get("GiaTriMuaRong",0))/1e9,1)}
    except Exception as e:
        log.debug(f"Foreign flow parse: {e}")
        return None


def fetch_usd_vnd() -> float | None:
    url  = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_API_KEY}/pair/USD/VND"
    data = _get(url, source="ExchangeRate")
    if data:
        try:
            return float(data.get("conversion_rate",0))
        except Exception:
            pass
    # Fallback Vietcombank
    try:
        import xml.etree.ElementTree as ET
        resp = requests.get(
            "https://portal.vietcombank.com.vn/Usercontrols/TVPortal.TyGia/pXML.aspx?b=10",
            timeout=8)
        root = ET.fromstring(resp.text)
        for ex in root.findall(".//Exrate"):
            if ex.get("CurrencyCode") == "USD":
                sell = ex.get("Sell","").replace(",","")
                return float(sell) if sell else None
    except Exception as e:
        log.debug(f"VCB rate fallback: {e}")
    return None


def fetch_rss(url: str, max_items: int = 20) -> list[dict]:
    try:
        import feedparser
        t0   = time.time()
        feed = feedparser.parse(url)
        log_api_call(log, "RSS", url[:60], "OK", int((time.time()-t0)*1000))
        return [{"title":     e.get("title",""),
                 "link":      e.get("link",""),
                 "published": e.get("published",""),
                 "summary":   e.get("summary","")[:500]}
                for e in feed.entries[:max_items]]
    except Exception as e:
        log.warning(f"RSS error ({url[:40]}): {e}")
        return []
