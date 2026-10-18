# Trạng thái chạy thử — beta riêng tư

Lượt mới 2026-10-16: [MVP cloud demo và số đo thực](mvp-cloud-demo-20261016.md).
Các bảng bên dưới là lịch sử, không ghi đè kết quả/giới hạn mới trong hướng dẫn đó.

Cập nhật 2026-10-14. **Source chạy xuyên suốt trên trang tự tạo; benchmark manga riêng chưa đạt.** Chưa promote frozen companion, chưa thay đăng ký Edge cá nhân và chưa nghiệm thu Windows sạch.

**Lượt mới nhất:** [báo cáo gọn và quyết định](quality-review-20261014-latest.md). Source scope hiện là v4, speaker binding `speaker-source-v1`/DB schema 4; dữ liệu cũ giữ cho reader xác nhận, không tự gán sang geometry mới. Các phần v3/v20 dưới đây ghi lại đối chứng lịch sử. Không lấy test xanh làm chứng nhận chất lượng manga.

## Kết quả hiện tại

| Kiểm tra | Kết quả / giới hạn |
|---|---|
| Python | 877 qua, 1 skip do quyền tạo symlink Windows; gồm source-binding/đảo ID/cutoff/migration gián đoạn, replay/race/context/xưng hô/OCR/gate, không phải điểm accuracy |
| TypeScript / typecheck / build | 42 test qua; Manifest V3 build thành công; source-binding review, comparator ID/dàn chữ và diagnostic va chạm |
| UI/options/art QA | Qua trên Edge headless riêng; 1280/760/390 px tùy harness; native/OCR/dịch giả lập |
| UI source binding mới | Save control sticky/hittable desktop/mobile, mở review không request, xác nhận unknown có revision; native/OCR/dịch giả lập |
| Source browser E2E cloud v20/v16 | Native Messaging → PP detector → manga-ocr → DeepSeek → bốn bóng integrated trên trang tự tạo; cuộn/mobile/stop/cache qua |
| Dàn chữ private | Một bóng chọn thủ công, geometry/font/renderer production; 365 pixel mực trong ROI → 0, không đổi ngoài halo, xem gốc chính xác; bản dịch do QA cung cấp |
| Bộ private đầy đủ | 8 trang/78 crop; OCR 48/78 exact, CER 9,37%; cổng perfect **FAIL** |
| OCR đối chứng native Paddle | Full-page cùng detector/layout: 8/78 exact, CER chẩn đoán 43,77%; không thay manga-ocr |
| OCR đối chứng Hayai Nova | PIL/FP32 local, crop private 42/78 exact, CER 11,61%; demo 13/13 không đủ; không thay manga-ocr |
| PaddleOCR-VL-For-Manga native5 | Checkpoint/processor preflight qua, 21 pixel check; chưa nạp trọng số/chưa OCR do thiếu RAM trống; không thay default |
| Cloud trên text private | Đã có reader xác nhận quyền/đồng ý text-only; MN109-08 dịch 10 vùng, ID/cuộn qua; pixel xem gốc còn FAIL, chất lượng chưa đạt |
| Replay private không model/API | Qua MV3/native/ID/cuộn/390 px/Alt+T/stop; RAF bị trì hoãn vẫn ẩn ngay và hash nguồn khớp; không chứng minh inference |
| Cổng dàn chữ private riêng | **FAIL**: 4 cặp textBox giao nhau, ảnh RAM thấy chữ chồng đầu trang; không promote |
| Comparator block mới trên private | 30/78 exact, alignment 50/78; PP + guide 33/78, alignment 59/78; cả hai chưa promote dù sửa hai câu đầu MN109-08 |
| Guide v2, 10 union crop fresh | 34/78 exact, alignment 62/78, CER 28,86%; 108 crop khác không đổi, không crash; còn regression mất ký tự, chưa promote |
| Replay candidate + cloud mới | MN109-08 0 box chồng, 10 toggle khớp pixel native-size; một request text-only 2,56 s / reported USD 0,0006591; vẫn có OCR sai và nhãn trắng rõ, không chứng nhận nghĩa/cleanup |
| Source Native Messaging không inference | Đối chiếu prompt v21/OCR/layout/scope/speaker-source-v1; điều hướng cài đặt desktop/mobile qua, engine vẫn chưa nạp; không cloud |
| Frozen inference/Edge cá nhân/Windows sạch | Chưa được xác nhận với source mới |

Runtime source: prompt `ja-vi-v22-directed-wait-no-stack`, OCR `manga-ocr/0.1.14-local-v3`, layout `balloon-mask-v16-outer-notch-veto`. v22 giữ san-variant/no-stack và bổ sung guard hẹp cho câu `待ってる` để không đảo người chờ/người được chờ; giữ mệnh đề sau, style natural và ngoại lệ reader. Bản v22 đã build/test, **chưa chạy native/browser inference hoặc đóng gói frozen**; các số đo E2E v20 bên dưới là lịch sử. Đổi phiên bản prompt làm mất hiệu lực cache dịch cũ, không cần xóa cache OCR/context.

v15 từng giữ hành vi gom vùng ổn định v12; v16 chỉ bổ sung merge veto từ điểm lõm sâu ở viền ngoài của vùng nền có giới hạn. Không dùng text/gold để cắt, không cắt xuyên giữa crop, không suy speaker hoặc cấp quyền xóa mới. Trên 8 trang, b04 ở MN109-07 tăng thành exact; vùng b05 cũng đọc đúng riêng nhưng chưa được alignment gán do bbox gold hẹp. 7 trang khác có toàn bộ bbox/text/overlay/review giống v15. CER chẩn đoán 29,18%, exact 34/78; chưa đạt cổng chất lượng. Thử nghiệm gom nền mở/guide v2 vẫn không bật mặc định. Đổi layout làm mất hiệu lực cache OCR/layout cũ. Handshake và browser QA đối chiếu đủ prompt/OCR/layout/scope thay vì chỉ app version; cùng `0.1.0` không chứng minh cùng binary/runtime.

OCR local-v3 chỉ thêm kiểm tra cấu trúc/số lượng output: batch thiếu/thừa, chuỗi thay danh sách hoặc mục không phải text phải báo `OCR_RESULT`, không bị `zip` nuốt mất crop rồi cache cả trang là hoàn tất. Retry tường minh xử lý lại các crop còn thiếu. Không đổi weights/decoder/processor hoặc hình học crop; version mới vô hiệu cache OCR có thể thiếu nguồn. Rerun thật đủ 8 trang có toàn bộ regions/alignment/62 patch giống v2, fingerprint không đổi: đây là sửa tính toàn vẹn dữ liệu, **không cải thiện accuracy**.

Lượt source `--direct-source --connect-only` mới nhất: URL/title đúng, UI không trắng/error overlay, console không lỗi, bấm Cài đặt → Thư viện qua ở 1280×900/390×844; đủ năm phiên bản runtime khớp source. Model không nạp và host QA đã gỡ, registry kiểm tra không còn. Playwright dùng vì Browser plugin không có. Bằng chứng: `C:\Users\Huy\AppData\Local\Temp\mangalive-real-browser-NTEeX4\evidence`. Lượt bị từ chối quyền registry trước đó không tính là pass; lượt này dùng quyền đúng scope cho QA. Không chạy OCR/dịch/overlay trong lượt này, không thay host cá nhân hay xác nhận frozen binary.

UI mới nhất URL `http://127.0.0.1:64139/chapter/1`, 1280×900/760×800/390×844, save bằng chuột thật tại điểm hittable. Ảnh authored desktop/mobile đã xem trong system-temp `mangalive-speaker-review-final-5699c0a058664720b28be335ab78fe84`; native/OCR/dịch giả lập. Replay private hiện tại 10 lần raw-scroll/xem gốc khớp pixel, nhưng gate 4 cặp lettering giao nhau vẫn FAIL: `artifacts/private-render-speaker-binding-20261014.json`. Không inference/cloud mới. [Chi tiết binding và migration](speaker-source-bindings.md).

### Cloud trên một trang riêng: vẫn FAIL, không promote

Reader đã xác nhận có quyền và đồng ý gửi **text** đến OpenRouter cho lượt tối đa USD 0,03; không gửi ảnh, không lấy metadata mạng. Chạy MN109-08, DeepSeek V4.1 Flash, source v20/local-v3/v16/scope-v3, profile Edge riêng. Ba lần chạy cùng trang cho 10 regions, 7 surface integrated/3 fallback. Đây không phải 3 mẫu độc lập hoặc chấm mù bản dịch.

- Lần 1 dừng do harness so text đã soft-wrap với text một dòng. Comparator mới chỉ cho một dấu cách giữa từ thành xuống dòng mềm; không strip dấu câu/khoảng ngắt/đánh vần. Check theo từng ID và aria-label, không sort text để che gắn nhầm các câu giống nhau. Renderer thêm `data-region-id` từ ID đã được kiểm tra.
- Lần 2 qua comparator nhưng dừng vì harness tìm class `bar` chính xác, bỏ lọt `bar compact`. Lookup theo class token đã sửa.
- Lần 3 qua ID/wording/unknown speaker/cuộn. **Hash ảnh khi Alt+T xem gốc chưa khớp**; chưa xác định do capture/viewport hay lỗi renderer. Không bỏ assertion, chưa qua mobile/cache/console-health cuối flow. Cần replay không API để phân biệt hai nguyên nhân trước khi chạy paid lại.
- Ảnh RAM lần 2 đã xem: cột Việt chồng nhau, mảng fallback còn rõ; nguồn yếu bị đọc thành ellipsis, OCR nhầm `牙` thành `先` làm sai nghĩa. Không gọi 7 “integrated” nodes là 7 vùng đã đạt chất lượng. Bản dịch còn có câu thiếu tự nhiên và chủ thể mơ hồ. Không sửa gold bằng output model.
- Cả 3 lượt: 9 request, tổng reported cost **USD 0,002304888**; reservation **USD 0,029367**, còn nằm dưới trần USD 0,03. Reservation lần sau trừ phần các lượt trước; không reset ngân sách sau lỗi harness. Không phải hóa đơn đã đối soát; dừng gọi API ở đây.
- Cold reader total lần lượt 36,64/64,02/71,32 s; riêng dịch 4,82/5,87/6,24 s, gồm 3 request mỗi trang. Không có warm/cache percentile. Máy khoảng 15.554 MiB RAM, chỉ 107 MiB trống ở một thời điểm và 524 MiB sau cleanup; không xác lập nguyên nhân chậm chỉ từ các quan sát này, không coi đây là benchmark Windows sạch.
- Ba host QA đã gỡ và registry xác minh không còn; không đổi host/profile cá nhân. Không lưu screenshot private trên đĩa. Payload ảnh RAM của lượt cuối bị giới hạn output công cụ nên không được coi là bằng chứng ảnh đã kiểm tra đầy đủ.

Bằng chứng text/metrics local: `C:\Users\Huy\AppData\Local\Temp\mangalive-real-browser-{irTlx9,ghiEnm,RiANe4}\evidence\result.json`. Không ship các report này hoặc dataset. Hướng tiếp theo là OCR/grouping/dàn chữ + replay xem gốc, không mở tập lớn hơn hoặc hứa real-time từ unit test xanh.

Scope source hiện là `text-scope-v3-weak-mark-review`, được báo qua `status.scopeVersion`. Crop nhỏ có vài nét yếu trên nền phẳng được **review**, không skip hoặc khẳng định là nét tranh. Vẫn cho dịch/sửa nhưng không tự vào recent dialogue, tóm tắt hay glossary; không tự xóa tranh. Source cache dịch cũ mất hiệu lực qua scope version, cache OCR vẫn dùng và kiểm tra lại ảnh RAM. Không tự xóa fact lịch sử, không có nút mới ngầm xác nhận memory. Rerun detector/OCR/cleanup thật: đủ 8 trang, 132 vùng; toàn bộ chữ/bbox/order/alignment/62 patch giống baseline v16, chỉ `MN109-02:r000` thêm review/memory=false. CER/exact không cải thiện. UI QA mới qua 1280/760/390 px, transport giả lập; đã xem ảnh desktop/mobile. Chưa promote frozen host hoặc xác nhận Edge cá nhân. [Phương pháp và giới hạn](visual-source-review-20261014.md).

Pilot cloud v20 riêng: hai nhóm thoại tự viết × DeepSeek V4.1 Flash/Qwen3.8 Flash, bốn request một lần, đều qua guard xưng hô; lời gọi đứng riêng là `nee-chan`/`onii-chan`, không thêm chị/anh. Thời gian request 0,94–2,64 s; reported cost tổng USD 0,001261094, reservation USD 0,03. Không gồm OCR/overlay, không percentile đáng tin cậy hoặc chấm mù chất lượng. Không gửi text/ảnh private. Báo cáo `artifacts/cloud-sibling-v20-20261014/cloud-benchmark.json`.

Đã thử recognizer native Paddle có pin/checksum, hoàn toàn local, không đổi production dependencies/defaults hoặc đăng ký Edge. Test tự tạo 6/6 exact không đủ: full-page private còn kém hơn manga-ocr. Chi tiết [kết quả đối chứng](ocr-comparator-results-20261014.md). Không tích hợp engine này hoặc bỏ dấu câu để lấy điểm đẹp; baseline và cổng private vẫn chưa đạt.

Đã tái hiện và đối chứng thêm lỗi OCR tự thêm ngoặc. Bicubic/Lanczos không sửa được demo và làm giảm chất lượng trên đủ 78 crop private; crop dòng sửa demo nhưng tăng lỗi trên một crop thật. Không đổi preprocessing/retry mặc định. [Báo cáo ngắn, có lệnh tái lập](ocr-punctuation-review-20261014.md). Runtime source vẫn v20/v16; build không đồng nghĩa promote native host hay chứng nhận manga hoàn hảo.

Hayai Nova đã tải/checksum và chạy local sau rà source, không thay dependency production. Processor PIL explicit khác recipe Fast/torchvision; hai tensor IDS training-only được allowlist đúng shape/dtype, missing recognition keys vẫn bị chặn. Demo 13/13 exact, nhưng đủ 78 crop private chỉ 42/78, CER 11,61% (baseline 48/78, 9,37%); 10 crop cải thiện/20 regress/48 ngang điểm. Không thay mặc định hoặc dùng làm retry dấu. Chưa chạy full-page Hayai, chưa chứng minh upstream parity hoặc quyền phân phối. [Kết quả và tái lập](hayai-comparator-results-20261014.md). Source/gold/fingerprint không đổi, không gửi private text/ảnh lên cloud.

Gom cột nền mở aligned-start v17 cũng chưa promote: đủ 8 trang/78 nhãn, alignment 62/78 và exact 34/78 không đổi, CER chẩn đoán 28,97% so 29,18%; một vùng hết 5 lỗi nhưng còn regression mất chữ/dấu. Một “regression” theo gold có thể do nhãn sai; đã lưu pending review riêng, không rescore. Runtime default vẫn v16; chỉ harness `--experimental-open-text` dùng version mới. [Chi tiết và lệnh](ocr-grouping-review-20261014.md#đối-chứng-cột-có-cùng-mốc-bắt-đầu--chưa-promote).

Decoder cũng chưa đổi mặc định: chặn mọi trigram làm sai lời lặp; bỏ chặn hoàn toàn làm giảm private exact 48→43/78. Chặn riêng dấu câu cho 48/78, CER 9,16% so 9,37%, nhưng có lời thừa ở control. Grid length penalty 1/1,5/2 được kiểm tra crop và toàn trang; 1 mất dấu cảm xúc ở câu đang exact, 1,5 vẫn có hai vùng ngoài annotation đổi prediction và chưa có held-out audit. Giữ OCR `local-v2`, không promote binary/Edge từ cải thiện nhỏ này. [Bằng chứng và tái lập](ocr-decoding-review-20261014.md).

PaddleOCR-VL-For-Manga có adapter native Transformers 5.0.0 riêng, không chạy model-repository Python và không đổi production dependencies. Audit header/META: 620 raw/608 native; đủ core, 12 surplus được rà theo từng key/shape/BF16 cho đúng nhánh OCR ảnh. Gate giữ raw surplus hiển thị, chặn ngoại lệ khác trước load. Processor có 13 control authored + 8 pixel/color/boundary control; sai số so công thức độc lập quan sát 0, không chứng minh legacy runtime/model parity. Máy chỉ còn ~1,4–1,7 GiB trước các lượt nhẹ; guard load cần ≥7 GiB trống, không đóng app hoặc tự giảm precision. **Chưa có inference/accuracy/latency Paddle VL**; các report này không thay cổng private FAIL. [Kết quả/lệnh và giới hạn](paddle-vl-comparator-preflight-20261014.md).

## Luồng QA và tốc độ thật đã quan sát

Luồng: localhost reader → bắt đầu dịch → OCR/dịch thật → overlay → cuộn/390 px → dừng → trang warm mới → cache revisit. Playwright dùng profile/host QA riêng vì **Browser plugin not available**, không điều khiển phiên Edge đang đọc của người dùng.

Lượt source mới nhất 2026-10-14, prompt v20/layout v16, DeepSeek V4.1 Flash qua OpenRouter, hai request đều qua Together:

| Lượt | Browser toàn luồng | Native | Ghi chú |
|---|---|---|---|
| Cold | 31,04 s | 30,36 s | Detector 20,05 s; OCR 8,69 s; cloud 1,52 s |
| Warm, page ID mới | 5,65 s | 5,08 s | Detector 1,41 s; OCR 2,43 s; cloud 1,23 s |
| Đọc lại cache | 585 ms | 4,27 ms | 0 token/request dịch mới; browser còn debounce/poll/render |

Đây là ba quan sát trên **một trang tự tạo bốn bóng**, không p50/p95 hay chứng nhận real-time manga. Cache quan sát chưa dưới 200 ms; first overlay warm native 5,08 s cũng chưa dưới ngưỡng 5 s. Không lấy một trang 4 bóng dưới 8 s làm bằng chứng đạt p95 trang 12 bóng: lượt trước từng warm 17,61 s/cloud 13,46 s, chưa xác lập nguyên nhân biến động. Tổng reported API cost của lượt mới USD 0,000805416, hai request; reservation thực USD 0,0070884 trong trần USD 0,03. Không phải số dư/billing đã đối soát. Cache local không gọi cloud mới; không suy prefix-cache hit từ chênh lệch chi phí khi chưa có token-cache evidence.

Bốn bóng dùng mask/font tích hợp, ảnh desktop/mobile đã xem. OCR vẫn thêm `「` ở hai câu và model giữ dấu nguồn đó; lời dịch còn cần chấm nghĩa. Không đoán chị/em nếu không có speaker/quan hệ xác nhận, và không tự sửa tên reader đã khóa.

Bằng chứng authored của lượt mới: `C:\Users\Huy\AppData\Local\Temp\mangalive-real-browser-j4RiCZ\evidence`; các lượt lịch sử `mangalive-real-browser-Agqnlf` và `mangalive-real-browser-aJ1m7l` vẫn không dùng làm kết quả phiên bản mới. Ảnh private QA chỉ RAM, không có screenshot private trên đĩa. UI QA riêng đã chạy lại ghi chú vùng tách ở 1280/760/390 px; transport vẫn giả lập ở harness đó, không thay E2E inference. Host QA ngẫu nhiên đã được gỡ và đã kiểm tra registry không còn; không thay host/profile Edge cá nhân.

### Kiểm tra rendered QA

| Cổng UI | Kết quả |
|---|---|
| URL/title đúng, màn hình không trắng | PASS |
| Không framework error overlay | PASS |
| Không console error liên quan | PASS |
| Desktop/mobile screenshot | Đã xem; còn dấu OCR dư được ghi nhận |
| Cuộn/resize và điều khiển | PASS; nested scroll/contain/cover thuộc harness UI giả lập |
| Sửa OCR/tên, xem gốc, retry/stale cancellation | PASS trong UI QA; không thay chấm chất lượng inference |

Lệnh chính: `npm run check`, `python -m pytest tests/python -q`, `npm run test:ui`, `test:options`, `test:art`, `node scripts/lettering-qa.mjs --real-crops`, `scripts/browser-pipeline-smoke.mjs --direct-source --cloud-test`.

## Ranh giới các bản chạy

- `dist/extension`: extension development, chưa store/bộ cài tự cập nhật.
- `dist/windows`: launcher development, còn cần source/.venv/models/runtime trong project.
- `dist/portable/MangaLiveHost`: bundle Python/dependencies/models/llama.cpp; phải giữ cả `_internal`, không copy riêng exe.
- Portable cũ **không mặc nhiên có v20/v16**; chưa rebuild/promote từ lượt QA này. Bản unsigned/checksum không phải chữ ký tin cậy hay chứng nhận sẵn sàng thương mại.
- Chạy test source không xác nhận bộ cài Windows sạch. QA tạo/gỡ đúng host ngẫu nhiên, không thay `vn.mangalive.companion` của người dùng.

Sau một build đã được nghiệm thu, người đọc Reload extension. Chuyển native host qua `Install companion.exe` là thay registry tài khoản hiện tại: chọn browser/ID đúng, không chạy nhiều bộ cài cùng lúc. Nếu Windows/antivirus chặn, tự kiểm tra cảnh báo; không tắt bảo vệ để chạy thử.

## Mặc định UX và phục hồi lỗi

- Local cleanup nền/chữ mặc định bật ở hồ sơ mới, giữ `false` đã lưu; không thêm token/credit. Vùng không chắc giữ art với nhãn có thể ẩn. Neural/cloud redraw chưa có; nếu thêm phải cảnh báo/xác nhận riêng.
- Lỗi foreground giữ trang, pause autoscan và có **Thử lại**; không cloud-loop, không tự đổi provider. Prefetch ≤2 ảnh đã tải, không đánh dấu đã đọc; lỗi prefetch không lặp vô hạn.
- `STALE_CONTEXT` có mã riêng qua native → background → content: gỡ chữ/erasure/patch cũ, giữ ảnh nguồn và nút retry. Sự kiện trả muộn và PNG decode đang chờ không dựng lại art; Blob URL được thu hồi. Không tự gọi cloud vì reader sửa context.
- Tác vụ giữ revision xuyên các nhóm thoại và cleanup/cache; chỉ đề xuất thuật ngữ của chính tác vụ được nâng revision. Kiểm tra/lưu page+cache là nguyên tử; không giữ khóa memory trong OCR/model/cleanup. Sửa speaker và invalidation cùng một transaction; dịch lại lấy speaker/context cùng snapshot. Reader edit không bị rollback cùng tác vụ lỗi thời.
- Chọn vùng ưu tiên hơn autoscan; tọa độ hết hiệu lực khi cuộn/resize trong lúc chờ. Đổi src/URL/chapter hủy kết quả cũ.
- Tên có **Đúng / Đổi / Để sau**, còn sửa được theo chapter; khóa reader và cutoff chống spoiler giữ nguyên.
- Quotes/ellipsis/nói lắp/đánh vần không bị strip toàn cục. Output framing lỗi được repair tối đa một lần, chỉ các ID lỗi. Quote OCR chưa khép và crop tách có ghi chú đối chiếu khi bấm.
- Cache OCR độc lập với bản dịch: retry mạng/consent/model không OCR lại phần đã xong. Cache gồm coverage, phiên bản layout/OCR/detector, identity/hash ảnh/selection; không lưu ảnh. Cache partial không giả làm cả trang.
- Cache bản dịch phụ thuộc context/glossary/model/prompt. Sửa nguồn hoặc context liên quan làm mất hiệu lực; không replay page cũ vào chapter mới. Tóm tắt tự động hiện tắt; mở thư viện không tải model nặng.

QA context 2026-10-14 đã tái hiện đỏ rồi sửa: cleanup/sự kiện cuối/cache-hit/multi-batch, commit page+cache lỗi và snapshot speaker bị trộn. OCR đã hoàn tất vẫn dùng lại sau `STALE_CONTEXT`; một thread reader sửa được khi cleanup đang chạy. Rendered QA toàn luồng qua trên Edge headless riêng ở 1280×900, 760×800, 390×844; URL `http://127.0.0.1:56065/chapter/1`, fixture tự tạo/native giả lập, server đã dừng. Ảnh trước/sau khôi phục và retry đã xem tại `C:\Users\Huy\AppData\Local\Temp\mangalive-context-final-d150dd428b4a422d83c70a60f9e9ecd9`. Các bbox/patch mocked chỉ chứng minh phục hồi UI, **không phải bằng chứng lettering/OCR manga đạt chuẩn**. Không gọi API, thay model hay promote host Edge/frozen. RAM trống đọc lại khoảng 1,21 GiB; vẫn không đủ guard 7 GiB cho Paddle VL FP32.

## Bài học runtime/đóng gói còn phải giữ

- Native stdin Windows chỉ một reader. Workaround PeekNamedPipe/ReadFile đã có test header/payload chia nhỏ, EOF/UTF-8/import worker; các thử nghiệm detach stdio/DLL chỉ diagnostic, không chứng minh một fix chung cho mọi Windows.
- Worker llama.cpp thuộc Windows Job Object riêng, host thoát thì child được quản lý kết thúc. Không gán ownership thì dừng worker mới; không kill process theo tên. Regression dùng child Python không thay thử inference thật.
- PaddleX có thể khởi tạo PDF reader ngay khi nhận ảnh RAM: frozen cần metadata thật pypdfium2/OpenCV/pyclipper/Shapely, không chỉ DLL. Frozen probe cũ không xác nhận bản mới sau mọi thay đổi.
- QA cloud lấy test key từ Windows Vault riêng, reserve chi phí trước mỗi initial/repair, không log key/prompt/ảnh. Cấu hình QA không phải BYOK đã lưu của extension cá nhân.
- Private browser harness yêu cầu folder/page rõ ràng, từ chối mẫu bị audit loại, không dùng mẫu thay thế và không lưu raster. Nó chưa qua inference private cloud; Node REPL cũng không khởi tạo được trong lượt này, nên dùng CLI/Playwright được cho phép.

## Replay xem gốc mới — chức năng qua, lettering còn FAIL

Đã thêm replay kiểm tra fingerprint/trang/kích thước/ID/chữ/bbox/thứ tự/review/ý nghĩa và topology scope. Scope hash theo profile khác nên so quyền/nhóm, không ép hai hash bằng nhau. Patches dựng lại từ pixel nguồn trong RAM; không chạy model/API hoặc giả lập cache hit. Entry QA riêng chặn warmup/retranslate/translate/summarize/metadata/provider; không đăng ký làm host cá nhân.

Replay nhẹ cả content-script và MV3/native qua exact restoration **trước** sửa, nên không khẳng định đã giải thích hash mismatch inference nặng. Regression độc lập: trì hoãn RAF rồi Alt+T còn 5 vùng dịch/3 erasure hiện. `content.ts` nay conceal đồng bộ; lớp mới bắt đầu ẩn, reveal chờ position/clip. Test từng đỏ nay qua, gồm late balloon/PNG và trả về bản dịch trước release RAF. Private hash initial/restored/stopped khớp hoàn toàn.

Native replay sau guard mới: `C:\Users\Huy\AppData\Local\Temp\mangalive-real-browser-5ReFG7\evidence\result.json`; handshake/runtime/ID/cuộn/mobile/stop/console/cleanup qua. Ảnh đã xem trong RAM, không ghi raster. `metrics.total_ms=1` là sentinel, **không phải** latency dịch. Host QA đã gỡ, không promote frozen/Edge cá nhân.

Cổng `--assert-no-lettering-overlap` **FAIL** với 4 cặp textBox giao nhau. Intersection báo rủi ro, không thay glyph/clean-background gold; ảnh xác nhận r000/r001 và r004/r005 chồng chữ. Không gộp source, nhỏ hóa font hoặc nới mask để làm cổng xanh. Lượt này **0 API**, ngân sách paid trước giữ nguyên. [Lệnh và giới hạn](renderer-visibility-review-20261014.md).

## Cổng nghiệm thu trước phát hành

1. Rà/chốt nhãn Nhật/bbox và bổ sung bản Việt giữ riêng; kiểm tra role/importance và glyph/protected-art riêng. [Bộ nhỏ còn fail](private-ground-truth-audit.md), [quy tắc lettering](lettering-spec.md).
2. Cloud trên nguồn được phép gửi + chấm người mù nghĩa/xưng hô/thuật ngữ; không dùng JSON đúng làm điểm dịch.
3. Frozen OCR/detector/LLM, popup activeTab thật, Edge cá nhân và Windows sạch; kiểm tra offline không network, worker lifetime/thiếu RAM/mất mạng.
4. Sau chất lượng: đo p50/p95 trang mới trên máy cố định, tối ưu warm/cache/prefetch. Không nạp OCR và nhiều LLM lớn để làm đẹp tốc độ.
5. Rà quyền code/weights/fonts/data/API, privacy, ký/cập nhật và pháp lý trước public/thu phí. Chưa kích hoạt thanh toán/subscription.

Không coi DOCX kế hoạch cũ trong `deliverables/` là báo cáo nghiệm thu hiện tại.
