---
name: eod-report
description: >
  Tổng kết phiên giao dịch và liên hệ khách hàng (15h00–18h00).
  Kích hoạt khi broker nói "tổng kết ngày", "báo cáo cuối ngày",
  "EOD report", "liên hệ khách hàng", "danh mục khách hàng hôm nay",
  "top gainers losers", hoặc khi thời gian hệ thống trong khoảng
  14h55–18h00. Skill thu thập dữ liệu đóng cửa, tạo báo cáo Word
  cho broker, tổng hợp P&L danh mục từng KH, và soạn nội dung
  liên hệ chăm sóc khách hàng — tất cả chờ broker duyệt.
---

# EOD Report Skill — Tổng kết & Liên hệ KH 15h00–18h00

## Mục tiêu

Đến 18h00, broker có sẵn:

1. File Word `eod_report_{date}.docx` — báo cáo đầy đủ phiên hôm nay
2. Bảng P&L từng KH — riêng tư, lưu trong `private/`
3. Danh sách KH cần liên hệ hôm nay — kèm nội dung soạn sẵn
4. JSON tổng kết ngày — input cho ca After-hours soạn newsletter

---

## Quy trình thực hiện

---

### Bước 1 — Thu thập dữ liệu đóng cửa (15h00–15h30)

**Script:** `scripts/collect_eod_data.py`

Chạy ngay sau khi ATC kết thúc lúc 15h00.

#### 1.1 Dữ liệu thị trường chung

```python
eod_market = {
    # Chỉ số chính
    "vnindex_close":    fetch_close("VNINDEX"),
    "vnindex_change":   pct_change("VNINDEX"),
    "hnx_close":        fetch_close("HNX"),
    "vn30_close":       fetch_close("VN30"),
    "total_volume":     fetch_total_market_volume(),   # tỷ VNĐ
    "market_breadth": {
        "advances":     count_advancing_stocks(),
        "declines":     count_declining_stocks(),
        "unchanged":    count_unchanged_stocks(),
    },
    # Top movers toàn thị trường
    "top5_gainers":     fetch_top_gainers(n=5),
    "top5_losers":      fetch_top_losers(n=5),
    "top5_volume":      fetch_top_volume(n=5),        # thanh khoản cao nhất
    # Nhóm ngành
    "sector_heatmap":   fetch_sector_performance(),   # % thay đổi theo ngành
}
```

#### 1.2 Dữ liệu danh mục từng KH

```python
for customer in load_customers("data/customer_list.json"):
    portfolio = fetch_portfolio(customer.id, db="broker_db")
    eod_portfolio[customer.id] = {
        "holdings": [
            {
                "ticker":       ticker,
                "qty":          qty,
                "avg_cost":     avg_cost,
                "close_price":  close_prices[ticker],
                "pnl_today":    (close_prices[ticker] - prev_close[ticker]) * qty,
                "pnl_total":    (close_prices[ticker] - avg_cost) * qty,
                "pnl_pct":      pct vs avg_cost,
            }
            for ticker, qty, avg_cost in portfolio
        ],
        "nav_today":        sum(pnl_today),
        "nav_total":        sum(pnl_total),
        "nav_pct_today":    nav_today / total_asset,
    }
```

Lưu vào: `data/cache/eod_portfolio_{date}.json` (BẢO MẬT)

---

### Bước 2 — Tạo báo cáo EOD Word (15h30–16h30)

**Script:** `scripts/generate_eod_docx.py`
**Template:** `templates/eod_report.docx`
**Output:** `outputs/{date}/eod_report_{date}.docx`

#### 2.1 Cấu trúc file Word

```
Section 1: DASHBOARD TỔNG QUAN
  ┌─────────────────────────────────────────┐
  │  VN-Index  {điểm}  ({±%})              │
  │  HNX       {điểm}  ({±%})              │
  │  VN30      {điểm}  ({±%})              │
  │  KL Toàn TT: {tỷ VNĐ}                  │
  │  Độ rộng:  {N}↑  {M}↓  {K}–           │
  └─────────────────────────────────────────┘
  Biểu đồ cột: Hiệu suất ngành hôm nay (sector heatmap)

Section 2: TOP MOVERS & LÝ DO BIẾN ĐỘNG
  Top 5 tăng mạnh:
    [MÃ]  +{%}  KL: {K cp}  Lý do: {1 câu — tìm từ tin tức}
  Top 5 giảm mạnh:
    [MÃ]  -{%}  KL: {K cp}  Lý do: {1 câu — tìm từ tin tức}
  Top 5 thanh khoản:
    [MÃ]  {KL tỷ VNĐ}  {±%}

Section 3: DIỄN BIẾN WATCHLIST
  Bảng tổng hợp tất cả mã trong watchlist hôm nay:
  [MÃ] | Mở | Cao | Thấp | Đóng | ±% | KL | vs TB20

Section 4: CẢNH BÁO & PHÂN TÍCH ĐÃ PHÁT HÔM NAY
  Tổng hợp từ outputs/{date}/alerts_{date}.json
  và outputs/{date}/analysis_*.json (on-demand ca giao dịch)

Section 5: KHUYẾN NGHỊ & GHI CHÚ
  [Broker tự điền tay — Claude để trống section này]
  Dòng gợi ý: "Broker điền nhận định và hành động cho ngày mai"

Footer bắt buộc mỗi trang:
  "Báo cáo nội bộ — Thông tin chỉ mang tính tham khảo"
  "Tạo lúc: {HH:MM} {DD/MM/YYYY}"
```

#### 2.2 File danh mục KH (riêng biệt — bảo mật)

Tạo thêm 1 file Excel riêng: `outputs/{date}/private/portfolio_summary_{date}.xlsx`

```
Sheet "Tổng hợp":   Danh sách KH | NAV hôm nay | ±% | Tổng P&L
Sheet "Chi tiết":   Từng KH — từng mã — cost — giá đóng — P&L
```

**Không** đưa dữ liệu này vào file Word chung `eod_report_{date}.docx`.

---

### Bước 3 — Phân tích lý do biến động (15h45–16h15)

**Script:** `scripts/explain_movers.py`

Với mỗi mã trong top 5 tăng/giảm và mã trong watchlist biến động > ±2%:

1. Tìm tin tức liên quan trong 24h qua (nguồn: CafeF, VnExpress, HOSE)
2. Kiểm tra có sự kiện pháp lý không (UBCKNN, BCTC công bố)
3. Kiểm tra khối lượng bất thường → dấu hiệu lực cầu/cung lớn
4. Viết 1 câu giải thích — format: `"[Nguyên nhân chính] — [Dữ liệu bổ trợ]"`

Ví dụ hợp lệ:
```
HPG +2.9%: Giá thép HRC tăng 1.2% tuần này, KL giao dịch gấp 2.1 lần TB.
VHM -2.1%: Thông tin điều tra UBCKNN về trái phiếu, xuất hiện lúc 10h22.
```

---

### Bước 4 — Soạn nội dung liên hệ KH (16h30–17h30)

**Script:** `scripts/prepare_customer_contact.py`

#### 4.1 Phân loại KH cần liên hệ hôm nay

```python
priority_contacts = []

for customer in all_customers:
    reasons = []

    # Ưu tiên 1: Danh mục biến động mạnh
    if abs(customer.nav_pct_today) >= 3.0:
        reasons.append(f"NAV thay đổi {customer.nav_pct_today:+.1f}% hôm nay")

    # Ưu tiên 2: Có mã sắp đến sự kiện quan trọng
    for ticker in customer.holdings:
        if ticker in upcoming_events_3days:
            reasons.append(f"{ticker} có sự kiện: {event_desc}")

    # Ưu tiên 3: KH VIP — liên hệ hàng ngày không phụ thuộc biến động
    if customer.tier == "VIP":
        reasons.append("Chăm sóc định kỳ KH VIP")

    if reasons:
        priority_contacts.append({
            "customer": customer,
            "reasons":  reasons,
            "channel":  customer.preferred_channel,  # Zalo / điện thoại / LinkedIn
        })
```

#### 4.2 Soạn nội dung liên hệ mẫu

Với mỗi KH trong `priority_contacts`, soạn nội dung tùy kênh:

**Zalo (ngắn gọn, < 5 dòng):**
```
Chào {Tên KH}, broker {Tên Broker} đây ạ.

Hôm nay danh mục của anh/chị [tóm tắt 1 dòng].
[1 điểm đáng chú ý liên quan danh mục].

Anh/chị có muốn trao đổi thêm không ạ?
```

**Điện thoại (bullet gợi ý nói chuyện):**
```
Điểm mở đầu:  Hỏi thăm + tóm tắt thị trường hôm nay
Điểm chính:   [Vấn đề cụ thể của KH: mã biến động, sự kiện...]
Kết thúc:     Hỏi nhu cầu — đặt lịch gặp nếu cần
Thời gian:    ~ 5–7 phút
```

**Quy tắc bắt buộc:**
- KHÔNG dùng ngôn ngữ khuyến nghị mua/bán trong nội dung liên hệ
- KHÔNG gửi tự động — broker tự gửi sau khi đọc và chỉnh sửa
- Lưu nội dung vào `outputs/{date}/private/contact_{customer_id}_{date}.txt`

---

### Bước 5 — Đóng gói & bàn giao sang ca After-hours (17h30–18h00)

**Script:** `scripts/eod_handoff.py`

Tổng hợp JSON đầy đủ cho ca After-hours dùng soạn newsletter:

```json
// data/cache/eod_summary_{date}.json
{
  "date": "20250326",
  "market": {
    "vnindex": { "close": 1282.3, "change_pct": 0.94 },
    "hnx":     { "close": 228.1,  "change_pct": 0.41 },
    "total_volume_billion": 18650
  },
  "breadth": { "advances": 312, "declines": 187, "unchanged": 64 },
  "top_gainers": [
    { "ticker": "HPG", "change_pct": 2.87, "reason": "..." }
  ],
  "top_losers": [...],
  "alerts_count": { "red": 2, "yellow": 3 },
  "watchlist_summary": [...],
  "contacts_prepared": 8,
  "files_created": [
    "outputs/20250326/eod_report_20250326.docx",
    "outputs/20250326/private/portfolio_summary_20250326.xlsx"
  ]
}
```

In terminal lúc 18h00:

```
╔═══════════════════════════════════════════════════════╗
║  CA TỔNG KẾT HOÀN THÀNH — {DD/MM/YYYY} 18:00         ║
╠═══════════════════════════════════════════════════════╣
║  VN-Index đóng cửa: {điểm} ({±%})                    ║
║  Báo cáo EOD:       outputs/{date}/eod_report.docx   ║
║  Danh mục KH:       outputs/{date}/private/ (bảo mật)║
║  Liên hệ KH:        {N} nội dung soạn sẵn            ║
╠═══════════════════════════════════════════════════════╣
║  Chuyển sang ca After-hours — after-hours skill       ║
╚═══════════════════════════════════════════════════════╝
```

---

## Xử lý lỗi

| Tình huống | Hành động |
|---|---|
| API chưa có giá đóng cửa (chạy trước 15h05) | Chờ 5 phút, thử lại |
| Không kết nối được broker_db | Dùng cache portfolio từ hôm qua, đánh dấu "Chưa cập nhật" |
| Template Word bị hỏng | Dùng `templates/backup/eod_report.docx` |
| Không tìm được lý do biến động | Ghi "Chưa xác định được nguyên nhân" — không bịa |
| KH có giao dịch lớn bất thường | Ghi flag, báo broker review trước khi liên hệ |

---

## Tài nguyên liên quan

- Input ca giao dịch: `logs/realtime_{date}.csv`, `outputs/{date}/alerts_{date}.json`
- Input ca trưa: `data/cache/morning_summary_{date}.json`
- Danh sách KH: `data/customer_list.json`
- Database danh mục: PostgreSQL `broker_db` — bảng `portfolios`
- Template báo cáo: `templates/eod_report.docx`
- Output chính: `outputs/{date}/eod_report_{date}.docx`
- Output bảo mật: `outputs/{date}/private/`
- Bàn giao After-hours: `data/cache/eod_summary_{date}.json`
