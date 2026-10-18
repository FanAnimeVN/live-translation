# Pre-OCR hardness routing — 2026-10-16

## Mục đích

`companion/manga_live/page_hardness.py` tạo một tín hiệu rẻ trước recognizer
để chọn giữa tuyến OCR nhanh và comparator chậm hơn. Tín hiệu chỉ đọc geometry
detector: số vùng, mật độ diện tích, vùng nhỏ, score thấp, overlap, cặp dòng có
khả năng là fragment, source members và hướng dọc/ngang.

Nó **không** là confidence/probability, semantic classifier hay text-scope
filter. Không dùng nó để bỏ vùng, suy ra SFX/irrelevant, ghi story memory hoặc
cho phép erasure. Một region khó vẫn phải được giữ và có thể đưa vào review.

## Cách dùng thử

`scripts/benchmark_pages.py` ghi `pre_ocr_hardness` ngay sau detector và trước
mọi OCR call. `scripts/probe_preocr_hardness_router.py` chọn cả trang candidate
chỉ dựa trên score của baseline; candidate chưa thể trở thành production
default. Không trộn region từ hai report trong cùng một trang.

Ví dụ sau khi có hai report cùng fingerprint:

```powershell
.venv\Scripts\python.exe scripts/probe_preocr_hardness_router.py `
  --baseline artifacts/private-pages-baseline-hardness.json `
  --candidate artifacts/private-pages-ctd-hardness.json `
  --min-hardness 50 `
  --output artifacts/private-hardness-router-50.json
```

Ngưỡng phải được chọn trên development set rồi khóa trước held-out; không dùng
gold trong runtime. Cần báo riêng coverage, exact/CER, miss/overmerge, p50/p95
latency và RAM. Nếu routing giảm lỗi bằng cách bỏ câu hoặc làm hỏng tranh thì
candidate bị loại dù CER trung bình đẹp hơn.

## Giới hạn hiện tại

- Score chưa calibrated và chưa chứng minh chọn đúng trang khó trên private set.
- Grouping/recognizer vẫn là nút thắt; hardness chỉ giúp đưa trang khó tới
  tuyến phù hợp sớm hơn.
- 78 Japanese labels chưa rà độc lập; chưa có Vietnamese gold hoặc clean
  background gold. Kết quả router không thể chứng minh 78/78 hay chất lượng dịch.
- Đây là candidate harness; chưa thay mặc định, chưa gọi cloud, chưa đụng Edge.

## Kết quả probe trên private development set

Fresh baseline giữ nguyên `35/78 exact`, `62/78 assigned`, CER `28,65%`.
Fresh CTD line/8-thread giữ `44/78 exact`, `63/78 assigned`, CER `16,72%`,
nhưng trang đầu bị CTD miss toàn bộ và p95 detector có cold-start lớn.

Routing theo score hiện **chưa thắng** routing review-count cũ: ngưỡng 0–20
chọn CTD cho mọi trang và chỉ đạt `44/78`; ngưỡng 30 đạt `38/78`, ngưỡng
50 trở lên quay về baseline `35/78`. Vì vậy tín hiệu này được giữ như instrumentation
và không được promote. Kết quả cho thấy cần feature/route cấp vùng tốt hơn,
hoặc recognizer thứ ba có bằng chứng, chứ không chỉ đổi ngưỡng trang.

PaddleOCR-VL-For-Manga crop comparator đã pin sẵn nhưng lượt chạy fail-closed
trước khi nạp trọng số vì free RAM dưới guard 7 GiB; không có inference/ảnh gửi
ra ngoài. Không hạ guard để lấy điểm tạm thời.

