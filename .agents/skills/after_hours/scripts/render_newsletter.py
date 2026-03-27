"""
skills/after_hours/scripts/render_newsletter.py
Bước 1 ca after-hours: Soạn newsletter HTML từ eod_summary.
"""

import sys
from datetime import datetime
from pathlib  import Path
sys.path.insert(0, str(Path(__file__).parents[4]))
from utils.data_loader import load_cache, output_dir, today
from utils.logger      import get_logger

log = get_logger(__name__)

TEMPLATE = Path("templates/newsletter_base.html")
DISCLAIMER_HTML = """
<p style="font-size:11px;color:#888;margin-top:24px;border-top:1px solid #eee;padding-top:12px;">
Bản tin này được cung cấp chỉ nhằm mục đích thông tin và tham khảo.
Nội dung không cấu thành khuyến nghị đầu tư hay tư vấn tài chính.
Nhà đầu tư tự chịu trách nhiệm về quyết định của mình.
Dữ liệu có thể có độ trễ.
</p>"""


def run(preview: bool = False) -> Path:
    """
    Tạo newsletter HTML từ dữ liệu EOD bàn giao.

    Args:
        preview: Nếu True thì chỉ print nội dung, không lưu file.
    """
    log.info("Soạn newsletter...")
    date_str = today()
    eod      = load_eod_summary(date_str)

    if not eod:
        log.error("Không có eod_summary — chạy eod_handoff.py trước")
        return None

    vn       = eod.get("market", {}).get("vn_index", {})
    chg      = vn.get("change_pct", 0)
    value    = vn.get("value", "N/A")
    gainers  = eod.get("top_gainers",  [])
    losers   = eod.get("top_losers",   [])
    notable  = eod.get("notable_events", [])
    one_liner = eod.get("session_one_liner", "")
    date_show = datetime.now().strftime("%d/%m/%Y")
    sign      = "+" if chg >= 0 else ""

    # ── Subject line ──────────────────────────────────────────────────────
    subject = f"Nhận định {date_show} | VN-Index {value} ({sign}{chg:.2f}%)"

    # ── Block 1: Tóm tắt phiên ────────────────────────────────────────────
    foreign = eod.get("market", {}).get("foreign_flow", {})
    net     = foreign.get("net_bil", 0)
    wl      = eod.get("watchlist_summary", [])
    top_up  = [w for w in wl if w.get("change_pct", 0) > 0]
    top_dn  = [w for w in wl if w.get("change_pct", 0) < 0]

    bullets_b1 = [
        f"VN-Index {sign}{chg:.2f}% ({value} điểm) — "
        + ("thị trường tăng điểm phiên thứ " + str(_streak(chg)) + "."
           if chg > 0 else "phiên điều chỉnh."),

        (f"Dẫn đầu: {gainers[0]['ticker']} (+{gainers[0]['change_pct']:.2f}%)"
         if gainers else "") +
        (f" | Giảm mạnh: {losers[0]['ticker']} ({losers[0]['change_pct']:.2f}%)"
         if losers else ""),

        f"Khối ngoại {'mua' if net >= 0 else 'bán'} ròng {abs(net):,.0f} tỷ VNĐ."
        if net else "Thanh khoản ở mức bình thường.",
    ]

    # ── Block 2: Cổ phiếu đáng chú ý ─────────────────────────────────────
    spotlight = _pick_spotlight(gainers, losers, notable)
    b2_html   = _spotlight_html(spotlight) if spotlight else ""

    # ── Block 3: Ngày mai ─────────────────────────────────────────────────
    b3_html = _tomorrow_html()

    # ── Render HTML ───────────────────────────────────────────────────────
    html = _render(
        subject, date_show, value, sign, chg,
        bullets_b1, b2_html, b3_html,
    )

    if preview:
        print(f"\n── PREVIEW NEWSLETTER ──────────────────────────")
        print(f"Subject: {subject}")
        print(f"One-liner: {one_liner}")
        print(f"Block 1: {len(bullets_b1)} bullets")
        print(f"Spotlight: {spotlight.get('ticker', 'N/A') if spotlight else 'None'}")
        print("────────────────────────────────────────────────\n")
        return None

    out_path = output_dir(date_str) / f"newsletter_{date_str}.html"
    out_path.write_text(html, encoding="utf-8")
    log.info(f"Newsletter đã sẵn sàng: {out_path}")
    log.warning("⚠ Broker cần review và duyệt trước khi gửi!")
    return out_path


def _pick_spotlight(gainers: list, losers: list, notable: list) -> dict | None:
    """Chọn 1 mã đáng chú ý nhất với lý do rõ ràng."""
    if gainers:
        return gainers[0]
    if losers:
        return losers[0]
    return None


def _spotlight_html(stock: dict) -> str:
    ticker = stock.get("ticker", "")
    chg    = stock.get("change_pct", 0)
    sign   = "+" if chg >= 0 else ""
    color  = "#1D9E75" if chg >= 0 else "#993C1D"
    return f"""
    <tr><td style="padding:16px 0;">
      <h3 style="margin:0 0 8px;font-size:15px;">{ticker}
        <span style="color:{color};font-weight:500;">{sign}{chg:.2f}%</span>
      </h3>
      <p style="margin:0;color:#444;font-size:13px;">
        Cổ phiếu giao dịch nổi bật hôm nay với khối lượng
        {stock.get('volume_bil', 0):,.1f} tỷ VNĐ.
        Broker sẽ cập nhật thêm thông tin trong buổi trao đổi tới.
      </p>
    </td></tr>"""


def _tomorrow_html() -> str:
    return """
    <tr><td style="padding:16px 0;">
      <p style="margin:0;color:#444;font-size:13px;">
        Lịch sự kiện ngày mai đang được cập nhật — broker sẽ gửi thêm nếu có
        sự kiện quan trọng ảnh hưởng đến danh mục của bạn.
      </p>
    </td></tr>"""


def _streak(chg: float) -> int:
    """Placeholder — thực tế cần lịch sử VN-Index."""
    return 1 if chg > 0 else 0


def _render(subject, date_show, value, sign, chg, bullets, b2, b3) -> str:
    bullets_html = "".join(f"<li>{b}</li>" for b in bullets if b)
    chg_color    = "#1D9E75" if chg >= 0 else "#993C1D"

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:#f5f5f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:24px 16px;">
<table width="600" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:12px;overflow:hidden;
              border:1px solid #e0dfd6;">

  <!-- Header -->
  <tr><td style="background:#0f3d6e;padding:24px 32px;">
    <p style="margin:0;color:#85B7EB;font-size:11px;letter-spacing:.1em;
              text-transform:uppercase;">NHẬN ĐỊNH THỊ TRƯỜNG</p>
    <h1 style="margin:6px 0 4px;color:#fff;font-size:20px;font-weight:500;">
      VN-Index {value}
      <span style="color:{chg_color};">{sign}{chg:.2f}%</span>
    </h1>
    <p style="margin:0;color:#a8c8e8;font-size:13px;">{date_show}</p>
  </td></tr>

  <!-- Body -->
  <table cellpadding="0" cellspacing="0" style="padding:0 32px;">

    <!-- Block 1 -->
    <tr><td style="padding-top:24px;">
      <h2 style="margin:0 0 12px;font-size:14px;font-weight:600;
                 text-transform:uppercase;color:#185FA5;letter-spacing:.06em;">
        Tóm tắt phiên hôm nay
      </h2>
      <ul style="margin:0;padding-left:20px;color:#2c2c2a;font-size:13px;
                 line-height:1.8;">{bullets_html}</ul>
    </td></tr>

    <!-- Block 2 -->
    <tr><td style="padding-top:20px;">
      <h2 style="margin:0 0 4px;font-size:14px;font-weight:600;
                 text-transform:uppercase;color:#185FA5;letter-spacing:.06em;">
        Cổ phiếu đáng chú ý
      </h2>
      <table width="100%" cellpadding="0" cellspacing="0">{b2}</table>
    </td></tr>

    <!-- Block 3 -->
    <tr><td style="padding-top:20px;">
      <h2 style="margin:0 0 4px;font-size:14px;font-weight:600;
                 text-transform:uppercase;color:#185FA5;letter-spacing:.06em;">
        Chuẩn bị cho ngày mai
      </h2>
      <table width="100%" cellpadding="0" cellspacing="0">{b3}</table>
    </td></tr>

    <!-- Disclaimer -->
    <tr><td>{DISCLAIMER_HTML}</td></tr>
  </table>

</table>
</td></tr>
</table>
</body>
</html>"""
