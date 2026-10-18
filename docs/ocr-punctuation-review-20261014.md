# OCR thêm ngoặc — đã tái hiện, chưa sửa an toàn

Ngày 2026-10-14. **Không thay OCR/preprocessing/decoder của extension.** Không xóa dấu câu toàn cục, không gửi ảnh hoặc text private lên cloud, không sửa gold. Hai ứng viên mới bị loại sau đối chứng; thành công trên demo không được dùng để tự sửa manga thật.

## Bằng chứng và quyết định

- Replay crop detector thật trên trang tự tạo: 2/4 câu thêm `「`. Ca tối giản `r000` cũng tái hiện; `glyph_mask` vẫn lỗi. Lệnh đỏ: `scripts/probe_ocr_focus.py --region r000 --assert-strategy detector`.
- Output thô đã có `「`; hậu xử lý không thêm dấu này. Runtime thực dùng beam 4, length penalty 2, không sampling, no-repeat-ngram 3. Decoder config trong nhánh con không phải config generation toàn model. Việc cùng upstream cũng lỗi không chứng minh ảnh có ngoặc thật.
- Probe mới đo bước **ký tự nhìn thấy đầu tiên**, bỏ qua CLS bắt buộc: `「` là token có score cao nhất ở `r000`, dù ảnh tự tạo không có ngoặc. Điều này thu hẹp lỗi vào nhận dạng/giải mã với crop hiện tại; không chứng minh có thể sửa an toàn bằng cấm token ngoặc. Artifact: `artifacts/ocr-punctuation-controls-baseline-20261014.json` (13 controls, baseline 10/13 exact).
- Chỉ đổi `processor.resample`, giữ weights, crop, grayscale, generation và hậu xử lý: bilinear/bicubic/Lanczos cùng 7/10 exact trên nhóm kiểm soát ban đầu. Ngoặc thật, ngoặc mở/đóng riêng, chữ dọc và ảnh trống được giữ; mẫu nhịp điệu vẫn còn lỗi. **Không sửa được triệu chứng.**
- Crop riêng dòng ngang theo khoảng trắng pixel sửa được hai dấu giả trên demo (7→9/10 exact), nhưng **regress manga thật**. Không dùng số ngoặc ít hơn hoặc quote balance như chứng cứ rằng bản mới đúng hơn.

Lượt kiểm soát mở rộng 13 crop: baseline 10/13 exact, crop dòng 12/13; ngoặc thật/mở/đóng qua hai dòng đều giữ đúng. Mẫu nhịp `わ…た…し…？` vẫn sai dấu kéo dài. Đây không phải bằng chứng tổng quát hóa: trên private, cùng thuật toán đã regress.

| 78 crop private, cùng nhãn/ảnh | Exact | Edit / 939 ký tự | CER |
|---|---:|---:|---:|
| Mặc định bilinear | 48/78 | 88 | 9,37% |
| Bicubic | 46/78 | 97 | 10,33% |
| Lanczos | 44/78 | 108 | 11,50% |
| Crop dòng, hoặc chỉ retry vùng quote-balance | 48/78 | 89 | 9,48% |

Bicubic có 1 crop cải thiện nhưng 5 xấu đi; Lanczos có 1 cải thiện nhưng 8 xấu đi. Crop dòng chỉ áp dụng được vào 1/78 crop và tăng lỗi 3→4, kể cả tuyến chỉ retry quote-balance. Bộ này không có đủ crop ngang/ngoặc thật đa dòng để hiệu chuẩn bộ sửa tự động; **0 regression không phải điều đã đạt**.

Fingerprint nguồn không đổi: `445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`. Sau audit cấu trúc vẫn 8 trang/78 crop/0 bản Việt hợp lệ; có nhãn Nhật cần rà độc lập. Đây là đối chứng crop có sẵn bbox, không phải điểm detector, dịch hoặc latency toàn extension. Cổng perfect vẫn chưa đạt.

## Tái lập và bước tiếp theo

Harness chỉ diagnostic, không được companion import: `probe_ocr_resampling.py`, `probe_ocr_line_crops.py`. Thêm kiểm soát ngoặc thật qua hai dòng; các script không đọc gold để chọn transform. Cấu hình resample luôn được khôi phục, cả khi lỗi. Ảnh chỉ RAM; report text trong `artifacts/` gitignored.

- `scripts/probe_ocr_resampling.py --folder <nguồn> --output artifacts/private-ocr-resampling-20261014.json`
- `scripts/probe_ocr_line_crops.py --folder <nguồn> --output artifacts/private-ocr-line-crops-20261014.json`
- `scripts/probe_ocr_line_crops.py --output artifacts/ocr-line-crops-controls-20261014.json`

Giữ guard xưng hô v20 và geometry v16; chưa promote binary/host cá nhân. Lỗi ngoặc cần được giải quyết bằng recognizer/crop có bằng chứng mạnh hơn, không bằng prompt yêu cầu model dịch bỏ nguồn. Ưu tiên đối chứng recognizer manga mạnh hơn trên **cùng bộ nhỏ**, tách chất lượng glyph/kana/kanji khỏi punctuation và phân biệt lỗi gold. Mọi ứng viên mới phải giữ ngoặc thật/partial quote, nhịp thoại và blank controls; chỉ tích hợp sau khi có cải thiện trên manga thật và không tạo regression nghiêm trọng mới.

Sau bổ sung harness: **515 Python qua, 1 skip quyền symlink Windows; 29 TypeScript qua; typecheck/build qua**. 7 test mới chỉ khóa tính cô lập và geometry của thí nghiệm, không phải 7 ca dịch đạt chất lượng. Không thay production hoặc UI nên không chạy lại rendered/native cloud QA chỉ để tạo một kết quả xanh không liên quan. Perfect manga và các mục tiêu p95 vẫn chưa đạt.
