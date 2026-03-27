---
name: trading-hours
description: >
  Hỗ trợ broker trong giờ giao dịch HOSE/HNX (9h00–15h00).
  Kích hoạt skill này khi broker nói "chạy ca giao dịch", "bật monitor",
  "theo dõi thị trường", "phân tích [MÃ CK]", "cảnh báo hôm nay",
  "thị trường đang thế nào", hoặc khi thời gian hệ thống trong khoảng
  08:45–15h10. Skill chạy 3 chế độ đồng thời: monitor nền liên tục,
  phân tích on-demand theo yêu cầu, và cập nhật vĩ mô định kỳ mỗi 2 tiếng.
---

# Trading Hours Skill — Giờ giao dịch 9h00–15h00

## Mục tiêu

Trong suốt giờ giao dịch, broker luôn có sẵn:
1. **Cảnh báo tức thì** khi cổ phiếu trong watchlist biến động bất thường
2. **Phân tích kỹ thuật nhanh** bất kỳ mã nào trong vòng 30 giây khi được hỏi
3. **Cập nhật vĩ mô** mỗi 2 tiếng — không bỏ lỡ tin tức quan trọng
4. **Log đầy đủ** mọi biến động trong ngày để dùng cho báo cáo EOD

---

## Ba chế độ hoạt động song song

```
┌─────────────────────────────────────────────────────────────┐
│  CHẾ ĐỘ 1         CHẾ ĐỘ 2              CHẾ ĐỘ 3           │
│  Monitor nền  →   On-demand analysis  →  Macro update       │
│  (liên tục)       (khi broker hỏi)       (mỗi 2 tiếng)      │
└─────────────────────────────────────────────────────────────┘
```

Ba chế độ chạy độc lập — chế độ 2 có thể kích hoạt bất cứ lúc nào
mà không làm gián đoạn chế độ 1 và 3.

---

## Chế độ 1 — Monitor nền (chạy liên tục 9h00–15h00)

**Script:** `scripts/price_monitor.py`

### 1.1 Khởi động phiên (8h55–9h00)

Trước khi thị trường mở, thực hiện:
- Load `data/watchlist.json` — danh sách mã cần theo dõi hôm nay
- Load `outputs/{date}/morning_{date}.pdf` — đọc lại điểm đáng chú ý từ ca sáng
- Kết nối VNDirect WebSocket / SSI iBoard API
- Kiểm tra kết nối: nếu lỗi → thử fallback CafeF API
- In ra terminal: `[08:55] Monitor khởi động — {N} mã trong watchlist`

### 1.2 Vòng lặp monitor (poll mỗi 30 giây)

```python
while market_is_open():
    prices = fetch_realtime_prices(watchlist)
    volume  = fetch_realtime_volume(watchlist)

    check_price_alert(prices)    # Xem mục 1.3
    check_volume_alert(volume)   # Xem mục 1.4
    check_index_alert()          # Xem mục 1.5

    log_to_csv(prices, volume)   # logs/realtime_{date}.csv
    sleep(30)
```

### 1.3 Cảnh báo giá (Price Alert)

**Script:** `scripts/alert_engine.py` — hàm `check_price_alert()`

| Mức cảnh báo | Điều kiện | Hành động |
|---|---|---|
| 🔴 Khẩn cấp | Cổ phiếu KH thay đổi ≥ ±3% trong 15 phút | In terminal + ghi `alerts_{date}.json` ngay |
| 🟡 Quan trọng | Cổ phiếu watchlist thay đổi ≥ ±2% trong 15 phút | In terminal + ghi log |
| 🟢 Thông tin | VN-Index thay đổi ≥ ±1% so với mở cửa | In terminal (không ghi file) |

**Format cảnh báo in ra terminal:**
```
[10:32] 🔴 CẢNH BÁO: HPG +2.87% (15 phút) | Giá: 27.5 | KL: 4,230K cp (+180% TB)
[10:47] 🟡 QUAN TÂM: VHM -2.10% (15 phút) | Giá: 42.1 | KL: 1,850K cp
[11:02] 🟢 VN-Index: 1,284.5 (+1.02% từ mở cửa) | KL toàn thị trường: 18,450 tỷ
```

**Quy tắc chống spam:**
- Cùng 1 mã: chờ tối thiểu 10 phút trước khi báo lại ở cùng mức cảnh báo
- Nếu giá đã về vùng bình thường: reset bộ đếm thời gian

### 1.4 Cảnh báo khối lượng (Volume Alert)

**Script:** `scripts/alert_engine.py` — hàm `check_volume_alert()`

Tính khối lượng trung bình 20 phiên gần nhất (`vol_avg_20`).
Nếu khối lượng tích lũy trong 30 phút hiện tại vượt ngưỡng:

```
> 150% vol_avg_20  → 🟡 Khối lượng tăng bất thường
> 250% vol_avg_20  → 🔴 Khối lượng đột biến — kiểm tra ngay
```

**Lưu ý đặc biệt:**
- Không cảnh báo khối lượng trong 15 phút đầu ATO (9h00–9h15) — giai đoạn
  khớp lệnh định kỳ, khối lượng tự nhiên cao hơn bình thường
- Không cảnh báo khối lượng trong 30 phút cuối ATC (14h30–15h00)
  vì lý do tương tự

### 1.5 Theo dõi chỉ số tổng hợp

Mỗi 5 phút, lấy và ghi log:

```
VN-Index    → % thay đổi so với đóng cửa hôm qua
HNX-Index   → % thay đổi so với đóng cửa hôm qua
VN30        → % thay đổi + danh sách mã kéo index mạnh nhất
Độ rộng TT  → Số mã tăng / Số mã giảm / Số mã đứng giá
```

Nếu VN-Index thay đổi ≥ ±1.5% so với đóng cửa hôm qua → cảnh báo 🔴
ngay lập tức, không chờ chu kỳ 30 giây.

---

## Chế độ 2 — On-demand Analysis (khi broker yêu cầu)

**Script:** `scripts/technical_quick.py`

Kích hoạt khi broker nhắn hoặc gõ lệnh phân tích một mã cụ thể.
Ví dụ: `"phân tích VHM"`, `"check HPG"`, `"xem BID"`, `"VCB thế nào"`

**Mục tiêu thời gian:** Trả kết quả trong vòng **30 giây**.

### 2.1 Dữ liệu cần lấy

```python
def quick_analysis(ticker: str) -> dict:
    return {
        # Giá realtime
        "price":        get_current_price(ticker),
        "change_pct":   get_change_vs_yesterday(ticker),
        "change_3d":    get_change_vs_3days(ticker),
        "volume_today": get_volume_today(ticker),
        "vol_vs_avg":   volume_today / vol_avg_20(ticker),

        # Kỹ thuật — tính từ 60 phiên gần nhất
        "ma20":   moving_average(ticker, 20),
        "ma50":   moving_average(ticker, 50),
        "rsi14":  rsi(ticker, 14),
        "bb_upper": bollinger_upper(ticker),
        "bb_lower": bollinger_lower(ticker),

        # Vùng giá quan trọng — tính từ 20 phiên
        "support":    find_support(ticker, lookback=20),
        "resistance": find_resistance(ticker, lookback=20),

        # Nền tảng cơ bản (từ cache — không fetch lại realtime)
        "pe":  get_cached_pe(ticker),
        "pb":  get_cached_pb(ticker),
        "roe": get_cached_roe(ticker),
    }
```

### 2.2 Format kết quả in ra terminal

```
══════════════════════════════════════════════════
  PHÂN TÍCH NHANH: VHM  |  {HH:MM} {DD/MM/YYYY}
══════════════════════════════════════════════════
  GIÁ HIỆN TẠI   42,100 VNĐ   (+1.20% hôm nay)
  3 phiên gần    -2.80%        KL: 1,850K cp (x1.4 TB)

  KỸ THUẬT
  ├ RSI(14)      58.3          → Trung tính, chưa quá mua
  ├ MA20         41,250        → Giá đang trên MA20 ✓
  ├ MA50         40,100        → Giá đang trên MA50 ✓
  └ Bollinger    40,800–43,600 → Giá ở giữa dải

  VÙNG GIÁ QUAN TRỌNG (20 phiên)
  ├ Kháng cự gần  43,500       (+3.3% so với hiện tại)
  └ Hỗ trợ gần    41,000       (-2.6% so với hiện tại)

  CƠ BẢN (cache)
  ├ P/E  14.2x   P/B  1.8x    ROE  13.5%

  NHẬN ĐỊNH (1 câu)
  → RSI trung tính, giá trên cả 2 đường MA, còn cách
    kháng cự 3.3% — chưa có tín hiệu rõ ràng.

  ⚠ Thông tin chỉ mang tính tham khảo, không phải
    khuyến nghị đầu tư.
══════════════════════════════════════════════════
```

### 2.3 Quy tắc viết nhận định 1 câu

Nhận định phải:
- Dựa **thuần túy vào số liệu** vừa tính được, không phán đoán chủ quan
- Nêu **tối đa 3 điểm** từ dữ liệu kỹ thuật
- **KHÔNG** dùng các từ: "nên mua", "nên bán", "tiềm năng", "hấp dẫn",
  "rủi ro cao", "cơ hội tốt" — đây là ngôn ngữ khuyến nghị đầu tư

**Ví dụ nhận định hợp lệ:**
```
→ RSI 58 chưa vào vùng quá mua, giá nằm trong dải Bollinger,
  khối lượng hôm nay gấp 1.4 lần trung bình.
```

**Ví dụ nhận định KHÔNG hợp lệ:**
```
→ Cổ phiếu đang có tín hiệu tích cực, nhà đầu tư có thể
  xem xét tích lũy ở vùng hỗ trợ. ← VI PHẠM QUY TẮC
```

### 2.4 Lưu kết quả phân tích

Mỗi lần phân tích on-demand → lưu vào:
```
outputs/{date}/analysis_{TICKER}_{HHMM}.json
```

Cuối ngày, tổng hợp tất cả file này vào báo cáo EOD (ca tổng kết).

---

## Chế độ 3 — Macro Update (mỗi 2 tiếng)

**Script:** `scripts/macro_update.py`

Chạy vào: **9h30**, **11h30** (trước nghỉ trưa), **13h30**, **15h00** (tổng kết)

### 3.1 Nội dung cập nhật

**Tin tức vĩ mô trong nước** (nguồn: VnExpress Kinh doanh RSS, CafeF RSS):
- Fetch 20 tin mới nhất kể từ lần cập nhật trước
- Lọc theo từ khóa: `["lãi suất", "tỷ giá", "FED", "NHNN", "GDP",
  "lạm phát", "xuất khẩu", "FDI", "trái phiếu", "room tín dụng"]`
- Tóm tắt tối đa 3 tin liên quan nhất, mỗi tin ≤ 2 câu

**Hàng hóa & ngoại tệ** (nguồn: Yahoo Finance):
- Giá dầu Brent — so với đầu phiên
- Giá vàng spot — so với đầu phiên
- USD/VND — so với đầu phiên

### 3.2 Format cập nhật in ra terminal

```
──────────────────────────────────────────────
  MACRO UPDATE  |  11:30  |  Cập nhật 2 tiếng
──────────────────────────────────────────────
  HÀNG HÓA & NGOẠI TỆ
  Dầu Brent  $82.4  (-0.8% từ đầu phiên)
  Vàng       $2,310 (+0.3% từ đầu phiên)
  USD/VND    25,150 (không đổi)

  TIN TỨC LIÊN QUAN (3 tin từ 9h30 đến 11h30)
  • NHNN giữ nguyên lãi suất điều hành, không điều chỉnh
    trong tháng 3. (VnExpress, 10:45)
  • Xuất khẩu Q1 tăng 8.2% YoY, nhóm điện tử dẫn đầu.
    (CafeF, 11:15)
  • [Không có tin mới đáng chú ý trong khung này]

  → Không có tác động vĩ mô đột biến đến thị trường.
──────────────────────────────────────────────
```

### 3.3 Cập nhật 13h30 — Tóm tắt buổi sáng

Cập nhật 13h30 có thêm phần **tóm tắt hiệu suất buổi sáng**
(9h00–11h30) trước khi phiên chiều bắt đầu:

```
  TÓM TẮT PHIÊN SÁNG (9h00–11h30)
  VN-Index   1,278.5  (+0.62%)   KL: 9,840 tỷ VNĐ
  Top tăng   HPG +2.9%, VIC +2.1%, MSN +1.8%
  Top giảm   VHM -2.1%, NVL -1.9%, PDR -1.5%
  Cảnh báo   2 cảnh báo đã phát (HPG 10:32, VHM 10:47)
```

---

## Kết thúc phiên (15h00)

Khi thị trường đóng cửa lúc 15h00:

1. Dừng vòng lặp monitor (chế độ 1)
2. Chạy `scripts/session_summary.py` — tổng hợp nhanh:
   - Tổng số cảnh báo đã phát trong ngày
   - Mã biến động mạnh nhất (top 3 tăng / top 3 giảm trong watchlist)
   - Tổng khối lượng giao dịch watchlist vs hôm qua
3. Lưu toàn bộ dữ liệu realtime vào `logs/realtime_{date}.csv`
4. In thông báo bàn giao sang ca tổng kết:

```
╔══════════════════════════════════════════════════╗
║  PHIÊN GIAO DỊCH KẾT THÚC — {DD/MM/YYYY} 15:00  ║
╠══════════════════════════════════════════════════╣
║  VN-Index  1,282.3  (+0.94%)  KL: 18,650 tỷ      ║
║  Cảnh báo đã phát: 4  (2🔴 khẩn cấp, 2🟡 QT)    ║
║  Phân tích on-demand: 3 mã  (VHM, HPG, BID)      ║
╠══════════════════════════════════════════════════╣
║  Chuyển sang ca tổng kết — EOD Report skill       ║
║  Dữ liệu: logs/realtime_20250326.csv              ║
║  Phân tích: outputs/20250326/analysis_*.json      ║
╚══════════════════════════════════════════════════╝
```

---

## Xử lý gián đoạn & lỗi

| Tình huống | Hành động |
|---|---|
| Mất kết nối VNDirect | Chuyển ngay sang CafeF API, ghi log, thông báo broker |
| Cả 2 API đều lỗi | Dừng monitor, thông báo broker, ghi log — KHÔNG im lặng |
| Broker hỏi mã ngoài watchlist | Vẫn phân tích bình thường (on-demand không giới hạn mã) |
| Thị trường nghỉ trưa 11h30–13h00 | Tạm dừng chế độ 1 & 2, chế độ 3 vẫn chạy macro update 11h30 |
| ATO/ATC (khớp lệnh định kỳ) | Giảm tần suất cảnh báo volume (xem mục 1.4) |
| Cổ phiếu bị tạm dừng giao dịch | Ghi nhận, thông báo broker ngay, bỏ khỏi monitor tạm thời |
| Quá nhiều cảnh báo (>10 trong 30 phút) | Nhóm cảnh báo lại thành 1 bản tóm tắt, tránh spam terminal |

---

## Quy tắc tuyệt đối trong giờ giao dịch

- **KHÔNG** tự động đặt, sửa, hoặc hủy lệnh mua/bán dưới bất kỳ hình thức nào
- **KHÔNG** gửi tin nhắn, email, hoặc thông báo trực tiếp đến khách hàng
- **KHÔNG** đưa ra khuyến nghị mua/bán dù broker yêu cầu — chỉ cung cấp số liệu
- Mọi phân tích kỹ thuật phải kèm disclaimer:
  *"Thông tin chỉ mang tính tham khảo, không phải khuyến nghị đầu tư."*

---

## Tài nguyên liên quan

- Watchlist hôm nay: `data/watchlist.json`
- Cache dữ liệu cơ bản: `data/cache/fundamentals_{date}.json`
- Log realtime: `logs/realtime_{date}.csv`
- Cảnh báo trong ngày: `outputs/{date}/alerts_{date}.json`
- Phân tích on-demand: `outputs/{date}/analysis_{TICKER}_{HHMM}.json`
- Dữ liệu bàn giao EOD: `data/cache/session_summary_{date}.json`
