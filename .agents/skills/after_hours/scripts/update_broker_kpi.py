"""
skills/after_hours/scripts/update_broker_kpi.py
Bước 5: Tổng kết KPI cá nhân cuối ngày.
"""
import json
from datetime import datetime
from utils.data_loader import load_alerts, load_realtime_log, output_dir, today
from utils.logger      import get_logger
log = get_logger(__name__)

def run():
    log.info("Tổng kết KPI cuối ngày...")
    date_str = today()
    out_dir  = output_dir(date_str)
    alerts   = load_alerts(date_str)
    df       = load_realtime_log(date_str)

    kpi = {
        "date":      date_str,
        "generated": datetime.now().isoformat(),
        "system": {
            "alerts_fired":      len(alerts),
            "alerts_critical":   sum(1 for a in alerts if a.get("level")=="critical"),
            "ondemand_analyses": len(list(out_dir.glob("analysis_*.json"))),
            "deep_analyses":     len(list(out_dir.glob(f"deep_analysis_*_{date_str}.md"))),
            "newsletter_ready":  (out_dir/f"newsletter_{date_str}.html").exists(),
            "rows_logged":       len(df) if not df.empty else 0,
        },
        "broker_fill": {"contacts_made": None, "fee_revenue_vnd": None, "notes": ""},
    }

    out_path = out_dir/f"kpi_{date_str}.json"
    out_path.write_text(json.dumps(kpi, ensure_ascii=False, indent=2), encoding="utf-8")

    s = kpi["system"]
    sep = "═"*52
    print(f"\n╔{sep}╗")
    print(f"║  CA SAU GIỜ HOÀN THÀNH — {datetime.now().strftime('%d/%m/%Y %H:%M')}{'':>14}║"[:56])
    print(f"╠{sep}╣")
    print(f"║  Newsletter    {'✓' if s['newsletter_ready'] else '✗'} Sẵn sàng gửi{'':>30}║"[:56])
    print(f"║  Cảnh báo     ✓ {s['alerts_fired']} phát ({s['alerts_critical']} khẩn cấp){'':>20}║"[:56])
    print(f"║  On-demand    ✓ {s['ondemand_analyses']} phân tích{'':>30}║"[:56])
    print(f"║  Phân tích sâu ✓ {s['deep_analyses']} mã{'':>33}║"[:56])
    print(f"╠{sep}╣")
    print(f"║  Việc còn lại: duyệt newsletter, gửi email KH{'':>8}║")
    print(f"║  Ca sáng tiếp theo: morning-prep 06:00{'':>14}║")
    print(f"╚{sep}╝\n")
    log.info(f"  KPI lưu tại: {out_path.name}")
