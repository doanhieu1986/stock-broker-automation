"""
skills/after_hours/scripts/draft_outreach.py
Bước 3 ca after-hours: Soạn draft email trả lời KH tồn đọng.
"""

from datetime import datetime
from pathlib  import Path

from utils.data_loader import read_json, output_dir, today, DATA_DIR
from utils.logger      import get_logger

log = get_logger(__name__)

DISCLAIMER_SHORT = (
    "Thông tin chỉ mang tính tham khảo. "
    "Mọi quyết định đầu tư thuộc về Quý khách."
)


def run() -> Path:
    """Soạn draft trả lời cho các câu hỏi KH tồn đọng."""
    date_str = today()
    pending  = read_json(DATA_DIR / f"pending_responses_{date_str}.json", default=[])

    if not pending:
        log.info("Không có câu hỏi KH tồn đọng hôm nay.")
        return None

    log.info(f"Soạn {len(pending)} draft email KH...")
    lines = [
        f"# Draft Email Trả Lời KH — {datetime.now().strftime('%d/%m/%Y')}",
        f"*{len(pending)} câu hỏi cần trả lời — Broker review và gửi*",
        "",
    ]

    for item in pending:
        name     = item.get("customer_name", "Quý khách")
        question = item.get("question", "")
        ticker   = item.get("ticker", "")
        context  = item.get("context", "")

        draft = _draft_reply(name, question, ticker, context)
        lines += [
            f"## {name}",
            f"**Câu hỏi:** {question}",
            "",
            "**Draft trả lời:**",
            draft,
            "",
            "---",
            "",
        ]

    out_dir  = output_dir(date_str) / "private"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"email_drafts_{date_str}.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Đã soạn drafts: {out_path.name}")
    return out_path


def _draft_reply(name: str, question: str, ticker: str, context: str) -> str:
    """Tạo draft email ngắn gọn, chuyên nghiệp, không khuyến nghị."""
    greeting = f"Chào {name},"
    body = context if context else (
        f"Cảm ơn anh/chị đã hỏi về {ticker or 'thị trường'}. "
        f"Dựa trên dữ liệu hiện tại, {context or 'mình sẽ cập nhật thêm sau khi có thêm thông tin'}."
    )
    return (
        f"{greeting}\n\n"
        f"{body}\n\n"
        f"*{DISCLAIMER_SHORT}*\n\n"
        "Nếu anh/chị cần trao đổi thêm, mình có thể gọi điện vào "
        "sáng mai sau khi có báo cáo thị trường.\n\n"
        "Trân trọng,"
    )
