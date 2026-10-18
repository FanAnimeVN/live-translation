# PaddleOCR-VL-For-Manga: adapter qua kiểm tra, chất lượng chưa đo

Cập nhật 2026-10-14. **Chưa thay manga-ocr, chưa nạp trọng số để OCR và chưa có điểm accuracy/latency của PaddleOCR-VL.** Đây không phải recognizer PP-OCRv5_mobile_rec đã thử trước đó.

## Đã xác minh

- Model revision `1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8`: 9 file dữ liệu local đã kiểm tra checksum; inference không tải hoặc thực thi Python của repo model.
- Transformers 5.0.0/Hub 1.3.0 nằm riêng trong `artifacts/comparator-runtime/paddle-vl-native5`; production vẫn 4.57.6/0.36.2. Wheel đã pin/hash; không đổi dependency hoặc đăng ký companion cá nhân.
- Checkpoint thực có **620 tensor BF16**, kiến trúc native META có **608**. Không thiếu/sai shape/trùng ánh xạ trọng số lõi. Đúng 12 tensor surplus khớp từng key, shape và BF16; đã rà source chứng minh chúng không được dùng trong luồng OCR ảnh này. Không áp dụng ignore theo regex chung.
- Giữ nguyên danh sách surplus trong báo cáo: `raw_to_native_shape_gate=false` vì hai inventory không giống hoàn toàn; `reviewed_image_ocr_inventory_gate=true` chỉ chứng minh ngoại lệ đã được kiểm chứng. Gate này chạy trước khi nạp giá trị trọng số, không thay cổng OCR perfect.
- **13 control thoại tự tạo + 8 control pixel biên/màu** qua processor. Prompt/tokenizer giữ cấu trúc đã pin; giữ mRoPE `[16,24,24]`. Tất cả 21 pixel check khớp công thức độc lập với sai số quan sát **0**, ngưỡng `1e-7`. Khai báo `channels_last` cho ảnh PIL RGB để tránh đoán nhầm trục ở ảnh cao 1–3 pixel.
- Guard Python ghi **0 socket attempts**; không gửi ảnh/text manga lên cloud. Ảnh control chỉ RAM. Không khẳng định đây là truy vết mạng toàn hệ thống.

Source/nhánh, token, pixel và wheel: [review adapter](paddle-vl-native-adapter-review-20261014.md). Đây là kiểm tra công thức với PIL/NumPy hiện tại, **không phải chạy legacy runtime để chứng minh parity, không phải forward model hay chất lượng manga**.

## RAM và điều kiện chạy OCR tiếp theo

Máy có 16.309.932.032 byte RAM vật lý (~15,2 GiB khả dụng hệ thống), nhưng chỉ còn khoảng 1,4–1,7 GiB trước các lượt nhẹ. Processor-only peak working set cuối ~555 MiB. FP32 native parameter storage riêng đã khoảng 3,37 GiB, chưa gồm framework, activations hay load transient; không dùng số processor này làm peak của OCR.

Giữ guard **ít nhất 7 GiB RAM trống trước load**. Đây là mức bảo vệ thận trọng, không bảo đảm hết OOM. Không đóng ứng dụng người dùng, không tự giảm precision/budget pixel để lấy kết quả đẹp. Chưa có process inference đang chạy hoặc benchmark cần chờ.

Khi đủ RAM: chạy 13 control authored với FP32/CPU/eager, greedy, batch 1, max 300 token, `use_cache=False` → kiểm tra load/quotes/truncation → chạy đúng 78 crop private không đổi gold → chỉ sau đó thử toàn trang cùng detector/layout. KV cache là biến thể riêng, chưa được chấp thuận mặc định.

## Tái lập

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/benchmark_paddle_vl.py --audit-checkpoint --output artifacts/paddle-vl-native-checkpoint-strict-20261014.json
.\.venv\Scripts\python.exe -X utf8 -B scripts/benchmark_paddle_vl.py --preflight --output artifacts/paddle-vl-native-pixel-preflight-20261014.json
.\.venv\Scripts\python.exe -X utf8 -B -m pytest -q -p no:cacheprovider tests/python/test_paddle_vl_comparator.py
```

Comparator: **78 test qua**, có các trường hợp từ chối missing core, collision, key gần giống, từng surplus bị thiếu/sai shape/dtype, pixel bị đổi kênh/thang/thứ tự và RAM thấp. Toàn bộ Python **618 qua/1 skip**; TypeScript **29 qua**, typecheck/build qua. Không đổi UI nên lượt này không dùng test browser cũ làm nghiệm thu mới.

Benchmark thật vẫn **48/78 exact, CER 9,37%** với manga-ocr trên crop gold; toàn trang v16 **34/78 exact, CER chẩn đoán 29,18%**. Cổng private **FAIL**; chưa có gold Việt đủ để chấm lỗi dịch ≤2%, chưa đạt nghiệm thu tốc độ/bộ cài. [Trạng thái dữ liệu](private-ground-truth-audit.md).

Đã chạy lại audit-only nguồn người dùng với `--assert-perfect`: vẫn 8 trang/78 crop đủ điều kiện, 0 nhãn Việt dùng được, lỗi kích thước SL-01 và ảnh trùng MN109-10 giữ nguyên; gate false. Fingerprint vẫn `445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`; không sửa gold. Artifact `artifacts/private-data-audit-paddle-preflight-20261014.json` là audit dữ liệu, không phải lượt OCR mới.
