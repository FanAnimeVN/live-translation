# Hayai Nova: demo tốt, chưa thay manga-ocr

Đo 2026-10-14, CPU 4 luồng, FP32, batch 1, 512 patches. **Không thay OCR/prompt/layout production, không promote companion.** Không gọi API; ảnh/crop chỉ RAM, báo cáo text nằm trong `artifacts/` gitignored.

## Kết quả quyết định

| Tuyến crop cấp sẵn | Exact | Edit / ký tự | CER |
|---|---:|---:|---:|
| Manga-ocr mặc định, private | 48/78 | 88/939 | 9,37% |
| Hayai Nova comparator, private | 42/78 | 109/939 | 11,61% |
| Hayai, 13 mẫu tự tạo | 13/13 | 0/135 | 0% |

So từng crop private, Hayai giảm lỗi ở 10 crop, tăng ở 20, ngang điểm ở 48. Không dùng đáp án để chọn engine từng crop hoặc lọc bỏ crop khó. Kết quả trên mẫu tự tạo không dự báo được bộ manga thật: Hayai sửa được hai ngoặc giả, giữ ngoặc thật/ngoặc xuyên nhiều vùng và nhịp `わ…た…し…？` của demo, nhưng điểm private tổng thể kém hơn.

Fingerprint nguồn vẫn `445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`. Vẫn 8 trang/78 crop hợp lệ cấu trúc, **0 gold Việt dùng được**; nhãn Nhật còn cần rà độc lập. Không sửa ảnh/gold, không gọi kết quả OCR là điểm chất lượng dịch. Cổng perfect vẫn chưa đạt.

Một lượt private: load 13,29 s; p50 crop 1,69 s, p95 crop 2,19 s; peak working set process khoảng 1.202 MiB. Process gồm imports/model và ảnh RAM, **không có page detector**. Đây là phân bố một lượt trên crop cấp sẵn, không latency extension, không đo RAM máy thực hay p95 nhiều phiên. 0 lần thử kết nối qua guard Python socket; không phải trace mạng toàn hệ thống.

## Tương thích đã xử lý, không chứng minh upstream parity

- Weights và 9 file đã pin/checksum; chỉ fetch rõ ràng mới online. Import đúng hai file Python đã đọc đầy đủ, từ đường dẫn local sau kiểm tra hash; không `trust_remote_code` hoặc tải code lúc inference. Xem [source audit](ocr-candidate-source-audit-20261014.md).
- Inject Google SigLIP2 config local; không tải Google base weights. Tokenizer dùng `PreTrainedTokenizerFast` rõ ràng để tránh metadata Transformers 5 chọn loader không có trong môi trường.
- Checkpoint có đúng hai tensor IDS training-only không được inference dùng. Chỉ cho phép đúng tên/shape/dtype; thiếu recognition weight hoặc tensor lạ vẫn fail. Không sửa checkpoint.
- Môi trường không có torchvision. Comparator dùng native **`Siglip2ImageProcessor` PIL**, thay vì Fast/torchvision trong recipe của tác giả. Không cài hoặc nâng dependency production; chưa chứng minh processor parity. Không dùng lượt này để kết luận mọi cấu hình Hayai đều kém hơn.
- Giữ raw quotes/newlines/gaps; metric chỉ NFKC + bỏ whitespace như baseline, không strip punctuation. Raw output vẫn phải được xem khi đánh giá biểu cảm; exact chuẩn hóa không chứng nhận bảo toàn mọi khoảng cách.

## Quyết định và tái lập

Giữ manga-ocr. Không chạy hai OCR cho tất cả crop, không dùng Hayai như bộ sửa dấu tự động và không đưa vào installer. Chưa chạy Hayai full-page: comparator crop hiện chưa đủ căn cứ thay mặc định; detector/layout/bố trí và bản dịch vẫn là các cổng riêng. Quyền phân phối/provenance dữ liệu chưa được source audit giải quyết đầy đủ.

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/benchmark_hayai_nova.py --authored --output artifacts/hayai-nova-authored-512-20261014.json
.\.venv\Scripts\python.exe -X utf8 -B scripts/benchmark_hayai_nova.py --folder <private-folder> --output artifacts/private-hayai-nova-crops-512-20261014.json
```

Test source: 539 Python qua, 1 skip; 29 TypeScript qua; typecheck/build qua. Riêng adapter/page seam: 26 test qua. Đây là điểm kiểm thử phần mềm, không số lượng bản dịch đã được chấm đúng. Thay đổi lượt này chỉ thuộc harness/diagnostics/docs, không có UI mới cần promote.
