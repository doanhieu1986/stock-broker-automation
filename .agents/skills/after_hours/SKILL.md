---
name: after-hours
description: >
  Soạn newsletter, học thuật nâng cao và chuẩn bị tài liệu cho ngày mai
  (18h00–21h00). Kích hoạt khi broker nói "soạn newsletter", "bản tin tối",
  "chuẩn bị ngày mai", "tóm tắt báo cáo SSI/VCSC", "học chứng chỉ",
  "cập nhật watchlist", hoặc khi thời gian hệ thống trong khoảng 18h00–21h30.
  Skill hoàn thiện newsletter chờ broker duyệt gửi, tổng hợp báo cáo
  phân tích từ các CTCK, và chuẩn bị đầy đủ tài liệu để ca sáng mai
  chạy trơn tru từ 6h00.
---

# After-hours Skill — Hoạt động sau giờ 18h00–21h00

## Mục tiêu

Đến 21h00, sẵn sàng cho ngày mai:

1. Newsletter hoàn chỉnh — chờ broker duyệt 1 lần rồi gửi
2. Báo cáo phân tích từ SSI/VCSC/MBS đã được tóm tắt 5 bullet/báo cáo
3. Watchlist ngày mai đã cập nhật với lý do cụ thể
4. Lịch sự kiện doanh nghiệp 3 ngày tới đã phân loại theo mức độ quan trọng
5. KPI cá nhân broker đã cập nhật — phi giao dịch, tỷ lệ hài lòng KH

---

## Quy trình thực hiện

---

### Bước 1 — Soạn Newsletter (18h00–19h00)

**Script:** `scripts/render_newsletter.py`
**Template:** `templates/newsletter_base.html`
**Output:** `outputs/{date}/newsletter_{date}.html`

#### 1.1 Đọc dữ liệu từ ca EOD

Load `data/cache/eod_summary_{date}.json` — file bàn giao từ ca EOD.
Nếu file chưa có → chạy `scripts/collect_eod_data.py` để lấy lại.

#### 1.2 Cấu trúc newsletter

```
Subject: "Nhận định thị trường {DD/MM} | VN-Index {điểm} ({±%})"

── HEADER ───────────────────────────────────────────────
  Logo công ty | Ngày {DD/MM/YYYY} | "BẢN TIN THỊ TRƯỜNG"

── BLOCK 1: TÓM TẮT PHIÊN HÔM NAY ─────────────────────
  • VN-Index {điểm} ({±%}) — KL {tỷ VNĐ}
  • Dòng tiền tập trung: [top 2 nhóm ngành tăng mạnh]
  • Điểm nổi bật: [1 sự kiện/tin tức đáng chú ý nhất]

── BLOCK 2: 1 CỔ PHIẾU ĐÁNG CHÚ Ý ─────────────────────
  Chọn 1 mã từ top movers hôm nay (ưu tiên mã phổ biến
  trong danh mục nhiều KH nhất).

  Cấu trúc phân tích ngắn (~150 chữ):
    Giá đóng cửa: {X} ({±%})
    Lý do biến động hôm nay: [1–2 câu từ Bước 3 ca EOD]
    Bức tranh kỹ thuật ngắn: MA, RSI — chỉ số liệu, không khuyến nghị
    Sự kiện sắp tới (nếu có): [GDKHQ, BCTC, ĐHCĐ...]

── BLOCK 3: DỰ BÁO & LỊCH SỰ KIỆN NGÀY MAI ────────────
  Lịch sự kiện quan trọng ngày mai:
    [MÃ CK]  [Loại sự kiện]  [Tóm tắt 1 dòng]

  Yếu tố vĩ mô cần theo dõi:
    [Lấy từ macro update cuối ca giao dịch — 15h00]

── FOOTER ───────────────────────────────────────────────
  Disclaimer bắt buộc (KHÔNG được bỏ qua, KHÔNG được rút gọn):

  "Thông tin trong bản tin này chỉ mang tính tham khảo và
   không cấu thành khuyến nghị đầu tư dưới bất kỳ hình thức
   nào. Nhà đầu tư cần tự đánh giá và chịu trách nhiệm với
   quyết định đầu tư của mình. Dữ liệu có thể có độ trễ."

  Unsubscribe link | Tên công ty | Địa chỉ | Giấy phép
```

#### 1.3 Quy tắc ngôn ngữ newsletter

**Được phép:**
- Mô tả diễn biến thị trường dựa trên số liệu
- Nêu sự kiện sắp diễn ra và ý nghĩa lịch sử của chúng
- Trích dẫn báo cáo phân tích từ CTCK (ghi rõ nguồn)

**TUYỆT ĐỐI KHÔNG dùng:**
```
❌ "Nên mua / nên bán / nên nắm giữ..."
❌ "Cơ hội tốt để tích lũy..."
❌ "Rủi ro thấp / tiềm năng cao..."
❌ "Chúng tôi khuyến nghị..."
❌ Bất kỳ cụm từ nào hàm ý broker đang đưa ra quyết định thay KH
```

#### 1.4 Quy trình duyệt & gửi

```
1. Render HTML → lưu outputs/{date}/newsletter_{date}.html
2. In terminal: "⏳ Newsletter sẵn sàng review: outputs/{date}/newsletter_{date}.html"
3. ═══ DỪNG — broker mở file, đọc kỹ, chỉnh sửa nếu cần ═══
4. Broker xác nhận: python run.py --task newsletter-send --confirm
5. Hệ thống gửi qua SMTP → ghi log số lượng người nhận
6. KHÔNG tự động gửi dù bất kỳ lý do gì
```

---

### Bước 2 — Tổng hợp báo cáo phân tích CTCK (19h00–20h00)

**Script:** `scripts/summarize_research.py`

#### 2.1 Nguồn báo cáo

Tải báo cáo phân tích mới nhất (trong ngày) từ:

| Nguồn | Loại | Cách lấy |
|---|---|---|
| SSI Research | PDF báo cáo cổ phiếu | API / scrape ssi.com.vn |
| VCSC (Bản Việt) | PDF báo cáo ngành | API / scrape vcsc.com.vn |
| MBS Research | PDF/Word | Email hoặc website |
| ACBS Research | PDF | acbs.com.vn |

Lọc: chỉ lấy báo cáo về mã có trong `data/watchlist.json`
hoặc mã KH đang nắm giữ.

#### 2.2 Format tóm tắt — đúng 5 bullet mỗi báo cáo

```
BÁO CÁO: {Tên mã} — {Tên CTCK} — {Ngày phát hành}
─────────────────────────────────────────────────
• Luận điểm chính: [Tóm tắt thesis 1 câu]
• Dữ liệu tài chính nổi bật: [Chỉ số cụ thể — doanh thu, EPS, ROE...]
• Rủi ro đã nêu: [Rủi ro chính CTCK đề cập]
• Catalyst ngắn hạn: [Sự kiện có thể ảnh hưởng giá trong 1–3 tháng]
• Khuyến nghị trong báo cáo: [Chép nguyên văn — ghi rõ đây là quan điểm {Tên CTCK}]
─────────────────────────────────────────────────
Nguồn: {CTCK} | {Ngày} | Tải đầy đủ: {link hoặc path file}
```

**Lưu ý quan trọng:**
- Bullet thứ 5 ghi NGUYÊN VĂN khuyến nghị của CTCK — không phải khuyến nghị của broker
- Phải ghi rõ nguồn để tránh nhầm lẫn với quan điểm của công ty

#### 2.3 Output

```
outputs/{date}/research_summary_{date}.md   ← tóm tắt tất cả báo cáo
outputs/{date}/research_raw/                ← PDF gốc lưu tại đây
    ├── SSI_{TICKER}_{date}.pdf
    ├── VCSC_{TICKER}_{date}.pdf
    └── ...
```

---

### Bước 3 — Cập nhật Watchlist ngày mai (20h00–20h30)

**Script:** `scripts/update_watchlist.py`

#### 3.1 Đọc watchlist hiện tại

```json
// data/watchlist.json (hiện tại)
{
  "date": "20250326",
  "tickers": ["VCB", "BID", "HPG", "VHM", "VIC"],
  "daily_compare_pair": ["VCB", "BID"],
  "added_reason": {
    "HPG": "Giá thép tăng — theo dõi breakout 28,000",
    "VHM": "ĐHCĐ ngày 28/03 — quan sát phản ứng"
  }
}
```

#### 3.2 Logic cập nhật

```python
new_watchlist = current_watchlist.copy()

# Thêm mã mới nếu:
# - Xuất hiện trong báo cáo CTCK hôm nay (Bước 2)
# - Có sự kiện quan trọng trong 3 ngày tới (Bước 4)
# - KH VIP vừa request phân tích sâu hôm nay

# Xóa mã nếu:
# - Đã xong sự kiện mà mã được thêm vào
# - Không còn trong danh mục bất kỳ KH nào
# - Thanh khoản < 10 tỷ/ngày liên tục 5 phiên

# Cập nhật daily_compare_pair:
# - Luân phiên theo ngành (ngân hàng → bất động sản → thép → hóa chất...)
# - Ưu tiên cặp có BCTC vừa ra hoặc sắp ra
```

Mọi thay đổi watchlist phải ghi rõ lý do:
```json
"added_reason": { "MSN": "BCTC Q1 công bố ngày mai — theo dõi phản ứng" },
"removed_reason": { "NVL": "ĐHCĐ đã xong, thanh khoản yếu dần" }
```

---

### Bước 4 — Lịch sự kiện doanh nghiệp 3 ngày tới (20h00–20h30)

**Script:** `scripts/fetch_tomorrow_events.py`

Chạy song song với Bước 3.

#### 4.1 Nguồn dữ liệu sự kiện

- Vietstock Calendar API — GDKHQ, trả cổ tức, phát hành thêm
- HNX/HOSE website — công bố BCTC chính thức
- UBCKNN — lịch họp, thông báo mới

#### 4.2 Phân loại sự kiện theo mức độ ảnh hưởng

```
MỨC A — Ảnh hưởng cao:
  GDKHQ, trả cổ tức tiền mặt > 500đ/cp, phát hành thêm > 20%,
  công bố BCTC quý (đặc biệt quý 4 hàng năm), ĐHCĐ bất thường

MỨC B — Ảnh hưởng trung bình:
  Trả cổ tức < 500đ/cp, ĐHCĐ thường niên, họp HĐQT
  
MỨC C — Theo dõi:
  Giao dịch nội bộ của lãnh đạo, thay đổi sở hữu cổ đông lớn
```

#### 4.3 Output format cho terminal

```
LỊCH SỰ KIỆN 3 NGÀY TỚI — cập nhật {HH:MM}
═══════════════════════════════════════════════════
  Ngày mai {DD/MM}:
  [A] VCB    — GDKHQ: Cổ tức 800đ/cp tiền mặt
  [B] MSN    — Công bố KQKD Q1/2025
  [C] HPG    — GĐ mua vào 500K cp (công bố hôm nay)

  {DD+1/MM}:
  [A] NVL    — Phát hành thêm 15% vốn điều lệ
  [B] BID    — ĐHCĐ thường niên 2025

  {DD+2/MM}:
  [B] VIC    — Họp HĐQT — dự kiến thông qua kế hoạch 2025
═══════════════════════════════════════════════════
```

Lưu: `data/cache/events_3days_{date}.json`
→ File này là input cho ca sáng hôm sau (morning-prep Bước 3).

---

### Bước 5 — Cập nhật KPI cá nhân broker (20h30–21h00)

**Script:** `scripts/update_broker_kpi.py`

Broker tự nhập hoặc hệ thống tự tính từ broker_db:

```
KPI NGÀY {DD/MM/YYYY}
─────────────────────────────────────────────
Phi giao dịch thu được:   {X triệu VNĐ}
Số lệnh thực hiện:        {N lệnh}
Số KH liên hệ hôm nay:   {M KH}
Tỷ lệ KH phản hồi tích cực: {%} (từ feedback Zalo/điện thoại)
KH VIP đã chăm sóc:      {K / tổng VIP}
Khiếu nại (nếu có):      {ghi chú}
─────────────────────────────────────────────
Tích lũy tháng {MM/YYYY}:
  Phi:  {X triệu} / KPI {Y triệu} = {%} hoàn thành
  KH mới: {N KH} / KPI {M KH}    = {%} hoàn thành
─────────────────────────────────────────────
```

Lưu: `data/broker_kpi_{YYYY_MM}.json` (append từng ngày)

---

### Kết thúc ca — Checklist cuối ngày (20h55–21h00)

Trước khi tắt hệ thống, xác nhận đủ:

```
CHECKLIST KẾT THÚC NGÀY — {DD/MM/YYYY}
═══════════════════════════════════════
Ca sáng:
  [x] outputs/{date}/morning_{date}.pdf
Ca giao dịch:
  [x] logs/realtime_{date}.csv
  [x] outputs/{date}/alerts_{date}.json
Ca nghỉ trưa:
  [x] data/cache/morning_summary_{date}.json
  [x] outputs/{date}/deep_*.pdf (nếu có)
  [x] outputs/{date}/private/vip_*.pdf (nếu có)
Ca EOD:
  [x] outputs/{date}/eod_report_{date}.docx
  [x] outputs/{date}/private/portfolio_summary_{date}.xlsx
  [x] data/cache/eod_summary_{date}.json
Ca After-hours:
  [x] outputs/{date}/newsletter_{date}.html (đã gửi hoặc đã duyệt)
  [x] outputs/{date}/research_summary_{date}.md
  [x] data/watchlist.json (đã cập nhật cho ngày mai)
  [x] data/cache/events_3days_{date}.json
  [x] data/broker_kpi_{YYYY_MM}.json

Nếu thiếu file nào → ghi vào logs/missing_{date}.log
═══════════════════════════════════════
```

In terminal lúc 21h00:

```
╔═══════════════════════════════════════════════════════╗
║  KẾT THÚC NGÀY — {DD/MM/YYYY} 21:00                  ║
╠═══════════════════════════════════════════════════════╣
║  Newsletter: {Đã gửi / Chờ broker duyệt}             ║
║  Báo cáo CTCK: {N} báo cáo tóm tắt                  ║
║  Watchlist mai: {M} mã ({+K thêm / -J xóa})          ║
║  Sự kiện 3 ngày: {P} sự kiện đáng chú ý              ║
╠═══════════════════════════════════════════════════════╣
║  Ca sáng mai khởi động: 06:00                         ║
║  Hệ thống sẵn sàng — chúc broker nghỉ ngơi tốt       ║
╚═══════════════════════════════════════════════════════╝
```

---

## Xử lý lỗi

| Tình huống | Hành động |
|---|---|
| `eod_summary_{date}.json` không có | Chạy lại `collect_eod_data.py` trước Bước 1 |
| Không tải được báo cáo CTCK | Ghi chú nguồn bị lỗi, bỏ qua, xử lý thủ công |
| Newsletter render lỗi template | Dùng `templates/backup/newsletter_base.html` |
| Broker quên duyệt newsletter | Nhắc nhở qua terminal — KHÔNG tự gửi |
| Watchlist.json bị corrupt | Khôi phục từ `data/backup/watchlist_{date-1}.json` |

---

## Tài nguyên liên quan

- Input từ ca EOD: `data/cache/eod_summary_{date}.json`
- Template newsletter: `templates/newsletter_base.html`
- Watchlist hiện tại: `data/watchlist.json`
- Danh sách KH: `data/customer_list.json`
- Output newsletter: `outputs/{date}/newsletter_{date}.html`
- Output tóm tắt CTCK: `outputs/{date}/research_summary_{date}.md`
- Output events: `data/cache/events_3days_{date}.json`
  → Đây là input cho `morning-prep` ngày mai — Bước 3
- Output KPI: `data/broker_kpi_{YYYY_MM}.json`
