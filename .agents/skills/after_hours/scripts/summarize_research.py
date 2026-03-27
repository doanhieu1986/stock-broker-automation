"""
skills/after_hours/scripts/summarize_research.py
Bước 2 ca after-hours: Tìm và tóm tắt báo cáo phân tích CTCK mới.
"""

import sys
from datetime import datetime
from pathlib  import Path
sys.path.insert(0, str(Path(__file__).parents[4]))

from utils.api_client  import fetch_rss
from utils.data_loader import cache_write, today
from utils.logger      import api_call, section, get_logger

log = get_logger(__name__)

CTCK_SOURCES = {
    "SSI":   "https://www.ssi.com.vn/en/research/rss",
    "VCSC":  "https://www.vcsc.com.vn/research/rss",
    "MBS":   "https://mbs.com.vn/tin-tuc/bao-cao-phan-tich/rss",
    "VDSC":  "https://www.rong-viet.com.vn/research/rss",
}

MAX_REPORTS = 5


def run() -> Path:
    """Tìm báo cáo CTCK mới và tóm tắt 5 điểm chính mỗi báo cáo."""
    log.info("Tóm tắt báo cáo phân tích CTCK...")
    date_str  = today()
    watchlist = load_watchlist()
    tickers   = set(watchlist.get("tickers", []))

    all_reports  = []
    for ctck, url in CTCK_SOURCES.items():
        items = fetch_rss(url, max_items=10)
        for item in items:
            title = item.get("title", "")
            # Kiểm tra có liên quan watchlist không
            related = [t for t in tickers if t in title.upper()]
            all_reports.append({
                "ctck":      ctck,
                "title":     title,
                "link":      item.get("link", ""),
                "published": item.get("published", ""),
                "summary":   item.get("summary", "")[:600],
                "related_tickers": related,
                "priority":  1 if related else 0,
            })

    # Sắp xếp ưu tiên mã trong watchlist
    all_reports.sort(key=lambda r: r["priority"], reverse=True)
    selected = all_reports[:MAX_REPORTS]

    # Xây output markdown
    lines = [
        f"# Tóm tắt báo cáo CTCK — {datetime.now().strftime('%d/%m/%Y')}",
        "",
    ]
    for r in selected:
        lines += [
            f"## [{r['ctck']}] {r['title']}",
            f"*{r['published']}*" + (
                f" | Liên quan: **{', '.join(r['related_tickers'])}**"
                if r["related_tickers"] else ""
            ),
            "",
            "**Nội dung chính:**",
            r["summary"] or "(Không có tóm tắt — xem link gốc)",
            "",
            f"🔗 [Đọc báo cáo đầy đủ]({r['link']})",
            "",
            "> ⚠ Đây là quan điểm của " + r['ctck'] +
            ", không phải quan điểm của công ty chúng ta.",
            "",
            "---",
            "",
        ]

    if not selected:
        lines.append("*Không tìm thấy báo cáo mới từ các CTCK hôm nay.*")

    out_path = output_dir(date_str) / f"research_summary_{date_str}.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Đã tóm tắt {len(selected)} báo cáo → {out_path.name}")
    return out_path
