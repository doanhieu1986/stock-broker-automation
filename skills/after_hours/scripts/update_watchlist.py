"""
skills/after_hours/scripts/update_watchlist.py
Bước 4b: Cập nhật watchlist cho ngày mai.
"""
from utils.data_loader import load_watchlist, save_watchlist, read_json, DATA_DIR
from utils.logger      import get_logger
log = get_logger(__name__)

def run():
    log.info("Cập nhật watchlist ngày mai...")
    wl      = load_watchlist()
    changes = read_json(DATA_DIR/"watchlist_changes.json", default={})

    for t in changes.get("add", []):
        if t.upper() not in wl.get("tickers", []):
            wl.setdefault("tickers", []).append(t.upper())
            log.info(f"  + Thêm mã: {t.upper()}")

    wl["tickers"] = [t for t in wl.get("tickers", [])
                     if t not in changes.get("remove", [])]

    if changes.get("compare_pair"):
        wl["daily_compare_pair"] = [t.upper() for t in changes["compare_pair"][:2]]
        log.info(f"  Cặp so sánh ngày mai: {wl['daily_compare_pair']}")

    save_watchlist(wl, tomorrow=True)
    log.info(f"  Đã lưu: watchlist_tomorrow.json ({len(wl.get('tickers',[]))} mã)")
