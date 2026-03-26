---
name: morning-prep
description: >
  Tự động hóa ca chuẩn bị buổi sáng (6h00–9h00) cho broker chứng khoán.
  Kích hoạt skill này khi broker nói "chạy ca sáng", "chuẩn bị buổi sáng",
  "báo cáo sáng", "tin tức sáng nay", hoặc khi thời gian hệ thống trong
  khoảng 05:30–09:00. Skill thu thập dữ liệu từ nhiều nguồn, tổng hợp
  thành báo cáo PDF và gửi tóm tắt nhanh lên terminal cho broker đọc
  trước khi thị trường mở cửa lúc 9h.
---

# Morning Prep Skill — Ca sáng 6h00–9h00

## Mục tiêu

Đến 8h45, broker có sẵn trên màn hình:
1. File `outputs/{date}/morning_{date}.pdf` — báo cáo đầy đủ để in hoặc gửi
2. Tóm tắt 10 dòng trên terminal — đọc trong 60 giây
3. Danh sách cổ phiếu cần chú ý hôm nay — dựa trên watchlist + tin tức đêm qua

---

## Quy trình thực hiện

Chạy tuần tự theo 5 bước. Nếu một bước bị lỗi API, ghi log và chạy tiếp
bước kế — **không dừng toàn bộ quy trình**.

---

### Bước 1 — Thu thập thị trường quốc tế (6h00–6h30)

**Script:** `scripts/fetch_global_markets.py`

Thu thập và lưu vào `data/cache/global_{date}.json`:

```
Chỉ số chứng khoán:
  - Dow Jones Industrial Average  (^DJI)
  - S&P 500                       (^GSPC)
  - Nasdaq Composite              (^IXIC)
  - VIX — chỉ số sợ hãi          (^VIX)

Hàng hóa:
  - Dầu thô Brent                 (BZ=F)
  - Vàng spot                     (GC=F)

Tiền tệ:
  - USD/VND                       (từ exchangerate-api.com)
  - DXY — chỉ số đồng USD        (DX-Y.NYB)
```

**Nhận định tự động:** Sau khi lấy đủ dữ liệu, Claude viết 2–3 câu nhận định
tổng thể theo template:

```
"Thị trường Mỹ phiên đêm qua [tăng/giảm/đi ngang], Dow Jones [±X.X%].
VIX ở mức [XX.X] — tâm lý nhà đầu tư [lạc quan/thận trọng/lo ngại].
Giá dầu [±X.X%], vàng [±X.X%] — [nhận định tác động ngắn đến VN]."
```

**Fallback nếu Yahoo Finance lỗi:** Thử lại sau 30 giây × 3 lần.
Nếu vẫn lỗi → dùng giá đóng cửa phiên trước từ cache, ghi chú "Dữ liệu
có thể chưa cập nhật" vào báo cáo.

---

### Bước 2 — Thị trường châu Á (6h30–7h00)

**Script:** `scripts/fetch_asia_markets.py`

Các thị trường cần lấy (theo thứ tự quan trọng với VN):

| Thị trường | Mã | Lý do quan trọng |
|---|---|---|
| Trung Quốc — Shanghai | 000001.SS | Ảnh hưởng lớn nhất đến VN |
| Hồng Kông — Hang Seng | ^HSI | Barometer FDI châu Á |
| Nhật Bản — Nikkei 225 | ^N225 | Tâm lý chung khu vực |
| Hàn Quốc — KOSPI | ^KS11 | Cùng nhóm emerging market |
| Thái Lan — SET | ^SET.BK | So sánh cùng Đông Nam Á |

**Lưu ý múi giờ:**
- Nhật/Hàn/Trung mở cửa lúc 7h–8h giờ VN → có thể chưa có dữ liệu phiên mới
- Nếu thị trường chưa mở: lấy kết quả đóng cửa hôm qua, ghi rõ "(đóng cửa hôm qua)"
- KHÔNG điền số 0 hoặc bỏ trống — luôn có chú thích rõ nguồn dữ liệu

**Phát hiện tín hiệu đáng chú ý:**
Nếu bất kỳ chỉ số nào thay đổi ≥ 1.5% so với phiên trước →
đánh dấu 🔴 (giảm) hoặc 🟢 (tăng) và viết thêm 1 câu giải thích
nguyên nhân (tìm từ Reuters/Bloomberg RSS).

---

### Bước 3 — Chính sách & sự kiện pháp lý (7h00–7h30)

**Script:** `scripts/scrape_regulatory.py`

**Nguồn 1 — UBCKNN** (ssc.gov.vn/ubcknn/tin-tuc):
- Crawl danh sách thông báo mới trong 24h qua
- Lọc các từ khóa quan trọng: "đình chỉ giao dịch", "phạt", "hủy niêm yết",
  "phát hành thêm", "mua lại cổ phiếu quỹ", "thay đổi lãnh đạo"
- Nếu có thông báo liên quan đến mã trong `data/watchlist.json` →
  đánh dấu ⚠️ ƯU TIÊN CAO, để lên đầu Section 2 của báo cáo

**Nguồn 2 — Sự kiện doanh nghiệp niêm yết:**
Lấy từ Vietstock calendar API, lọc trong 3 ngày tới:

```python
event_types_to_track = [
    "GDKHQ",          # Ngày giao dịch không hưởng quyền
    "tra_co_tuc",     # Trả cổ tức tiền mặt / cổ phiếu
    "hop_DHCD",       # Họp đại hội cổ đông
    "phat_hanh_them", # Phát hành cổ phiếu thêm / quyền mua
    "ket_qua_KD",     # Công bố KQKD quý
]
```

**Output Bước 3:** Danh sách tối đa 5 sự kiện quan trọng nhất,
mỗi sự kiện một dòng: `[Ngày] | [Mã CK] | [Loại sự kiện] | [Tóm tắt ngắn]`

---

### Bước 4 — Phân tích cơ bản cặp cổ phiếu (7h30–8h30)

**Script:** `scripts/fundamental_compare.py`

Mỗi ngày phân tích một cặp cổ phiếu cùng ngành.
Cặp hôm nay lấy từ `data/watchlist.json` → field `"daily_compare_pair"`.

**Ví dụ watchlist.json:**
```json
{
  "daily_compare_pair": ["VCB", "BID"],
  "sector": "Ngân hàng",
  "focus_today": "So sánh tăng trưởng tín dụng Q1"
}
```

**Bảng so sánh 8 chỉ số — bắt buộc có đủ:**

| Chỉ số | Ý nghĩa | Nguồn |
|---|---|---|
| P/E | Giá / Thu nhập | Vietstock API |
| P/B | Giá / Giá trị sổ sách | Vietstock API |
| ROE | Lợi nhuận / Vốn chủ | BCTC gần nhất |
| ROA | Lợi nhuận / Tổng tài sản | BCTC gần nhất |
| EPS (TTM) | Thu nhập mỗi cổ phiếu | BCTC gần nhất |
| Tăng trưởng DT | YoY % | BCTC gần nhất |
| Tỷ lệ nợ/vốn | Đòn bẩy tài chính | BCTC gần nhất |
| Thanh khoản TB | Khối lượng 20 phiên | CafeF API |

**Nhận định cuối Bước 4:**
Viết đoạn 3–5 câu so sánh 2 mã, KHÔNG đưa ra khuyến nghị mua/bán,
CHỈ nhận xét định lượng:

```
"Xét về định giá, [MÃ1] đang giao dịch tại P/E = X.X lần,
thấp hơn [MÃ2] (P/E = Y.Y lần) khoảng Z%. Về hiệu quả hoạt động,
ROE của [MÃ1] đạt A.A%, cao hơn mức B.B% của [MÃ2]...
[Nêu 1–2 điểm khác biệt nổi bật từ dữ liệu]."
```

---

### Bước 5 — Tổng hợp và xuất báo cáo PDF (8h30–8h45)

**Script:** `scripts/generate_morning_pdf.py`

Ghép kết quả 4 bước trên vào template, xuất PDF.

**Cấu trúc file PDF `morning_{date}.pdf`:**

```
┌─────────────────────────────────────────────┐
│  HEADER: Logo công ty | Ngày | "BÁO CÁO SÁNG" │
├─────────────────────────────────────────────┤
│  TRANG 1: TỔNG QUAN THỊ TRƯỜNG              │
│  ┌──────────────────┬──────────────────┐    │
│  │ Thị trường Mỹ    │ Thị trường châu Á │    │
│  │ (3 chỉ số + VIX) │ (5 thị trường)   │    │
│  └──────────────────┴──────────────────┘    │
│  Hàng hóa: Dầu | Vàng | USD/VND             │
│  Nhận định tổng quan (2–3 câu)              │
├─────────────────────────────────────────────┤
│  TRANG 2: TIN TỨC & SỰ KIỆN               │
│  • Top 5 tin quốc tế (mỗi tin ≤ 80 chữ)   │
│  • Sự kiện pháp lý trong 3 ngày tới        │
│  • ⚠️ Cảnh báo nếu có thông báo UBCKNN mới  │
├─────────────────────────────────────────────┤
│  TRANG 3: PHÂN TÍCH CƠ BẢN                │
│  So sánh [MÃ1] vs [MÃ2]                    │
│  Bảng 8 chỉ số + biểu đồ cột so sánh       │
│  Nhận định 3–5 câu                         │
├─────────────────────────────────────────────┤
│  FOOTER: "Dữ liệu chỉ mang tính tham khảo" │
│  Timestamp tạo báo cáo | Phiên bản script  │
└─────────────────────────────────────────────┘
```

**Template gốc:** `templates/morning_report.docx`
Sau khi điền dữ liệu → convert sang PDF bằng `docx2pdf`.

**Output cuối cùng:**
- `outputs/{date}/morning_{date}.pdf` — báo cáo đầy đủ
- `outputs/{date}/morning_{date}_summary.txt` — tóm tắt 10 dòng cho terminal

---

## Định dạng tóm tắt terminal (in ra sau khi xong)

```
╔══════════════════════════════════════════════════════╗
║  BÁO CÁO SÁNG — {DD/MM/YYYY}  |  Tạo lúc {HH:MM}   ║
╠══════════════════════════════════════════════════════╣
║  🌍 QUỐC TẾ                                          ║
║     Dow Jones  {±X.XX%}  |  S&P500  {±X.XX%}         ║
║     VIX {XX.X} ({nhận xét: thấp/trung bình/cao})    ║
║     Dầu Brent ${XX.X}  |  Vàng ${X,XXX}              ║
║     USD/VND: {XX,XXX}                                ║
╠══════════════════════════════════════════════════════╣
║  🌏 CHÂU Á                                           ║
║     Shanghai {±X.XX%}  |  Nikkei {±X.XX%}            ║
║     Hang Seng {±X.XX%} |  KOSPI  {±X.XX%}            ║
╠══════════════════════════════════════════════════════╣
║  ⚠️  ĐÁNG CHÚ Ý HÔM NAY                              ║
║     • {Sự kiện 1}                                    ║
║     • {Sự kiện 2}                                    ║
║     • {Sự kiện 3 nếu có}                             ║
╠══════════════════════════════════════════════════════╣
║  📊 PHÂN TÍCH: {MÃ1} vs {MÃ2}                       ║
║     {1 câu nhận định ngắn nhất từ bước 4}            ║
╠══════════════════════════════════════════════════════╣
║  📁 Báo cáo đầy đủ: outputs/{date}/morning_{date}.pdf ║
╚══════════════════════════════════════════════════════╝
```

---

## Xử lý lỗi & Fallback

| Tình huống | Hành động |
|---|---|
| API lỗi < 3 phút | Retry 3 lần, mỗi lần cách 30 giây |
| API lỗi > 3 phút | Dùng cache ngày hôm qua, ghi chú rõ trong báo cáo |
| Không tìm được cặp so sánh trong watchlist | Mặc định dùng VCB vs BID |
| File template bị hỏng | Dùng template backup tại `templates/backup/morning_report.docx` |
| Chạy sau 9h00 | Vẫn tạo báo cáo nhưng in cảnh báo: "⚠️ Báo cáo trễ — thị trường đã mở cửa" |
| Tất cả API đều lỗi | Tạo file PDF rỗng với thông báo lỗi, gửi alert đến broker qua terminal |

---

## Kiểm tra chất lượng trước khi lưu PDF

Trước khi gọi `generate_morning_pdf.py`, kiểm tra checklist sau:

- [ ] Tất cả 3 chỉ số Mỹ có giá trị (không phải None/N/A)
- [ ] Ít nhất 3/5 thị trường châu Á có dữ liệu
- [ ] Bảng so sánh cơ bản có đủ 8 chỉ số (thiếu chỉ số nào → ghi "Chưa có dữ liệu")
- [ ] Footer có disclaimer pháp lý
- [ ] Timestamp tạo báo cáo được ghi đúng

Nếu thiếu dữ liệu > 30% → in cảnh báo trên terminal,
vẫn tạo PDF nhưng với các ô dữ liệu rõ ràng là "N/A — [lý do]".

---

## Tài nguyên liên quan

- Template Word: `templates/morning_report.docx`
- Watchlist hôm nay: `data/watchlist.json`
- Cache dữ liệu: `data/cache/`
- Log chi tiết: `logs/api_{date}.log`
- Script chính: `scripts/generate_morning_pdf.py`

Xem thêm ví dụ báo cáo mẫu tại: `templates/examples/morning_sample_20250101.pdf`
