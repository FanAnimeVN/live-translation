# Benchmark riêng: chưa đạt cổng chất lượng

Cập nhật 2026-10-14. Chưa mở rộng dataset, chưa sửa gold gốc và chưa promote companion.

Nguồn đang dùng: `C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001`.
Fingerprint: `445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`.
Ảnh/crop/patch chỉ RAM; chi tiết OCR và báo cáo riêng ở `artifacts/`, không đi vào bundle.

## 1. Dữ liệu cần rà độc lập

- Có 10 ảnh, 81 nhãn Nhật, 3 nhãn Việt.
- `MN109-10` trùng byte ảnh `MN109-01`; không tính như mẫu độc lập.
- `SL-01` khai báo 1200×1600 nhưng ảnh thật 1654×1170. Không tự scale bbox hoặc lấy ảnh khác thay thế.
- Còn **8 trang / 78 crop / 0 nhãn Việt hợp lệ** sau audit cấu trúc. “Hợp lệ” ở đây chưa có nghĩa là bản chép Nhật đã được kiểm chứng.
- Đã thấy nhãn đáng ngờ khi đối chiếu nguồn: ví dụ `速く…` trong nhãn nhưng ảnh là `遠く…`; nhãn khác thiếu chữ hoặc khác ký tự. Cần người đọc Nhật rà bản sửa riêng có dấu vết; không lấy prediction của model làm gold.

## 2. Số đo hiện tại

OCR local manga-ocr 0.1.14, CPU 4 luồng, không cloud. CER được chuẩn hóa NFKC và bỏ khoảng trắng, không bỏ dấu câu để tăng điểm.

| Kiểm tra | Kết quả | Ý nghĩa |
|---|---|---|
| Crop theo bbox nhãn | **48/78 đúng hoàn toàn; CER 9,37%** | Chưa đạt; không gồm detector và dịch |
| Toàn trang, PP-OCRv5 mặc định + layout v12 | 131 vùng; 62/78 nhãn được gán prediction | Chỉ alignment chẩn đoán, không phải recall/precision chuẩn |
| Alignment toàn trang v12 | CER 29,82%; exact 42,31% | Gộp lỗi detector/gom vùng/OCR/nhãn; không phải điểm dịch |
| Toàn trang v16, cùng detector/OCR | 132 vùng; 62/78 alignment; CER 29,18%; exact 34/78 | Một overmerge được sửa; 7 trang khác giữ nguyên bbox/text/overlay/review |
| Bóng có nền phẳng được xác minh, v16/scope v3 | 8; 62 patch local khác | Số vùng được nhận, **không chứng minh redraw đúng** |
| Cổng `--assert-perfect` | **FAIL** | Audit còn lỗi và chưa đạt exact toàn bộ |

Layout v10 sửa lỗi lấy tổng diện tích nhiều nền rời nhau để gán quyền sở hữu cho một bóng. Test tối giản từng đỏ ở cả nền sáng/tối, hiện xanh; private rerun không tăng điểm OCR. Không gọi sửa an toàn này là cải thiện accuracy đã đo.

Layout v11 giữ các crop detector nhỏ khi một union trải quá xa; trước đó chúng bị bỏ cùng union quá lớn. Crop tách được đánh dấu cần review và không tự có quyền xóa tranh. Test grouping, OCR và native-to-renderer schema đã từng đỏ; hiện qua. Rerun đủ 8 trang vẫn có cùng số alignment, không tuyên bố tăng accuracy trên bộ này.

Layout v12 còn kiểm tra lân cận cột/dòng: nền liền nhau không đủ để nhập các cụm chữ xa nhau thành một thoại. Vùng tách giữ toàn bộ crop và cờ review, không dùng chung textBox/quyền xóa của cả nền. Regression từng đỏ trên cả nền sáng/tối, chữ dọc/ngang; các test an toàn cũ vẫn qua. Trên cùng 8 trang, CER giảm từ 36,63% xuống 29,82%, alignment tăng 53→62/78, exact tăng 31→33/78. Tuy nhiên tổng edit trên MN109-03 tăng 24→33, MN109-04 tăng 40→42; chưa giải quyết detector bỏ cột, nối sai câu hoặc nhãn thiếu/sai.

Đối chứng **chỉ thay resize detector lên 1280**, giữ weights/OCR/layout v12: 115 vùng, 61/78 alignment, CER 26,52%, exact 32/78, 6 bóng phẳng và 67 patch. CER thấp hơn nhưng coverage/exact giảm so với v12 mặc định; chưa đổi resize của companion. Một lượt không chứng minh latency percentile hay generalization. Không bỏ nhãn, thay gold hoặc gửi private text/ảnh tới cloud.

Báo cáo: `artifacts/private-ocr-20261014-current.json`, `artifacts/private-pages-20261014-v10.json`, `artifacts/private-pages-20261014-v11.json`, `artifacts/private-pages-20261014-v12.json`, `artifacts/private-pages-20261014-v12-pp1280.json`, `artifacts/private-gate-audit-20261014-v12.json`. Audit strict chạy lại vẫn FAIL và fingerprint không đổi. Phiếu hiện có bốn nhãn cần rà riêng: `artifacts/private-label-review-proposals-20261014.json`; **pending**, không được dùng để tính điểm.

Đối chứng recognizer **PP-OCRv5_mobile_rec native** cũng chưa thay default: full-page cùng detector/grouping v12 được 61/78 alignment, 8/78 exact và CER chẩn đoán 43,77%, kém hơn manga-ocr trên bộ này. Detect lại từng crop cho 3/78 exact, CER 51,65% và 35 crop không tìm được dòng; không dùng tuyến này để kết luận riêng accuracy recognizer. Bốn lượt crop không cache có text giống nhau; mẫu tự tạo detector+rec 6/6 exact vẫn không dự báo được chất lượng private. Xem [kết quả/phương pháp](ocr-comparator-results-20261014.md); artifact `artifacts/private-paddle-rec-pages-20261014.json`, `artifacts/private-paddle-rec-20261014.json`. Ảnh chỉ RAM, không cloud, fingerprint nguồn không đổi.

**Thử nghiệm gom chữ mở v13/v14 bị từ chối làm mặc định.** v13 sửa hai cột bị đọc lặp nhưng gộp lời giới thiệu, tiêu đề lớn và chú thích nhỏ: 57/78 alignment, CER 32,91%, 31/78 exact. Thu hẹp khoảng cách/thang chữ và không tìm viền qua pixel nằm trong detector overlap ở v14 cho 61/78 alignment, CER 29,71%, 33/78 exact; vẫn mất một alignment và có regression crop khác. Không chốt engine theo một câu sửa được hoặc CER thấp hơn rất ít. Code thử nghiệm giữ riêng qua `--experimental-open-text`, không phải cài đặt companion. v15 mặc định giữ grouping ổn định: 62/78 alignment, CER 29,82%, 33/78 exact, 131 vùng, 8 bóng phẳng/63 patch; toàn bộ text/bbox vùng giống v12. Cổng audit perfect vẫn FAIL; fingerprint nguồn không đổi. Artifact `artifacts/private-pages-20261014-v13.json`, `v14.json`, `v15.json` (cùng tiền tố). Chi tiết và các lỗi còn lại: [review gom vùng](ocr-grouping-review-20261014.md).

**v16 sửa overmerge viền cong, không mở rộng quyền xóa.** Numeric replay trước sửa: 5 cột → 1 crop, câu dài lẫn thêm “難しいかな”. Đường bao thật có điểm lõm ngoài sâu 25,69 px nằm gần cuối khối ngắn, trong khi khối kia tiếp tục xuống dưới. Veto mới tách 5 cột → 2 crop và giữ cờ `layout_fragment`; không tự gán speaker, cắt detector pixels hay chia erasure mask. Rerun thực: b04 6→0 edit; b05 raw OCR đúng nhãn nhưng containment 44,8% chưa đạt ngưỡng gán 50%, nên **không tự cộng b05 thành exact/alignment**. Không nới gate/gold/bbox để tăng điểm. 7 trang khác có toàn bộ bbox/text/overlay/review như v15; các nhãn còn lại không đổi prediction. Tổng exact tăng 33→34/78, CER 29,82%→29,18%; 8 bóng nền phẳng giữ nguyên, patch 63→62 vì fragment mới không được cleanup tự động. Artifact `artifacts/private-pages-20261014-v16.json`, gate `artifacts/private-gate-audit-20261014-v16.json`; fingerprint không đổi, perfect vẫn FAIL. Cờ thử nghiệm mở hiện kết hợp với nền v16 và mang version riêng; không lấy kết quả v14 lịch sử làm điểm của cấu hình mới.

## 3. Detector đối chứng, chưa tích hợp phát hành

Decoder repetition-policy được đối chứng riêng trên đủ 78 crop và pipeline 8 trang. Punctuation-only giảm 88→86 edit nhưng exact vẫn 48/78; bỏ chặn hoàn toàn chỉ còn 43/78. Các mẫu nói ngắt nhịp phát hiện lời thừa khi bỏ chặn lexical. Giảm length penalty xuống 1 mất dấu cảm xúc trong pipeline; mức 1,5 giữ alignment 62/78/exact 34/78 nhưng đổi hai vùng chưa có nhãn. Không coi aggregate là chứng minh mọi vùng không regress. Giữ OCR mặc định; [kết quả và lệnh](ocr-decoding-review-20261014.md). Thêm đề nghị rà `MN109-07:b07` theo ảnh nguồn, không thay gold/rescore hoặc mở rộng dataset.

Đối chứng preprocessing ngày 2026-10-14 trên **đủ 78 crop** cũng bị loại: bicubic 46/78 exact, CER 10,33%; Lanczos 44/78, CER 11,50%, so với mặc định 48/78, CER 9,37%. Crop dòng sửa ngoặc giả ở demo nhưng tăng 1 edit trên bộ riêng (CER 9,48%); tuyến chỉ retry `quote_balance` cũng regress. Không strip dấu câu, không thay runtime từ những phép thử này. Fingerprint/gold giữ nguyên. [Bằng chứng và lệnh tái lập](ocr-punctuation-review-20261014.md).

Đối chứng **Hayai Nova 512 patches, CPU FP32, processor PIL explicit**: 42/78 exact, 109 edit/939 ký tự, CER 11,61%; baseline manga-ocr 48/78, 88 edit, CER 9,37%. 10 crop giảm lỗi, 20 tăng, 48 ngang; demo 13/13 exact không đủ để promote. Giữ source/gold/fingerprint, 0 socket attempts trong guard Python; không cloud hoặc thay default. Processor khác recipe Fast của tác giả nên không khẳng định upstream parity; chưa chạy full-page Hayai. [Kết quả/phương pháp](hayai-comparator-results-20261014.md).

Giữ nguyên OCR và layout v9 trong phép so PP–CTD; v10 là lượt kiểm tra riêng sau đó.

| Detector | Vùng / nhãn được gán | CER / exact alignment | Detector warm/trang |
|---|---|---|---|
| PP-OCRv5 mobile, v9 | 113 / 53 | 36,63% / 39,74% | 1,05–1,39 s |
| CTD ONNX, tuyến lines | 74 / 56 | 26,62% / 50,00% | 8,41–9,23 s |
| CTD ONNX, tuyến blocks | 63 / 58 | 29,39% / 46,15% | 7,92–8,43 s |

CTD cải thiện một số alignment nhưng vẫn bỏ sót, chậm hơn nhiều trên CPU và chưa rõ quyền phân phối weights. Không đổi mặc định từ bảng này; đây không phải benchmark detector đầy đủ, cũng không phải upstream CTD parity. Xem [phương pháp/giấy phép](detector-primary-review-20261014.md).

## 4. Dàn chữ và dịch: cổng riêng

**Scope v3 cách ly bằng chứng thị giác yếu, không phải OCR mới.** Rerun detector/OCR/cleanup thật trên 8 trang có 132 vùng, 62/78 alignment, exact 34/78/CER 29,18% và 62 patch; so JSON từng vùng/trang, chữ/bbox/order/overlay/alignment/patch giống baseline v16. Một vùng không có alignment (`MN109-02:r000`) vẫn cho dịch nhưng không tự vào memory/glossary/tóm tắt và không tự xóa tranh. Không gọi nó là non-text đã chứng minh; crop mũi tên/chữ nhỏ `MN109-07:r011` không bị flag. Không sửa gold hay gửi cloud. Artifact `artifacts/private-pages-20261014-v16-scope-v3.json`, replay `artifacts/private-scope-review-20261014.json`; audit perfect chạy lại vẫn FAIL. [Chi tiết](visual-source-review-20261014.md).

Candidate aligned-open v17 được đối chứng đủ 8 trang, chưa promote: exact vẫn 34/78, CER chẩn đoán 28,97%; một vùng 5→0 edit nhưng có mất ký tự/dấu ở vùng khác. Rerun default sau candidate có 8/8 trang với toàn bộ region/alignment/patch giống baseline v16, nguồn không đổi. [Chi tiết](ocr-grouping-review-20261014.md#đối-chứng-cột-có-cùng-mốc-bắt-đầu--chưa-promote). MN109-06 b03 có thêm đề nghị rà `手ぶ`/`呼ぶ`, pending; không sửa gold hoặc rescore.

**Kiểm tra toàn vẹn OCR local-v3.** Batch trả thiếu/thừa hoặc sai kiểu trước đây bị `zip` cắt ngầm rồi đánh dấu toàn bộ detections đã xử lý. Regression pipeline từng đỏ; guard nay từ chối trước cache coverage/dịch, retry còn xử lý đủ các crop. Bumped engine name để không dùng cache có thể thiếu nguồn, không đổi weights/decoder/processor/grouping. Rerun thật `artifacts/private-pages-20261014-local-v3-contract.json`: đủ 8 trang, toàn bộ regions/alignment/transient patches giống baseline v2/v16/scope v3; exact 34/78, CER 29,18%, fingerprint/gold giữ nguyên. Không coi sửa contract là tăng độ chính xác.

**Ba phép biến đổi polygon crop bị từ chối làm mặc định.** Chỉ thay input OCR cho single-line regions khớp duy nhất với quad detector trên nền đủ phẳng; không đổi detector/grouping/bbox/order/output renderer, không chọn từng crop theo gold. Tất cả chạy đủ 8 trang với 132 regions, 62/78 alignment và 62 patch:

| Input OCR | Regions biến đổi /132 | Exact /78 | Edit /939 ký tự | CER chẩn đoán |
|---|---:|---:|---:|---:|
| Mặc định | — | 34 | 274 | 29,18% |
| Matte ngoài polygon (`mask`) | 72 | 33 | 273 | 29,07% |
| Perspective quad (`rectify`) | 70 | 34 | 271 | 28,86% |
| Perspective + halo nguồn 3 px (`rectify-halo`) | 70 | 34 | 283 | 30,14% |

Rectify sửa lỗi lặp hai cột ở MN109-08:b02 (5→0 edit), nhưng mất một dấu chấm trong khoảng ngắt ở MN109-05:b13 và dấu cảm xúc ở vùng khác. Halo nguồn không giải quyết an toàn: lỗi mục tiêu còn 3 edit và có vùng khác sinh thêm chữ. Mask làm giảm exact. Không promote, không strip/ghép dấu câu để che regression; gold đang pending vẫn không được sửa/rescore. Các lượt mask/rectify dùng local-v2, halo dùng local-v3 chỉ khác contract; rerun v3 mặc định giống v2 không biến khác biệt version thành cải thiện accuracy. Artifact `artifacts/private-pages-polygon-{mask,rectify,rectify-halo}-20261014.json`; harness `scripts/probe_ocr_polygons.py` tách khỏi companion. Không gửi cloud hay ghi ảnh/crop; chưa phải bằng chứng generalization hoặc p95.

- Một bóng thật được chọn thủ công đã qua geometry/font/renderer production: 365 pixel mực nguồn trong ROI kiểm tra → 0 còn lại, không đổi pixel ngoài halo và xem gốc khôi phục chính xác. Cuộn và viewport 390 px qua. Transport/bản dịch do QA cung cấp; không chứng minh OCR/dịch toàn trang.
- Source Edge → Native Messaging → OCR → DeepSeek → overlay đã qua trên **trang tự tạo**, không phải bộ riêng. Bốn bóng tích hợp nhưng còn dấu `「` OCR thêm ở hai câu.
- Harness chọn đúng một trang private theo ID, không thay mẫu bị loại, không lưu screenshot private. Sau reader xác nhận quyền và đồng ý text-only, đã chạy MN109-08 → DeepSeek V4.1 Flash: 10 regions/7 integrated nodes/3 fallback, ID và cuộn qua. **Toàn flow vẫn FAIL ở hash pixel xem gốc**, chưa qua mobile/cache cuối flow. Ảnh RAM đã xem còn cột dịch chồng nhau, OCR giả ellipsis/nhầm glyph và lỗi nghĩa; không coi completion hoặc số surface là chứng nhận chất lượng.
- Ba lần cùng trang dùng 9 request, reported cost USD 0,002304888; reservation cộng dồn USD 0,029367 ≤ USD 0,03. Không gửi ảnh hoặc metadata truyện ra mạng; không sửa source/gold. Máy thiếu RAM trống; chưa có warm/cache p95 hoặc chấm Việt độc lập. Các lần lỗi harness vẫn được tính phí, không bỏ khỏi báo cáo. [Trạng thái và ranh giới QA](portable-testing.md#cloud-trên-một-trang-riêng-vẫn-fail-không-promote).
- Không có clean-background/mask gold hay bản Việt đã chấm độc lập. Không thể chứng nhận “dịch hoàn hảo” từ 78 nhãn OCR.

Replay không model/API mới qua ID/chữ/cuộn/native/390 px/xem gốc chính xác. Regression RAF bị trì hoãn từng đỏ nay qua sau conceal đồng bộ; mask/PNG trả muộn không ló ra. Không suy ra nguyên nhân hash mismatch ở inference nặng trước. **Dàn chữ vẫn FAIL:** 4 cặp textBox giao nhau, ảnh RAM xác nhận chồng cột đầu MN109-08. Không đổi source/gold/weights/layout hay OCR lại; số đo 8 trang/78 crop giữ nguyên. [Bằng chứng và lệnh](renderer-visibility-review-20261014.md).

## 5. Thứ tự tiếp theo

1. Nhận đúng cặp ảnh/annotation `SL-01`; rà nhãn/bbox Nhật và thêm bản Việt có người chấm. Giữ nguyên nguồn, lưu bản sửa và bằng chứng riêng.
2. Tách lỗi thiếu detector, gộp/sai thứ tự, OCR và nhãn. Kiểm tra glyph/viền/tranh riêng; không nới mask để che khuyết điểm.
3. Test cloud trên text được phép gửi, chấm mù nghĩa/xưng hô/thuật ngữ. Giữ speaker chưa biết, khóa reader và cutoff chống spoiler.
4. Chỉ khi chất lượng đạt mới mở tập lớn hơn, tối ưu latency/chi phí và promote bộ cài.

Lệnh cổng dữ liệu: `scripts/benchmark.py --folder <nguồn> --audit-only --assert-perfect`.
Lệnh OCR thật: bỏ `--audit-only`; toàn trang dùng `scripts/benchmark_pages.py`. Đối chứng resize có cờ `--detector-side-len 1280`, chỉ cho benchmark, không lưu vào cài đặt người đọc. Cổng crop không phải chứng chỉ chất lượng dịch.
