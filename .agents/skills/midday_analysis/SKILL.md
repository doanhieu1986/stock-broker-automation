---
name: midday-analysis
description: >
  Phân tích kỹ thuật chuyên sâu và báo cáo VIP trong giờ nghỉ trưa
  (11h30–13h00). Kích hoạt khi broker nói "phân tích giữa phiên",
  "báo cáo VIP", "phân tích sâu [MÃ]", "tóm tắt buổi sáng",
  "chuẩn bị phiên chiều", hoặc khi thời gian hệ thống trong khoảng
  11h25–13h00. Tận dụng giờ nghỉ để làm phân tích chuyên sâu hơn
  on-demand 30 giây của ca giao dịch — xuất PDF cho KH VIP và
  chuẩn bị kịch bản cho phiên chiều.
---

# Midday Analysis Skill — Nghỉ trưa & Phân tích 11h30–13h00

## Mục tiêu

Giờ nghỉ trưa là thời gian duy nhất trong ngày không có áp lực realtime.
Đến 13h00 broker có sẵn:

1. Báo cáo phân tích kỹ thuật sâu (≥ 10 chỉ báo) cho mã VIP request
2. File PDF cá nhân hóa cho từng KH VIP — chờ broker duyệt gửi
3. Tổng kết phiên sáng dạng JSON — input cho ca EOD
4. Watchlist và kịch bản 2 chiều cho phiên chiều 13h–15h

---

## Quy trình thực hiện

Ưu tiên Bước 1 & 2 vì có deadline cứng 12h30.
Bước 3 & 4 chạy song song sau khi Bước 2 hoàn thành.

---

### Bước 1 — Phân tích kỹ thuật chuyên sâu (11h30–12h15)

**Script:** `scripts/technical_deep.py`

Khác với phân tích on-demand 30 giây ở ca giao dịch, bước này
dùng dữ liệu lịch sử 60–120 phiên và tính đủ bộ chỉ báo.

#### 1.1 Xác định mã cần phân tích

Lấy từ 3 nguồn, theo thứ tự ưu tiên:

```
Nguồn 1:  KH VIP request trực tiếp trong sáng nay
Nguồn 2:  Mã bị cảnh báo đỏ phiên sáng
          → đọc outputs/{date}/alerts_{date}.json
Nguồn 3:  Mã có khối lượng đột biến buổi sáng
          → đọc logs/realtime_{date}.csv
```

Giới hạn: tối đa 3 mã trong 1 giờ nghỉ.
Nếu > 3 request → ưu tiên KH VIP, báo broker phần còn lại
chuyển sang ca after-hours.

#### 1.2 Bộ chỉ báo kỹ thuật đầy đủ

```python
def deep_analysis(ticker, lookback=120):
    df = fetch_ohlcv(ticker, days=lookback)
    return {
        # Xu hướng
        "ma20": moving_average(df, 20),
        "ma50": moving_average(df, 50),
        "ma200": moving_average(df, 200),
        "ema12": ema(df, 12),
        "ema26": ema(df, 26),
        # Động lượng
        "rsi14": rsi(df, 14),
        "macd": macd(df, 12, 26, 9),       # line, signal, histogram
        "stoch": stochastic(df, 14, 3),    # %K, %D
        # Biến động
        "bb": bollinger(df, 20, 2),        # upper, mid, lower, %B
        "atr14": atr(df, 14),
        # Khối lượng & dòng tiền
        "vol_avg20": vol_ma(df, 20),
        "vol_ratio": df[-1].volume / vol_ma(df, 20),
        "obv": on_balance_volume(df),
        # Vùng giá quan trọng
        "support_1": find_support(df, strength=2),
        "support_2": find_support(df, strength=3),
        "resistance_1": find_resistance(df, strength=2),
        "resistance_2": find_resistance(df, strength=3),
        "pivot": pivot_point(df),          # PP, R1, R2, S1, S2
        "fib": fibonacci_retracement(df, 60),
    }
```

#### 1.3 Khung nhận định chuẩn — 4 phần

```
XU HƯỚNG:    [Dài hạn] MA200 cho thấy... | [Ngắn hạn] MA20 vs MA50...

ĐỘNG LƯỢNG:  RSI {X} — [nhận xét vùng quá mua/bán/trung tính]
             MACD [hội tụ/phân kỳ/cắt lên/cắt xuống] đường signal
             Stochastic %K={X} %D={Y} — [nhận xét]

DÒNG TIỀN:   OBV [tăng/giảm/phân kỳ] — [nhận xét]
             KL hôm nay gấp {X} lần TB 20 phiên

VÙNG GIÁ:   Kháng cự: {R1} (+{%})  xa hơn: {R2} (+{%})
             Hỗ trợ:   {S1} (-{%})  xa hơn: {S2} (-{%})
             Fibonacci 61.8%: {giá} | Pivot: {PP}
```

**Quy tắc bắt buộc:** KHÔNG kết luận bằng "nên mua/bán/nắm giữ".
Kết thúc bằng dữ liệu khách quan — broker tự đánh giá.

#### 1.4 Output

```
outputs/{date}/deep_{TICKER}_{date}.json   ← dữ liệu thô
outputs/{date}/deep_{TICKER}_{date}.pdf    ← báo cáo có bảng chỉ báo
```

---

### Bước 2 — Báo cáo nhanh KH VIP (12h00–12h30)

**Script:** `scripts/generate_vip_brief.py`
**Deadline cứng: 12h30** — broker cần review trước khi phiên chiều mở.

#### 2.1 Cấu trúc VIP Brief (cá nhân hóa từng KH)

```
VIP Brief — {Tên KH} — {DD/MM/YYYY}
─────────────────────────────────────────────────────
Phần 1: Danh mục của bạn — phiên sáng
  P&L buổi sáng:  {±X triệu VNĐ}  ({±%} NAV)
  Mã tăng mạnh:   [liệt kê nếu có]
  Mã cần chú ý:   [mã giảm hoặc có cảnh báo sáng nay]

Phần 2: Phân tích mã đang nắm giữ
  [Kết quả Bước 1 nếu mã đó được phân tích sâu hôm nay]
  [Nếu không: tóm tắt on-demand từ ca giao dịch sáng]

Phần 3: Sự kiện ảnh hưởng danh mục (3 ngày tới)
  [Từ output scrape_regulatory.py ca sáng]

Phần 4: Điểm cần theo dõi phiên chiều
  [1–2 câu thuần dữ liệu kỹ thuật]

Footer bắt buộc:
  "Thông tin chỉ mang tính tham khảo, không phải khuyến nghị
   đầu tư. Nhà đầu tư tự chịu trách nhiệm quyết định của mình."
─────────────────────────────────────────────────────
```

#### 2.2 Quy trình — bắt buộc chờ broker duyệt

```
1. Tạo PDF → lưu outputs/{date}/private/vip_{id}_{date}.pdf
2. In terminal: "⏳ VIP brief sẵn sàng: {N} file tại outputs/private/"
3. ═══ DỪNG — chờ broker review ═══
4. Broker xác nhận: python run.py --task vip-send --confirm
5. Ghi log → KHÔNG tự động gửi dưới bất kỳ hình thức nào
```

**Bảo mật:**
- Chỉ lưu trong `outputs/{date}/private/` — không ra ngoài thư mục này
- Không mix dữ liệu nhiều KH vào 1 file dù chỉ 1 trường
- Không đưa P&L cá nhân vào bất kỳ báo cáo chung nào

---

### Bước 3 — Tổng kết phiên sáng (12h15–12h45)

**Script:** `scripts/summarize_morning_session.py`

Đọc `logs/realtime_{date}.csv` (9h00–11h30) và xuất:

```
TỔNG KẾT PHIÊN SÁNG — {DD/MM/YYYY}
════════════════════════════════════════════════
CHỈ SỐ        Mở cửa    Đóng 11h30    ±%     KL
VN-Index      {X}        {Y}           {±%}   {tỷ VNĐ}
HNX-Index     {X}        {Y}           {±%}
VN30          {X}        {Y}           {±%}

ĐỘ RỘNG      Tăng: {N}  |  Giảm: {M}  |  Đứng: {K}

WATCHLIST — TOP BIẾN ĐỘNG
  Tăng:   {MÃ1} +{%}  |  {MÃ2} +{%}  |  {MÃ3} +{%}
  Giảm:   {MÃ4} -{%}  |  {MÃ5} -{%}

CẢNH BÁO ĐÃ PHÁT:  {N} cảnh báo
  Chi tiết: outputs/{date}/alerts_{date}.json

NHẬN XÉT (2 câu — thuần dữ liệu):
  "Dòng tiền tập trung nhóm ngân hàng và thép.
   KL toàn sàn đạt 65% mức TB 20 phiên."
════════════════════════════════════════════════
```

Lưu: `data/cache/morning_summary_{date}.json`
→ Input bắt buộc cho ca EOD và After-hours.

---

### Bước 4 — Chuẩn bị phiên chiều (12h45–13h00)

**Script:** `scripts/prepare_afternoon.py`

#### 4.1 Cập nhật ngưỡng cảnh báo watchlist

```python
for ticker in watchlist:
    if morning_change[ticker] >= +2.0:
        alert_threshold[ticker] = 1.5   # hạ ngưỡng bắt đảo chiều
    if morning_change[ticker] <= -2.0:
        watch_support[ticker] = True    # bật chế độ theo dõi hỗ trợ
```

#### 4.2 Kịch bản 2 chiều cho broker tham khảo

```
KỊCH BẢN PHIÊN CHIỀU (13h00–15h00)
─────────────────────────────────────────────────
Tích cực:    [1 câu nếu VN-Index giữ trên MA20]
Thận trọng:  [1 câu nếu VN-Index không giữ hỗ trợ]

⚠ Kịch bản dựa trên kỹ thuật, không phải khuyến nghị.
─────────────────────────────────────────────────
```

#### 4.3 Bàn giao sang ca giao dịch chiều

```
╔══════════════════════════════════════════════════╗
║  CA NGHỈ TRƯA KẾT THÚC — Sẵn sàng phiên chiều  ║
╠══════════════════════════════════════════════════╣
║  Phân tích sâu:  {N} mã hoàn thành              ║
║  VIP Brief:      {M} file — chờ broker xác nhận ║
║  Watchlist:      Đã cập nhật ngưỡng cảnh báo    ║
╠══════════════════════════════════════════════════╣
║  trading-hours skill tự động tiếp quản 13h00    ║
╚══════════════════════════════════════════════════╝
```

---

## Xử lý lỗi

| Tình huống | Hành động |
|---|---|
| Thiếu dữ liệu lịch sử | Dùng 60 phiên thay 120, ghi chú trong báo cáo |
| KH VIP request > 3 mã | Phân tích 3 mã ưu tiên, báo broker phần còn lại |
| Deadline 12h30 không kịp | Ưu tiên Bước 2, chạy Bước 1 song song |
| `customer_list.json` lỗi | Báo broker ngay, KHÔNG tự tạo danh sách KH |

---

## Tài nguyên liên quan

- Input ca sáng: `outputs/{date}/morning_{date}.pdf`
- Input ca giao dịch: `logs/realtime_{date}.csv`, `outputs/{date}/alerts_{date}.json`
- Danh sách KH VIP: `data/customer_list.json` → field `"tier": "VIP"`
- Output phân tích sâu: `outputs/{date}/deep_{TICKER}_{date}.pdf`
- Output VIP brief: `outputs/{date}/private/vip_{customer_id}_{date}.pdf`
- Cache tổng kết sáng: `data/cache/morning_summary_{date}.json`
