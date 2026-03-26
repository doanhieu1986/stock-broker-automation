"""
skills/eod-report/scripts/collect_eod_data.py
Bước 1 ca tổng kết (15h00–15h30): Thu thập dữ liệu đóng cửa chính thức.
Output: data/cache/eod_market_{date}.json
"""

import sys
import json
from datetime import datetime, date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parents[3]))
from utils.logger import api_call, section, Timer, log_output
from utils.api_helpers import (
    with_retry, cache_write, load_watchlist, load_customers, fmt_pct,
)

MIN_LIQUIDITY_BIL = 1.0


@api_call("CafeF", "indices_eod")
def _fetch_indices() -> dict:
    indices = {}
    for key, sym in [("vn_index","VNINDEX"), ("hnx_index","HNX"), ("vn30","VN30")]:
        r = requests.get(
            "https://s.cafef.vn/Indices/GetDataChart",
            params={"symbol": sym, "resolution": "D"},
            timeout=10, headers={"Referer": "https://cafef.vn/"},
        )
        r.raise_for_status()
        d    = r.json().get("Data", [])
        last = d[-1] if d else {}
        prev = d[-2] if len(d) >= 2 else {}
        cl, pr = last.get("Close"), prev.get("Close")
        indices[key] = {
            "symbol": sym, "close": cl,
            "change_pt":  round(cl - pr, 2) if cl and pr else None,
            "change_pct": round((cl - pr) / pr * 100, 2) if cl and pr else None,
            "volume_bil": round(last.get("Volume", 0) / 1e9, 2),
        }
    return indices


@api_call("CafeF", "top_movers")
def _fetch_top_movers() -> dict:
    r = requests.get(
        "https://s.cafef.vn/screener/stock/get-stock-list",
        params={"floorId": "10", "pageSize": "50", "orderby": "PerChange", "orderType": "desc"},
        timeout=10, headers={"Referer": "https://cafef.vn/"},
    )
    r.raise_for_status()
    items = r.json().get("Data", {}).get("StockInformationList", [])
    filtered = [
        {"ticker": i["Symbol"], "close": i.get("ClosePrice"),
         "change_pct": i.get("PerChange"), "value_bil": round((i.get("TotalValue") or 0) / 1e9, 2)}
        for i in items if (i.get("TotalValue") or 0) >= MIN_LIQUIDITY_BIL * 1e9
    ]
    return {
        "gainers": sorted(filtered, key=lambda x: x.get("change_pct") or -999, reverse=True)[:5],
        "losers":  sorted(filtered, key=lambda x: x.get("change_pct") or  999)[:5],
    }


@api_call("CafeF", "foreign_trading")
def _fetch_foreign() -> dict:
    # Placeholder — parser thực tuỳ cấu trúc trang CafeF
    r = requests.get("https://s.cafef.vn/Bao-cao-phan-tich/Giao-dich-khoi-ngoai.chn", timeout=10)
    r.raise_for_status()
    # TODO: parse HTML thực tế với BeautifulSoup
    return {"buy_bil": None, "sell_bil": None, "net_bil": None,
            "note": "Cần implement parser HTML"}


def _calc_pnl(customers: list[dict], eod_prices: dict) -> list[dict]:
    out = []
    for c in customers:
        holdings_out, day_pnl, total_val = [], 0, 0
        for h in c.get("holdings", []):
            tk   = h["ticker"]
            sh   = h.get("shares", 0)
            cost = h.get("cost_price", 0)
            curr = eod_prices.get(tk, {}).get("close") or cost
            prev = eod_prices.get(tk, {}).get("prev_close") or curr
            pd   = (curr - prev) * sh
            pt   = (curr - cost) * sh
            day_pnl   += pd
            total_val += curr * sh
            holdings_out.append({
                "ticker": tk, "shares": sh, "cost": cost, "close": curr,
                "change_pct":    round((curr - prev) / prev * 100, 2) if prev else None,
                "pnl_today":     round(pd, 0),
                "pnl_total":     round(pt, 0),
                "pnl_total_pct": round((curr - cost) / cost * 100, 2) if cost else None,
            })
        base = total_val - day_pnl
        out.append({
            "id": c.get("id"), "name": c.get("name"), "is_vip": c.get("vip", False),
            "total_value": round(total_val, 0),
            "pnl_today": round(day_pnl, 0),
            "pnl_today_pct": round(day_pnl / base * 100, 2) if base > 0 else None,
            "holdings": holdings_out,
        })
    return out


def _print(d: dict):
    section("ĐÓNG CỬA PHIÊN")
    for k, v in d.get("indices", {}).items():
        chg = fmt_pct(v["change_pct"]) if v.get("change_pct") else "N/A"
        print(f"  {k.upper():<12} {str(v.get('close','N/A')):>8}  ({chg})")
    top = d.get("top_movers", {})
    if top.get("gainers"):
        print(f"\n  TOP TĂNG: " + "  ".join(
            f"{g['ticker']} {fmt_pct(g['change_pct'])}" for g in top["gainers"][:3]))
    if top.get("losers"):
        print(f"  TOP GIẢM: " + "  ".join(
            f"{l['ticker']} {fmt_pct(l['change_pct'])}" for l in top["losers"][:3]))


def run() -> dict:
    section("Bước 1 — Thu thập dữ liệu đóng cửa")

    indices = with_retry(_fetch_indices, 3, 10, fallback={}, label="Indices")
    movers  = with_retry(_fetch_top_movers, 3, 10,
                         fallback={"gainers": [], "losers": []}, label="Top movers")
    foreign = with_retry(_fetch_foreign, 3, 10, fallback={}, label="Foreign")

    customers = load_customers()
    # eod_prices: lấy thực tế từ API cho toàn bộ mã KH đang giữ
    eod_prices = {}
    customer_pnl = _calc_pnl(customers, eod_prices)

    data = {
        "date": date.today().strftime("%Y%m%d"),
        "fetched_at": datetime.now().isoformat(),
        "indices": indices, "top_movers": movers,
        "foreign": foreign, "customers": customer_pnl,
    }
    path = cache_write("eod_market", data)
    log_output(str(path), path.stat().st_size / 1024)
    _print(data)
    return data


if __name__ == "__main__":
    run()
