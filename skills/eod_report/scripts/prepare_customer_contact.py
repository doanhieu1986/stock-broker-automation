"""
skills/eod_report/scripts/prepare_customer_contact.py
Bước 3 ca EOD: Soạn ghi chú liên hệ cá nhân hóa cho từng KH.
"""

from datetime import datetime
from pathlib  import Path

from utils.api_client  import fetch_cafef_quote
from utils.data_loader import (
    load_customers, load_cache, load_alerts,
    output_dir, today
)
from utils.logger import get_logger

log = get_logger(__name__)


def run() -> Path:
    """Phân nhóm KH và soạn ghi chú liên hệ."""
    log.info("Soạn ghi chú liên hệ khách hàng...")
    date_str  = today()
    eod       = load_cache("eod_raw", date_str) or {}
    customers = load_customers()
    alerts    = load_alerts(date_str)

    alert_tickers = {a.get("ticker") for a in alerts if a.get("level") == "critical"}

    groups = {"A": [], "B": [], "C": []}
    notes  = []

    for c in customers:
        holdings    = c.get("holdings", [])
        c_tickers   = {h.get("ticker") for h in holdings}
        has_alert   = bool(c_tickers & alert_tickers)
        is_vip      = c.get("vip", False)
        pnl_data    = _get_pnl(c, eod)
        worst_pct   = min((p["change_pct"] for p in pnl_data), default=0)
        best_pct    = max((p["change_pct"] for p in pnl_data), default=0)

        # Phân nhóm
        if has_alert or worst_pct < -5:
            group = "A"
        elif is_vip or best_pct > 5:
            group = "B"
        else:
            group = "C"

        groups[group].append(c.get("name", ""))
        note = _build_note(c, pnl_data, group, worst_pct, best_pct)
        notes.append(note)

    # Ghi file markdown vào private/
    out_dir  = output_dir(date_str) / "private"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"customer_notes_{date_str}.md"

    lines = [
        f"# DANH SÁCH LIÊN HỆ HÔM NAY — {datetime.now().strftime('%d/%m/%Y')}",
        "═" * 45,
        f"NHÓM A (gọi ngay):  {', '.join(groups['A']) or 'Không có'}",
        f"NHÓM B (nếu kịp):   {', '.join(groups['B']) or 'Không có'}",
        f"NHÓM C (bỏ qua):    {len(groups['C'])} khách hàng",
        "",
        "Thời gian tối ưu để gọi: **16h00–17h30**",
        "═" * 45,
        "",
    ] + notes

    out_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Đã lưu ghi chú: {out_path}")

    _print_contact_summary(groups)
    return out_path


def _get_pnl(customer: dict, eod: dict) -> list[dict]:
    """Tính P&L hôm nay cho từng mã của KH từ EOD cache."""
    wl_map = {w["ticker"]: w for w in eod.get("watchlist_eod", [])}
    result = []
    for h in customer.get("holdings", []):
        ticker = h.get("ticker", "")
        cost   = h.get("cost", 0)
        shares = h.get("shares", 0)
        close  = wl_map.get(ticker, {}).get("close", cost)
        chg    = wl_map.get(ticker, {}).get("change_pct", 0)
        pnl    = (close - cost) * shares if cost else 0
        result.append({
            "ticker": ticker, "close": close,
            "change_pct": chg, "pnl": pnl,
        })
    return result


def _build_note(c: dict, pnl: list, group: str, worst: float, best: float) -> str:
    """Xây dựng ghi chú 1 KH theo format markdown."""
    name    = c.get("name", "Quý khách")
    total   = sum(p["pnl"] for p in pnl)
    sign    = "+" if total >= 0 else ""
    worst_t = min(pnl, key=lambda p: p["change_pct"], default={}).get("ticker", "N/A")
    best_t  = max(pnl, key=lambda p: p["change_pct"], default={}).get("ticker", "N/A")

    # Tạo câu mở đầu gợi ý dựa trên nhóm
    if group == "A" and worst < 0:
        opener = (
            f"'{name} ơi, hôm nay {worst_t} của mình "
            f"có điều chỉnh {worst:.2f}%. "
            f"Mình muốn cập nhật thêm cho anh/chị về diễn biến và "
            f"kịch bản phiên mai.'"
        )
    elif group == "B" and best > 0:
        opener = (
            f"'{name} ơi, hôm nay {best_t} của mình "
            f"tăng tốt {best:.2f}%. "
            f"Mình muốn chia sẻ thêm về bức tranh thị trường hôm nay.'"
        )
    else:
        opener = f"'{name} ơi, mình gọi để cập nhật tình hình thị trường hôm nay.'"

    return "\n".join([
        f"## {name} — Nhóm {group}",
        "",
        f"**P&L hôm nay:** {sign}{total:,.0f} VNĐ | "
        f"Tốt nhất: {best_t} ({best:+.2f}%) | "
        f"Yếu nhất: {worst_t} ({worst:+.2f}%)",
        "",
        "**Điểm nên đề cập:**",
        f"- Diễn biến {worst_t if group == 'A' else best_t} hôm nay",
        "- Nhận định thị trường chung (từ EOD report)",
        "",
        "**Câu mở đầu gợi ý:**",
        opener,
        "",
        "**Broker cần chuẩn bị thêm:** _(tự điền)_",
        "",
        "---",
    ])


def _print_contact_summary(groups: dict) -> None:
    sep = "─" * 50
    print(f"\n{sep}")
    print("  DANH SÁCH LIÊN HỆ HÔM NAY")
    print(sep)
    print(f"  🔴 Nhóm A (gọi ngay):  {', '.join(groups['A']) or 'Không có'}")
    print(f"  🟡 Nhóm B (nếu kịp):   {', '.join(groups['B']) or 'Không có'}")
    print(f"  🟢 Nhóm C (bỏ qua):    {len(groups['C'])} khách hàng")
    print(sep + "\n")
