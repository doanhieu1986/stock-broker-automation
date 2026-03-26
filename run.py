"""
run.py — Entry point chính.

Usage:
    python run.py --session morning
    python run.py --session trading
    python run.py --session midday
    python run.py --session eod
    python run.py --session after-hours
    python run.py --task analyze VCB BID
    python run.py --task newsletter --preview
    python run.py --check-apis
    python run.py --logs today
    python run.py --dry-run morning  (thêm --dry-run với --session)
"""

import argparse, sys
from datetime import datetime
from utils.logger import get_logger

log = get_logger("run")


def run_session(session: str, dry_run: bool = False):
    log.info("═"*55)
    log.info(f"  SESSION: {session.upper()}")
    log.info("═"*55)

    if session == "morning":
        from skills.morning_prep.scripts.fetch_global_markets import run as s1
        from skills.morning_prep.scripts.fetch_asia_markets   import run as s2
        from skills.morning_prep.scripts.scrape_regulatory    import run as s3
        from skills.morning_prep.scripts.fundamental_compare  import run as s4
        from skills.morning_prep.scripts.generate_morning_pdf import run as s5
        steps = [("Tin tức quốc tế",s1),("Thị trường châu Á",s2),
                 ("Chính sách & pháp lý",s3),("Phân tích cơ bản",s4),
                 ("Xuất PDF",s5)]

    elif session == "trading":
        from skills.trading_hours.scripts.price_monitor  import run as s1
        from skills.trading_hours.scripts.session_summary import run as s2
        steps = [("Monitor realtime",s1),("Tổng kết phiên",s2)]

    elif session == "midday":
        from skills.midday_analysis.scripts.summarize_morning_session import run as s1
        from skills.midday_analysis.scripts.technical_deep            import run as s2
        from skills.midday_analysis.scripts.generate_vip_brief        import run as s3
        from skills.midday_analysis.scripts.prepare_afternoon         import run as s4
        steps = [("Tóm tắt phiên sáng",s1),("Phân tích sâu",s2),
                 ("Báo cáo VIP",s3),("Chuẩn bị chiều",s4)]

    elif session == "eod":
        from skills.eod_report.scripts.collect_eod_data        import run as s1
        from skills.eod_report.scripts.generate_eod_docx       import run as s2
        from skills.eod_report.scripts.prepare_customer_contact import run as s3
        from skills.eod_report.scripts.eod_handoff             import run as s4
        steps = [("Thu thập đóng cửa",s1),("Báo cáo Word",s2),
                 ("Ghi chú KH",s3),("Bàn giao after-hours",s4)]

    elif session == "after-hours":
        from skills.after_hours.scripts.render_newsletter     import run as s1
        from skills.after_hours.scripts.summarize_research    import run as s2
        from skills.after_hours.scripts.draft_outreach        import run as s3
        from skills.after_hours.scripts.fetch_tomorrow_events import run as s4
        steps = [("Newsletter",s1),("Báo cáo CTCK",s2),
                 ("Draft email KH",s3),("Sự kiện ngày mai",s4)]
    else:
        log.error(f"Session không hợp lệ: {session}")
        return

    for label, fn in steps:
        log.info(f"► {label}")
        if not dry_run:
            try:
                fn()
            except Exception as e:
                log.error(f"  FAILED: {e} — tiếp tục")


def run_task(task: str, args: list, preview: bool = False):
    if task == "morning-pdf":
        from skills.morning_prep.scripts.generate_morning_pdf import run
        run()
    elif task == "analyze":
        from skills.trading_hours.scripts.technical_quick import analyze_ticker
        for t in args:
            analyze_ticker(t.upper())
    elif task == "newsletter":
        from skills.after_hours.scripts.render_newsletter import run
        run(preview=preview)
    else:
        log.error(f"Task '{task}' không nhận ra")


def check_apis():
    from utils.api_client import fetch_yahoo_quote, fetch_cafef_index, fetch_usd_vnd
    checks = [
        ("Yahoo Finance", lambda: fetch_yahoo_quote("^DJI")),
        ("CafeF Index",   lambda: fetch_cafef_index()),
        ("USD/VND rate",  lambda: fetch_usd_vnd()),
    ]
    print("\n── Kiểm tra API ─────────────────────────────────")
    for name, fn in checks:
        try:
            result = fn()
            status = "✓ OK" if result else "✗ None"
        except Exception as e:
            status = f"✗ {e}"
        print(f"  {name:20s} {status}")
    print("─────────────────────────────────────────────────\n")


def show_logs(when: str = "today"):
    from utils.data_loader import today
    from pathlib import Path
    date_str = today() if when == "today" else when
    path = Path("logs") / f"api_{date_str}.log"
    if not path.exists():
        print(f"Log không tồn tại: {path}")
        return
    print(path.read_text(encoding="utf-8")[-3000:])


def main():
    parser = argparse.ArgumentParser(description="Broker Automation")
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--session", choices=["morning","trading","midday","eod","after-hours"])
    group.add_argument("--task",    metavar="TASK")
    group.add_argument("--check-apis", action="store_true")
    group.add_argument("--logs",    metavar="DATE")
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--preview",  action="store_true")
    parser.add_argument("args",       nargs="*")
    opts = parser.parse_args()

    log.info(f"Bắt đầu: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    if opts.dry_run: log.warning("DRY-RUN MODE")

    if opts.session:
        run_session(opts.session, dry_run=opts.dry_run)
    elif opts.task:
        run_task(opts.task, opts.args, preview=opts.preview)
    elif opts.check_apis:
        check_apis()
    elif opts.logs:
        show_logs(opts.logs)

    log.info(f"Hoàn thành: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
