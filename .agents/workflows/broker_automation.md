---
description: Tự động hóa quy trình môi giới chứng khoán (Broker Automation)
---

# Hệ thống Tự động hóa Quy trình Môi giới Chứng khoán

> Dự án tự động hóa quy trình hàng ngày của chuyên gia môi giới tại sàn HOSE/HNX.
> Antigravity (Assistant) đóng vai trò **trợ lý phân tích** — tổng hợp thông tin, soạn thảo báo cáo,
> cảnh báo biến động. **Không** tự động gửi khuyến nghị hoặc đặt lệnh giao dịch.

---

## 1. Tổng quan dự án

**Mục tiêu:** Tiết kiệm 3–4 giờ/ngày cho broker bằng cách tự động hóa
các tác vụ lặp lại: thu thập dữ liệu, soạn báo cáo, theo dõi cảnh báo.

**Người dùng chính:** Chuyên gia môi giới chứng khoán (broker), làm việc
tại công ty chứng khoán, theo dõi sàn HOSE và HNX.

**Lịch vận hành hàng ngày:**

| Ca | Thời gian | Tác vụ chính | Skill tương ứng |
|---|---|---|---|
| Chuẩn bị sáng | 06:00 – 09:00 | Thu thập tin tức, phân tích cơ bản | `morning-prep` |
| Giao dịch | 09:00 – 15:00 | Monitor realtime, cảnh báo, tư vấn nhanh | `trading-hours` |
| Nghỉ trưa & Phân tích | 11:30 – 13:00 | Phân tích kỹ thuật, báo cáo VIP | `midday-analysis` |
| Tổng kết ngày | 15:00 – 18:00 | Báo cáo EOD, liên hệ khách hàng | `eod-report` |
| Sau giờ | 18:00 – 21:00 | Newsletter, chuẩn bị ngày mai | `after-hours` |

---

## 2. Nguồn dữ liệu

### Thị trường quốc tế
- **Yahoo Finance API** — Dow Jones, S&P 500, Nasdaq, giá dầu, vàng
- **Reuters RSS** — Tin tức tài chính quốc tế (lọc từ khóa: Fed, interest rate, inflation)
- **Tỷ giá:** api.exchangerate-api.com (USD/VND cập nhật mỗi giờ)

### Thị trường trong nước
- **CafeF API** — VN-Index, HNX-Index, VN30, top gainers/losers
- **VNDirect WebSocket** — Giá realtime trong giờ giao dịch (poll mỗi 30 giây)
- **24h.com.vn RSS** — Tin tức chứng khoán Việt Nam
- **SSI iBoard** — Dữ liệu khớp lệnh, dư mua/dư bán

### Cơ quan quản lý & doanh nghiệp
- **UBCKNN** (ssc.gov.vn) — Thông báo chính sách, quyết định xử phạt
- **HNX/HOSE** — BCTC doanh nghiệp niêm yết, lịch họp ĐHCĐ, ngày GDKHQ
- **Vietstock** — Lịch sự kiện doanh nghiệp (trả cổ tức, phát hành thêm)

### Cơ sở dữ liệu nội bộ
- **PostgreSQL** `broker_db` — Danh sách khách hàng, danh mục, lịch sử giao dịch
- **Redis** — Cache giá realtime, watchlist broker
- **File:** `data/watchlist.json` — Danh sách mã cổ phiếu đang theo dõi hàng ngày

---

## 3. Quy tắc bắt buộc (KHÔNG được vi phạm)

### Bảo mật & Tuân thủ pháp lý
- **KHÔNG** tự động gửi bất kỳ nội dung nào đến khách hàng — mọi output chờ broker duyệt
- **KHÔNG** đặt lệnh mua/bán hoặc kết nối API giao dịch
- Nội dung phân tích PHẢI có disclaimer: *"Thông tin chỉ mang tính tham khảo,
  không phải khuyến nghị đầu tư. Nhà đầu tư tự chịu trách nhiệm quyết định."*
- File chứa dữ liệu khách hàng (tên, danh mục, P&L) → lưu vào `outputs/private/`,
  **không** đưa vào newsletter hoặc báo cáo chung

### Định dạng dữ liệu chuẩn
- Mã cổ phiếu: **VIẾT HOA**, ví dụ: `VCB`, `BID`, `HPG`, `VHM`
- Ngày tháng: `YYYYMMDD` trong tên file, `DD/MM/YYYY` khi hiển thị
- Số liệu phần trăm: làm tròn 2 chữ số thập phân, ví dụ: `+1.23%`, `-0.87%`
- Đơn vị giá: nghìn đồng (VNĐ), ví dụ: `68.5` = 68,500 VNĐ/cổ phiếu
- Đơn vị khối lượng: nghìn cổ phiếu, ví dụ: `1,250K cp`

### Logging bắt buộc
- Mọi API call ghi vào `logs/api_{YYYYMMDD}.log` với format:
  `[HH:MM:SS] SOURCE | ENDPOINT | STATUS | response_time_ms`
- Mọi file output tạo ra ghi vào `logs/output_{YYYYMMDD}.log`
- Khi có lỗi API: retry tối đa 3 lần, chờ 5 giây giữa mỗi lần, rồi fallback

---

## 4. Cấu trúc thư mục

```
stock-broker-automation/
│
├── .agents/workflows/           ← Chứa file cấu hình workflow này cho Antigravity
│   └── broker_automation.md
│
├── skills/                      ← Hướng dẫn từng ca làm việc (Antigravity format)
│   ├── morning_prep/
...
```

---

## 5. Lệnh hay dùng

```bash
# Chạy theo ca
python run.py --session morning        # 6h00 — Ca sáng
python run.py --session trading        # 9h00 — Giờ giao dịch
python run.py --session midday         # 11h30 — Phân tích trưa
python run.py --session eod            # 15h00 — Tổng kết ngày
python run.py --session after-hours    # 18h00 — Sau giờ

# Tác vụ đơn lẻ
python run.py --task morning-pdf            # Chỉ tạo báo cáo sáng
python run.py --task analyze VCB BID        # Phân tích so sánh 2 mã
python run.py --task newsletter --preview   # Preview newsletter, chưa gửi
python run.py --task watchlist --update     # Cập nhật danh sách theo dõi

# Kiểm tra hệ thống
python run.py --check-apis          # Test tất cả API connection
python run.py --logs today          # Xem log hôm nay
python run.py --dry-run morning     # Chạy thử, không tạo file thật
```

---

## 6. Xử lý lỗi thường gặp

| Lỗi | Nguyên nhân | Xử lý |
|---|---|---|
| `CafeF API timeout` | Server quá tải giờ cao điểm | Dùng VNDirect làm fallback, ghi log |
| `VN-Index = None` | Ngoài giờ giao dịch | Lấy giá đóng cửa phiên gần nhất |
| `UBCKNN 403` | IP bị block tạm thời | Chờ 10 phút, retry; nếu vẫn lỗi → bỏ qua mục này |
| `Template not found` | File docx bị xóa nhầm | Copy lại từ `templates/backup/` |
| `DB connection failed` | PostgreSQL chưa khởi động | Chạy `docker-compose up -d postgres` |

---

## 7. Cấu hình môi trường

```bash
# File .env (KHÔNG commit lên Git)
YAHOO_FINANCE_API_KEY=your_key_here
VNDIRECT_API_KEY=your_key_here
CAFEF_API_KEY=your_key_here
DB_HOST=localhost
...
```

---

## 8. Ngữ cảnh quan trọng cho Antigravity (Assistant)

**Về thị trường chứng khoán Việt Nam:**
- Giờ giao dịch HOSE/HNX: 9h00–11h30 và 13h00–15h00 (nghỉ trưa 11h30–13h00)
- Biên độ dao động: HOSE ±7%, HNX ±10%, UpCOM ±15%
- Khớp lệnh định kỳ: 9h00–9h15 (ATO) và 14h30–15h00 (ATC)
- Thanh toán T+2: mua hôm nay, nhận cổ phiếu sau 2 ngày làm việc

**Về thuật ngữ dùng trong hệ thống:**
- "KH" = Khách hàng (nhà đầu tư)
- "BCTC" = Báo cáo tài chính
- "ĐHCĐ" = Đại hội cổ đông
- "GDKHQ" = Ngày giao dịch không hưởng quyền
- "ATO/ATC" = At The Open / At The Close (lệnh khớp định kỳ)
- "VIP" = Khách hàng có tài sản >500 triệu VNĐ tại công ty

**Mức độ ưu tiên khi có xung đột:**
1. Tuân thủ pháp lý (cao nhất)
2. Bảo mật dữ liệu khách hàng
3. Độ chính xác thông tin
4. Tốc độ xử lý

---

*Cập nhật lần cuối: 2026-03-26 | Phiên bản: 1.1 (Migrated for Antigravity)*
*Mọi thay đổi quy trình → cập nhật file này trước khi chạy hệ thống.*
