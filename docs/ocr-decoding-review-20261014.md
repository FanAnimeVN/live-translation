# OCR: giữ lời lặp và dấu ngắt nhịp — 2026-10-14

## Kết luận hiện tại

Chưa đổi OCR production (`manga-ocr/0.1.14-local-v2`). Bộ chặn lặp mặc định có thể làm sai lời lặp có chủ đích; bỏ nó hoàn toàn cũng không an toàn. Các phương án mới còn ở harness, chưa vào companion/Edge cá nhân. Không strip dấu câu hoặc tự sửa bản chép nguồn để che lỗi.

## Bằng chứng

Repro local đã chạy đỏ: `いやいやいやいや！` → `ぃやぃやいやいヤ！`, 3 edit. Bỏ `no_repeat_ngram_size=3` đọc đúng mẫu đó, nhưng phải kiểm tra cả bộ riêng:

| Chính sách | Exact / 78 crop | Edit / 939 ký tự | CER |
|---|---:|---:|---:|
| Mặc định: chặn mọi trigram lặp | 48 | 88 | 9,37% |
| Không chặn lặp | 43 | 103 | 10,97% |
| Chặn riêng trigram toàn dấu câu, toàn lịch sử | 48 | 86 | 9,16% |
| Chỉ chặn trong chuỗi dấu câu hiện tại | 48 | 86 | 9,16% |
| Toàn lịch sử + length penalty 1 | 48 | 86 | 9,16% |
| Toàn lịch sử + length penalty 1,5 | 48 | 86 | 9,16% |

Hai lời lặp được cải thiện với punctuation-only; không có crop tăng edit ở phép so này. Nhưng tập nhỏ không chứng minh an toàn: trên **19 control tự tạo**, bản toàn lịch sử và bản theo chuỗi đều thêm lời không có trong ảnh ở một câu có nhiều ngắt nhịp dài. Bản theo chuỗi giữ đúng `わ…た…し…？`; bản toàn lịch sử vẫn thiếu dấu. Ngoặc OCR tự thêm cũng chưa được giải quyết.

Giảm length penalty 2→1 loại phần lời thừa ở control, không thay config/weights trên đĩa. Tuy nhiên, trên **pipeline 8 trang thực**, một câu đang exact mất dấu `！`:

| Toàn trang cùng detector/layout v16 | Alignment / 78 | Exact / 78 | CER chẩn đoán | Vùng / patch |
|---|---:|---:|---:|---:|
| Production baseline | 62 | 34 | 29,18% | 132 / 62 |
| Punctuation-only, penalty 2 | 62 | 34 | 28,97% | 132 / 62 |
| Punctuation-only, penalty 1 | 62 | 33 | 29,07% | 132 / 62 |
| Punctuation-only, penalty 1,5 | 62 | 34 | 28,97% | 132 / 62 |

Mức 1,5 giữ dấu `！` của câu trên và loại phần lời thừa ở control; toàn bộ 78 crop có prediction giống punctuation-only/penalty 2. Nhưng toàn trang có **hai vùng ngoài annotation đổi prediction**, một vùng nằm trên nét tranh ở phần đầu trang, vùng kia trộn chú thích nhỏ/mũi tên; không thể chấm chúng là tốt lên từ aggregate. Các lỗi nhận tranh thành chữ và đọc chú thích sai vẫn tồn tại. Không dùng CER thấp hơn một ít để bỏ qua lời thừa/mất dấu cảm xúc hoặc các vùng không được gold bao phủ.

Grid có giới hạn 1 / 1,5 / 2, không chọn theo từng crop. Trên 19 control cùng nhau: mặc định 11 exact/23 edit; punctuation-only 14/14; theo chuỗi 15/14; penalty 1 và 1,5 đều 14/13. Mẫu ngoặc giả, chín dấu chấm và chuỗi ngắt nhịp dài vẫn có lỗi. **Chưa promote bất kỳ decoder nào**: exact tổng private chưa tăng, hiệu quả nhỏ và chưa có kiểm định giữ riêng/độc lập cho thay đổi này. Runtime/gold giữ nguyên; cổng perfect vẫn FAIL.

## Giới hạn và bảo vệ

- Gold Nhật chưa được rà độc lập; 0 nhãn Việt hợp lệ và không có clean-background gold. Alignment theo containment chỉ chẩn đoán, không phải detector recall/precision hoặc điểm dịch.
- Fingerprint nguồn giữ nguyên: `445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`. Thêm đề nghị rà `MN109-07:b07` riêng, trạng thái pending; không sửa hoặc rescore gold.
- Processor, gray conversion, weights, beam count và postprocessing cố định. Phép so penalty chỉ đổi một đối số sau khi đã cố định punctuation policy. Không chọn decoder riêng cho từng crop theo gold.
- Mask tensor kiểm tra nhiều beam/batch, clone-on-write, giữ dtype/device và mask có sẵn; blank không nạp model; sai số lượng output bị chặn. Không chứng minh accuracy bằng unit test.
- Full-page probe từ chối `--case`/`--assert-variant` thay vì âm thầm bỏ qua các cờ dành cho crop; lỗi đã đỏ trước sửa. Phạm vi của một benchmark không được mở rộng/thu hẹp âm thầm.
- Ảnh/crop/patch chỉ RAM, text diagnostics trong `artifacts/` gitignored; không có request cloud ở các phép thử này. Không nâng binary hoặc thay registry cá nhân.

Toàn Python sau chốt harness: **661 qua / 1 skip** (symlink Windows); TypeScript **30 qua**, typecheck/build qua. Đây là regression/kiểm tra build, không phải tỷ lệ dịch đúng. Source production vẫn prompt v20, OCR local-v2, layout v16; chưa có lượt inference mới trên Edge cá nhân.

## Tái lập

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/probe_ocr_decoding.py --case intentional-repeat --assert-variant 3 --output artifacts/ocr-decoding-minimal-review-20261014.json
.\.venv\Scripts\python.exe -X utf8 -B scripts/probe_ocr_decoding.py --punctuation-only --folder 'C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001' --output artifacts/private-ocr-decoding-punctuation-20261014.json
.\.venv\Scripts\python.exe -X utf8 -B scripts/probe_ocr_decoding.py --punctuation-only --pages --folder 'C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001' --output artifacts/private-pages-decoding-punctuation-20261014.json
.\.venv\Scripts\python.exe -X utf8 -B scripts/probe_ocr_decoding.py --length-penalty-one --pages --folder 'C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001' --output artifacts/private-pages-decoding-penalty-20261014.json
.\.venv\Scripts\python.exe -X utf8 -B scripts/probe_ocr_decoding.py --length-penalty-mid --pages --folder 'C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001' --output artifacts/private-pages-decoding-penalty-mid-20261014.json
```

Lệnh đầu **phải đỏ** với mặc định vì kiểm tra đúng defect. Các lệnh còn lại chỉ tạo đối chứng; không đổi runtime hoặc công nhận cổng perfect. Báo cáo riêng giữ nguyên các prediction sai, không chỉ lưu câu tốt.
