# OCR đáng ngờ không tự thành trí nhớ truyện

2026-10-14. Source đã sửa và kiểm thử; **chưa promote frozen companion/Edge cá nhân**.

## Lỗi đã tái hiện

Crop `MN109-02:r000` có vài nét mờ nhưng OCR sinh text. Routing cũ (`unknown/translate`)
cho phép text này vào recent dialogue, tóm tắt và đề xuất thuật ngữ. Repro trước sửa
trả `story_memory_admitted: true`; sau sửa là `false`, vẫn `action: translate`.
Không coi việc thiếu nhãn gold là bằng chứng crop không có chữ.

## Thay đổi

- Hint pixel local có giới hạn: crop ≤96 px mỗi chiều/4.096 px², nền sáng phần lớn
  phẳng, ít nét tương phản mạnh, các cụm nhỏ rời nhau. Không dùng JA gold/model text
  để quyết định flag. Blank/reverse/dense/ngoài giới hạn không bị hint này kết luận.
- Kiểm tra thêm nét ở tương phản thấp: control chữ Nhật mờ từng làm test đỏ, nay qua.
  Ngưỡng là heuristic review, **không phải độ tin cậy đã hiệu chuẩn** hoặc classifier
  phân biệt nét tranh/chữ, không giải quyết việc nhận biết bảng chữ nào quan trọng.
- `visual_low_signal` + `scope.reason=visual_review/memory=false`: giữ nguồn và bản
  dịch; không tự thêm vào recent dialogue, summary job, glossary hoặc gợi ý tên.
- Không dựng mask/patch để xóa tranh ở vùng này. Renderer bỏ cả erasure metadata
  xung đột và patch đến muộn. Tap mở đối chiếu; mở ghi chú không phát sinh request.
- Sửa OCR vẫn dịch lại được nhưng không ngầm xác nhận bằng chứng ảnh hay cốt truyện.
  Override reader rõ ràng ở seam routing được giữ; chưa có flow xác nhận scope mới.
- Scope version v3 làm cache dịch v2 thành miss; OCR coverage vẫn được kiểm tra bằng
  ảnh hiện tại trong RAM. Không tự sửa/xóa fact lịch sử; ảnh không được lưu lại.

## Bằng chứng và giới hạn

| Kiểm tra | Kết quả |
|---|---|
| Full Python / TS | 694 qua + 1 skip symlink Windows / 31 qua; typecheck/build qua |
| Control nhỏ/mờ/reverse/dấu câu | Qua; không chứng minh mọi font/scan đều được phân biệt |
| Replay đủ nguồn riêng | 8 trang/132 vùng; 1 flag chưa có alignment; không skip vùng |
| Detector/OCR/cleanup chạy lại thật | Toàn bộ chữ, bbox, order, overlay, alignment và 62 patch giống baseline |
| Chất lượng toàn trang | Exact 34/78, CER chẩn đoán 29,18%; **không cải thiện từ thay đổi này** |
| Cổng dữ liệu perfect | **FAIL**; SL-01 sai kích thước, MN109-10 trùng, 0 nhãn Việt hợp lệ |
| Rendered QA | Edge headless riêng, 1280/760/390 px; warning, sửa OCR, raw art, late patch và retry qua |

Ảnh QA desktop/mobile đã xem, screenshot ngoài repo. Browser plugin không có nên
dùng Playwright sẵn có. Native/OCR/dịch được giả lập **trong UI QA**; phép rerun private
ở bảng trên dùng detector/OCR thật, không model dịch/cloud. Không có clean-background
gold, semantic-role gold hoặc chứng nhận chính xác Nhật–Việt từ các test này.

Lệnh tái lập (trong thư mục dự án, `.venv\Scripts\python.exe -X utf8 -B`):

```text
scripts/probe_art_text_replay.py --folder <nguồn riêng> --page MN109-02 --region r000 --assert-not-memory
scripts/probe_scope_pages.py --folder <nguồn riêng>
scripts/benchmark_pages.py --folder <nguồn riêng> --threads 4 --output artifacts/private-pages-20261014-v16-scope-v3.json
```

UI: `npm run test:ui`; regression: `pytest -q -p no:cacheprovider tests/python`.
Diagnostics source riêng ở `artifacts/`, không vào bundle. Fingerprint giữ nguyên
`445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`.

Bước tiếp: rà chữ/nhãn và các lỗi grouping/OCR còn lại; chấm bản dịch trên nguồn có
quyền, được phép gửi cloud. Không promote decoder/model hoặc quảng cáo real-time từ
các regression xanh. Chưa có số đo p95 overhead hay đối chứng semantic-role held-out.
