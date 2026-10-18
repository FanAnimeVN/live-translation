# OCR đối chứng local — chưa thay engine mặc định

Đo ngày 2026-10-14 trên Windows 11, CPU AMD, 4 luồng; PaddleOCR 3.7.0 / Paddle 3.3.1 / PaddleX 3.7.2. **Giữ manga-ocr: OCR nhẹ thử thêm chưa tốt hơn trên manga thật.** Không sửa nhãn, không gửi ảnh/text private lên dịch vụ cloud, không thay đăng ký companion hay bundle.

## Kết quả quan trọng

| Tuyến | Kết quả | Giới hạn |
|---|---|---|
| Paddle rec, 6 mẫu tự tạo, cấp sẵn vùng dòng | 5/6 exact; CER 3,23% | Mẫu chữ dọc sai hai ký tự; không có detector |
| Paddle rec, cùng 6 mẫu, detector thật trong crop | 6/6 exact; CER 0% | Chỉ mẫu tự tạo; không chứng minh manga thật |
| Paddle rec, 78 crop private, detect lại từng crop | 3/78 exact; CER 51,65%; 35 crop không tìm thấy dòng | Bị ảnh hưởng mạnh bởi detection trong crop nhỏ; không phải điểm riêng recognizer |
| Paddle rec, detect cả trang + grouping v12 | 61/78 nhãn được gán; 8/78 exact; CER chẩn đoán 43,77% | 8 trang, 121 vùng có text; containment alignment, không phải recall chuẩn |
| Manga-ocr hiện tại, detect cả trang + grouping v12 | 62/78 nhãn được gán; 33/78 exact; CER chẩn đoán 29,82% | Cùng nguồn/detector/layout; vẫn chưa đạt cổng chất lượng |

Trên 78 crop, chạy một lượt đầu và ba lượt warm không cache: text không đổi giữa các lượt. p50 detector+rec/crop khoảng 266–280 ms, p95 891–908 ms; **bao gồm 35 crop không tìm được dòng**, nên không dùng các số này để quảng cáo tốc độ dịch hoặc tốc độ nhận dạng thành công. Tải recognizer gồm imports khoảng 17,42 s; peak working set của process đối chứng khoảng 670 MiB. Tuyến full-page có peak khoảng 784 MiB, tải 17,60 s, OCR warm khoảng 4,07–8,33 s/trang; chưa gồm dịch, cleanup, context, browser. Không phải số đo toàn extension hoặc p95 trang.

Mẫu không có ngoặc không còn ngoặc thừa với Paddle; mẫu có `「…」` vẫn giữ ngoặc thật. Tuy nhiên, chưa có bằng chứng đủ để dùng Paddle tự sửa dấu cho manga-ocr trên truyện thật. Không xóa dấu ngoặc toàn cục. Các thử nghiệm padding/canvas/beam trước đó trên manga-ocr cũng chưa sửa ổn định cả bốn câu mẫu; không promote transform nào.

## Phương pháp và quyết định

- Weights chính thức `PP-OCRv5_mobile_rec`, revision/checksum cố định; toàn bộ ba file tải về đã được kiểm tra bytes/hash. Không cập nhật Transformers, không chạy Python từ repo model. Xem [nghiên cứu nguồn chính thức](ocr-comparator-review-20261014.md).
- Dùng `TextRecognition` với engine `paddle_static`, CPU, batch 1; BGR và `CropByPolys` của PaddleX hiện cài. Perspective crop rồi xoay CCW khi h/w ≥1,5. Đọc dòng ngang từ trên xuống, cột dọc từ phải sang trái; mixed/furigana còn là giới hạn.
- Full-page chỉ detect một lần trên ảnh nguồn, giữ grouping production v12 và cap 64 vùng. Mỗi raw polygon được gán đúng một vùng bằng geometry, không nhìn đáp án để chọn crop/hướng/thứ tự. Không threshold bỏ text có score thấp; score CTC không phải xác suất đúng đã hiệu chuẩn. Dòng/vùng rỗng vẫn tạo lỗi trong alignment.
- Nguồn private vẫn cùng fingerprint, 8 trang/78 crop được audit cấu trúc; **0 bản Việt hợp lệ và nhãn Nhật chưa được rà độc lập**. Không biến score OCR thành chứng nhận bản dịch; xem [cổng dataset](private-ground-truth-audit.md).
- **Không thay mặc định, không tự chạy hai OCR cho mọi vùng, không đưa comparator vào installer.** Tiếp tục tách lỗi detector/reading order/recognizer và rà nhãn trước khi chọn ứng viên mạnh hơn. Hayai cần implementation local đã rà; không bật `trust_remote_code=True` để rút ngắn công việc.

## Tái lập và bằng chứng

Harness: `scripts/benchmark_paddle_rec.py`. Chỉ `--fetch-model` tải file; inference không gọi cloud. Ảnh/crop chỉ RAM, báo cáo text nằm ở `artifacts/` gitignored.

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/benchmark_paddle_rec.py --fetch-model
.\.venv\Scripts\python.exe -X utf8 -B scripts/benchmark_paddle_rec.py --authored --line-source authored-glyphs --output artifacts/paddle-rec-authored-glyphs-20261014.json
.\.venv\Scripts\python.exe -X utf8 -B scripts/benchmark_paddle_rec.py --authored --output artifacts/paddle-rec-authored-detected-20261014.json
.\.venv\Scripts\python.exe -X utf8 -B scripts/benchmark_paddle_rec.py --folder <private-folder> --repeats 4 --output artifacts/private-paddle-rec-20261014.json
.\.venv\Scripts\python.exe -X utf8 -B scripts/benchmark_paddle_rec.py --folder <private-folder> --full-pages --output artifacts/private-paddle-rec-pages-20261014.json
```

Sau thay đổi harness: **473 Python qua, 1 skip quyền symlink; 28 TypeScript qua; typecheck/build qua**. Có 19 regression mới về output/score, dấu thật, ordering, missing text và polygon không bị dùng hai lần. Đây là kiểm thử harness/các invariant phần mềm, không phải 473 bản dịch đạt chất lượng. Không có thay đổi UI/engine production cần promote từ thử nghiệm này.
