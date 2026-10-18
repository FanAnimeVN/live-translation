# Bản kiểm tra mới nhất: đã sửa an toàn, chưa đạt chất lượng manga

## Checkpoint detector/recovery — 2026-10-16

Đã đo upstream threshold .4 và ép resize cạnh dài1600 trên đủ8 trang: CER giảm
nhưng exact lần lượt34/78 và33/78, đều có regression nên không đổi default35/78.
Comparator source-preserving recovery giữ toàn bộ vùng/anchor cũ, replay giảm
269→265 edit, không label regression nhưng exact vẫn35/78. Sáu proposal bổ sung
chỉ defer/review; xem ảnh RAM còn thấy một vùng nét lá cây bị OCR thành chữ ngoài
78 nhãn. **Không promote từ điểm tổng, không mở rộng/training hoặc dùng credit.**
Suite cuối1256 Python/1 skip,58 TS, typecheck/build qua; build extension không đổi,
frozen companion/Edge cá nhân chưa cập nhật trong lượt này.
[Thuật toán, dữ liệu từng ca và giới hạn](ocr-detector-recovery-20261016.md).

## Checkpoint mới — layout v20 trên manga thật, 2026-10-16

Đã sửa góc union không chứa chữ của các cột dài/ngắn; hai bóng kín từ nhãn
chuyển sang lettering nền trong suốt, giữ giọt mồ hôi và nét tranh ngoài vùng
chữ. Fresh đủ 8 trang vẫn 132 vùng, 35/78 exact, CER 28,65%; số bóng đủ điều
kiện integrated 8 → 10, không đổi nguồn OCR/ID/bbox/order/source-key.
Edge renderer hai bóng qua glyph ROI, cuộn và exact source restoration;
transport/bản Việt do QA cung cấp, không chứng nhận nghĩa. **Chưa đạt chuẩn
manga tổng thể, chưa cập nhật frozen companion cá nhân.**
[Thay đổi, kiểm thử và giới hạn](quality-upgrade-20261016.md).

## Checkpoint trước trong ngày 2026-10-16 — đối chứng OCR

Đã hoàn tất đối chứng Hayai 384 patches và tensor-resize-only 512 patches trên
đủ 78 crop private: lần lượt 43/78 và 42/78 exact, đều thấp hơn manga-ocr 48/78.
Không đổi engine/default/prompt/renderer hoặc đóng gói. Replay MN109-08 vẫn
**FAIL 3 cặp dàn chữ**; số cặp giảm từ 4 do dấu chấm review được defer, không
phải sửa chồng chữ. Cold/warm/cache cloud pilot và chi phí đã ghi tách khỏi
browser display latency. [Kết quả và giới hạn đầy đủ](hayai-resize-results-20261016.md).

Các checkpoint bên dưới giữ nguyên bằng chứng lịch sử và số test tại thời điểm
chạy, không được đọc như kết quả mới hoặc trạng thái đã phát hành.

2026-10-14. Làm tại `D:\Projects\Live translation`, không sửa Minecraft. Ảnh/crop/patch/screenshot private chỉ RAM.

## Cập nhật mới nhất — CSP và tính đúng của harness

- Ảnh Edge cá nhân xác nhận hai lỗi riêng: companion NOT_FOUND và CSP chặn evaluation ở `ui.js`. CSP được tái hiện đỏ ở cả sáu ca connection QA trước bản sửa; cấu hình Zod `jitless` trước schema đã làm cả sáu qua, không đổi CSP hoặc quyền extension. Build trên đĩa hiện là **`0.1.0-dev.d07a2886be4a`**. Host đã đăng ký lại đúng parent registry; Edge cá nhân cần restart/reload để xác minh cuối. [Bằng chứng và ranh giới](edge-native-discovery-primary-20261014.md).
- Typecheck/build, **51 TS test**, connection/options/content UI QA qua Edge độc lập. Kiểm thử renderer dùng mẫu tự tạo và transport giả lập, không chứng nhận manga thật. Toàn bộ Python mới nhất đạt **979 pass, 1 skip**.
- Đã chạy production detector → partition → manga-ocr thật trên đủ tám trang. Kết quả **35/78 exact, CER 28,65%**, 10 crop inference tách tại 5 seam, không label regression; b02 MN109-08 giảm 5→0 edit. Harness giữ độc lập text/polygon/score/nguồn và có guard review/memory. [Đối chiếu partition production](ocr-overlap-partition-20261014.md).
- Không gọi cloud, không tiêu credit; không đổi prompt v21, reader bindings, key/memory hoặc quyền dữ liệu. Cổng manga thật vẫn **FAIL**, gồm bốn cặp lettering giao nhau trên MN109-08. Chưa có điểm Việt gold/background gold hoặc p95 đọc truyện đạt mục tiêu.

Checkpoint trước đã sửa binding người nói và migration, kiểm thử UI, Native Messaging status source thật và renderer replay trên manga private. OCR 10 union crop guide v2 bên dưới thuộc lượt trước, không tính lại thành số đo mới. Source prompt v21 đã build và handshake thật; không coi test source/Edge riêng là xác minh frozen companion trong Edge cá nhân.

## Quyết định mới nhất

Giữ PP-OCRv5 + manga-ocr làm baseline. Detector khối chữ ogkalu sửa đúng hai câu đầu MN109-08 nhưng bỏ sót/đổi vùng ở trang khác; thử dùng nó chỉ để hỗ trợ gom PP cũng còn regression. **Cả hai chưa làm mặc định.** Không sửa gold hoặc hạ cổng “perfect”. [Nguồn/model và ranh giới giấy phép](detector-alternatives-20261014.md).

Candidate union guide v2 vẫn không được mặc định vì có regression. Partition seam trắng khác: giữ đủ 132 vùng nguồn, chỉ thay hộp inference; production replay đạt **35/78 exact, CER 28,65%** mà không tăng edit. Vùng mới vẫn review và không tự ghi memory. [Đối chiếu từng ca và guard](ocr-overlap-partition-20261014.md).

Trên Ryzen 7 7840H, 16 GB RAM, CPU 4 threads: model ONNX nhỏ đã pin revision/check SHA-256, 11.120.765 byte; ONNX Runtime 1.23.2. RGB 640², `orig_target_sizes=[[width,height]]`, ba output/class giữ riêng; ngưỡng 0,3 theo adapter tác giả. Không dùng bubble/text box làm mask xóa, không coi `text_free` là SFX/chữ vô nghĩa. Comparator không vào installer/runtime.

## Đã cải thiện

- Lựa chọn người nói/người nghe nay gắn source key + cutoff, không gắn ordinal `r000/r001`. Đảo reading order/reuse ID/thay ảnh không làm chuyển lock sang câu khác; binding sống qua cache hết hạn. Dữ liệu ordinal cũ giữ để reader xác nhận, không đoán anchor từ ảnh mới. [Quy tắc và giới hạn](speaker-source-bindings.md).
- Migration schema 3/4 rollback cả bảng, bản ghi và mốc phiên bản khi lỗi; đã tái hiện đỏ rồi kiểm thử khởi động lại xanh. Lời nhắc xác nhận dữ liệu cũ lấy lịch sử đúng cutoff, không bị lựa chọn chapter sau che mất. Chỉ thử lỗi trên DB tự tạo.
- Panel sửa xưng hô có footer sticky, nút Lưu/Đóng luôn bấm được ở 390 px. Mở panel không gọi dịch; xác nhận unknown vẫn đi qua revision hiện tại. Test nhấn chuột ở điểm hittable thật, không dùng click DOM để che lỗi clipping.
- Prompt/guard v21 thêm `姉さん → nee-san`, `兄さん → nii-san`; không ghép thêm title “chị/anh” trước lời gọi đã giữ tiếng Nhật. Giữ đại từ hợp lệ ở mệnh đề sau, style natural, nguồn quote và ngoại lệ reader khóa. Kiểm thử này chưa phải chấm chất lượng bằng model cloud mới.
- Harness guide lưu nguyên 136 raw record/class/score từ đối chứng detector; không biến `text_free` thành SFX/irrelevance. Replay phải cùng fingerprint/layout/OCR; 8 trang có output text/geometry/alignment giống lượt fresh. Replay bổ sung provenance không được tính là inference hoặc latency mới.
- Dấu “...” do OCR đọc từ nét tranh nay được đánh dấu cần đối chiếu khi crop rất nhỏ, nền sáng, nét nối ra mép và không có cụm chấm độc lập. Giữ nguyên OCR/bản dịch, không tự bỏ dấu câu, xóa tranh hoặc ghi thành sự kiện/thuật ngữ. Chữ thật, dấu chấm rõ, ngắt nhịp và ngoại lệ reader vẫn được giữ. Đây là heuristic review, không phải classifier đã hiệu chuẩn.
- Renderer từ chối cả mask/PNG đến muộn ở vùng này. Mở kiểm tra không gọi dịch trả phí; sửa OCR cũng không ngầm xác nhận bằng chứng ảnh.
- Policy `text-scope-v4-punctuation-support-review` làm cache dịch cũ mất hiệu lực, nhưng giữ namespace source-key v3 để không mất lựa chọn phân loại/ẩn chữ đã lưu. Không tự xóa fact lịch sử.
- Xem gốc loại cả lớp dàn chữ khỏi cây hiển thị ngay, kể cả RAF chậm. Khi trở lại dịch, chỉ hiện các lớp đã có tọa độ/clip hiện tại.

## Benchmark và giới hạn

| Đối chứng | Kết quả |
|---|---|
| OCR mặc định chạy lại thật | 8 trang/78 nhãn, 132 vùng; exact 34/78, CER chẩn đoán 29,18% |
| Gom cột chồng vùng v18, **thử nghiệm** | 131 vùng; exact 35/78, CER 28,65%; chỉ MN109-08:b02 giảm 5→0 lỗi |
| Tách crop inference tại seam trắng, **production có guard** | Vẫn 132 vùng nguồn; 10 crop fresh, 122 crop giữ nguyên; exact 35/78, CER 28,65%; chỉ r004 MN109-08 đổi text; 0 label regression |
| Đối chiếu từng crop | 7 trang không đổi; crop giống nhau giữ nguyên OCR; không thấy regression trên tập này |
| Policy review trên toàn bộ OCR đã ghi | 5 vùng cần kiểm tra; giữ nguyên chữ/bbox/order/alignment, không skip vùng |
| Detector khối chữ thay PP, **đối chứng thật** | 72 vùng; 50/78 nhãn có prediction được gán, exact 30/78, CER 29,07%; baseline là 62/78, 34/78, 29,18% |
| PP + block hỗ trợ gom, **candidate** | 110 vùng; 59/78 có prediction, exact 33/78, CER 28,86%; 14 crop mới OCR thật, 96 crop còn lại giữ nguyên chữ/bbox |
| PP + block guide v2, **candidate** | 118 vùng; 62/78 có prediction, exact 34/78, CER 28,86%; 10 crop mới OCR thật, 108 crop còn lại đã đối chiếu không đổi; không promote |
| Python / TypeScript mới nhất | 979 qua + 1 skip Windows / 51 qua; typecheck/build qua |
| UI/options/art/lettering | Qua Edge riêng, desktop 1280/760 và mobile-sized 390 px; OCR/dịch giả lập trong UI QA |
| UI source binding mới | Qua 1280×900, 760×800, 390×844; save thật/unknown/revision và mở review không request; native/OCR/dịch giả lập |
| Handshake source v21 mới | Native Messaging thật: prompt/OCR/layout/scope/speakerBindingVersion khớp source, settings/library desktop/mobile qua; không nạp model |
| Va chạm dàn chữ baseline MN109-08 | **FAIL:** 4 cặp textBox giao nhau; không coi candidate xanh là đã sửa default |
| MN109-08 dùng block + cloud mới | 5 vùng; 0 box giao nhau, ID/wording/cuộn qua, 10 lần xem gốc khớp pixel ở bố cục native-size; ảnh RAM đã xem |
| Cổng “perfect” | **FAIL:** chỉ 34/78 exact, nhãn chưa độc lập kiểm chứng, một trang sai kích thước/một ảnh trùng; 0 Việt gold hợp lệ |

Các số alignment/CER chỉ là chẩn đoán containment trên nhãn chưa rà, **không phải precision/recall detector hay điểm dịch Việt**. Một trang sai kích thước và một ảnh trùng vẫn bị loại; fingerprint nguồn giữ nguyên. v18 cũng chưa làm mặc định. Nhãn OCR không phải gold phân loại nội dung hoặc nền sạch.

OCR warm ở lượt CPU này khoảng 5,8–14,7 giây/trang; detector khoảng 1,1 giây. Không gồm model dịch và không đủ mẫu để kết luận p95 hoặc “real-time”. Ưu tiên chất lượng trước khi tối ưu/tuyên bố tốc độ.

Detector block warm đo một lượt khoảng **0,38–0,52 s/trang**, OCR **3,64–8,48 s/trang**; trang cold có OCR/import/load 45,99 s. Ít crop hơn đồng thời mất coverage; không gọi đây là bản nâng cấp tốc độ đã nghiệm thu. Candidate có guide giữ nguyên mọi crop không đổi, có danh sách source-member cho mỗi union, không cấp erasure/plot-memory cho union chưa xác minh. Replay scope sau đó dùng đúng crop đã đo, không giả làm inference mới.

Lượt guide v2 được reader cho phép chạy dù RAM trống thấp: worker CPU 4 threads kết thúc không crash. Trang đầu có union mất **52,81 s** cho import/load, OCR 3 crop và routing; ba trang union tiếp theo mất 2,30 s/3 crop, 1,12 s/2 crop, 1,28 s/2 crop. Đây là thời gian **phần crop mới + routing**, không full-page/E2E/p95 hay số đo RAM peak; các trang không có crop mới chỉ replay/routing. Không gọi cloud, không tự đóng ứng dụng khác.

## Cloud và hình ảnh: có tiến bộ, chưa đạt scanlation

Theo đồng ý mới tối đa **0,01 USD**, chỉ gửi text OCR trang MN109-08 qua OpenRouter/DeepSeek V4.1 Flash, context rỗng, speaker/listener unknown; không gửi gold, ảnh hoặc tra cốt truyện. Một request, **2,56 s**, reservation **0,003378 USD**, provider-reported cost **0,0006591 USD**. Đây chưa phải hóa đơn đối soát hoặc p95. Guard nay chặn cả attachment ảnh/tools nếu adapter thay đổi trong tương lai; không dùng lại trần thử cũ.

Ảnh RAM: hai câu đầu hết dịch vụn/chồng chữ, bốn vùng có cleanup local; **khối dài bên trái vẫn là nhãn nền trắng dễ nhận ra**, một câu OCR dài sai và biệt danh Việt còn thô. Không sửa nguồn từ gold, không chấm “đúng nghĩa” bằng JSON đúng. Render replay dùng OCR thực đã ghi + bản dịch cloud mới; **không phải inference mới xuyên Native Messaging**. Cổng no-overlap xanh ở candidate không chứng nhận sạch hết glyph hoặc không làm hỏng tranh.

## Phân biệt lỗi overlay với ảnh chụp trình duyệt

Stress toggle bắt 234 pixel lệch đúng 1 mức sáng. Cùng sai lệch được tái hiện ở raw sau cuộn/chụp **trước khi nạp extension**: đây không phải bằng chứng chữ hoặc patch còn sót. Thay display của lớp dịch hoặc đổi root geometry không giải thích hết sai lệch.

Replay kiểm tra lại sau source-binding: 10 raw-scroll captures + 10 chu kỳ dịch/gốc, hash initial/restored/stopped khớp; ID/cuộn/RAF chậm/console/không API qua. `--assert-no-lettering-overlap` vẫn **FAIL 4 cặp**, không bỏ gate hoặc gọi replay là inference/latency mới. Evidence: `artifacts/private-render-speaker-binding-20261014.json`.

Harness nay so decoded pixel và có raw control. Ở bố cục kiểm thử kích thước ảnh gốc, không nội suy: 25 raw-scroll captures + 25 chu kỳ dịch/gốc khớp chính xác, không dùng dung sai. Đây là kiểm tra khôi phục ảnh, **không chứng nhận typography/cleanup đẹp trên bố cục co giãn**. Hình học native-size chỉ áp dụng trong QA, không đổi website người đọc. Cổng va chạm vẫn giữ và vẫn đỏ.

Luồng đã thử: bật dịch → nhận output đã ghi → cuộn → Alt+T (RAF bị giữ) → ảnh gốc → dừng. Trang đúng/nonblank, console/framework overlay sạch, không request ngoài localhost; vùng review không được erasure. Private replay dùng OCR/bản dịch đã ghi, không giả làm lượt cloud mới.

## Việc tiếp theo, theo đúng ưu tiên

1. Gom đúng câu và tách vùng OCR khỏi vùng dàn chữ; sửa hai cụm cột hẹp chồng nhau trên trang thật, không thu font dưới sàn hay che tranh để vượt test.
2. Kiểm tra toàn bộ crop/label và các vùng chưa có nhãn; nghiệm thu cleanup cần gold nền sạch riêng. Chấm Việt bằng người đọc Nhật–Việt/đối chứng có quyền, không lấy CER làm điểm dịch.
3. Chỉ sau đó chọn model cloud và đo latency/cost đủ mẫu. Pilot nhỏ này chưa xếp hạng chất lượng hoặc thay prompt mặc định; không gửi cloud thêm âm thầm.
4. Khi các cổng qua, đóng gói companion, handshake phiên bản và thử đúng extension đã cài trước khi giao bản test mới.

Lệnh chính: `npm run check`, `npm run test:ui`, `npm run test:lettering`, `npm run test:art`, `npm run test:options`, `.venv\Scripts\python.exe -m pytest tests/python -q`.

Evidence private trong `artifacts/`: `private-pages-open-overlap-fresh-20261014.json`, `private-pages-default-fresh-20261014-v4-scope.json` (fresh OCR trước khi tách namespace source-key), `private-scope-v4-punctuation-20261014.json` (policy hiện tại), `private-render-v4-native-pixels-20261014.json`, `private-gate-audit-20261014-punctuation-v4.json`. Không ship các file này.

Evidence lượt mới: `private-pages-comic-blocks-20261014.json`, `private-block-guided-20261014.json` (14 crop fresh), `private-block-guided-scope-20261014.json` (scope replay/no-memory), `private-cloud-comic-blocks-20261014.json`, `private-render-comic-blocks-20261014.json`. Không ship text/model/ảnh private.

Evidence guide v2: `private-block-guided-v2-fresh-20261014.json` (10 crop fresh), `private-block-guided-v2-evidence-replay-20261014.json` (cùng output, thêm raw detector provenance, không inference), `private-gate-audit-20261014-guide-v2.json` (perfect FAIL). Fingerprint nguồn không đổi. Bộ test chạy bằng basetemp mới trong artifacts do ACL thư mục tạm Windows; hai test boundary nay dựng ROOT riêng, vẫn xác nhận từ chối trước file access/model load, không nới guard.

QA mới: Edge riêng, fixture UI URL `http://127.0.0.1:64139/chapter/1`, 1280×900/760×800/390×844; private replay URL `http://127.0.0.1:52708/private-reader`, 1280×900, ảnh gốc 827×1170. URL/title/nonblank/framework overlay/console/interaction đều qua. Luồng native source riêng: status → cài đặt → thư viện, khớp prompt v21/OCR local-v3/layout v16/scope v4/speaker-source-v1, không nạp model, host QA đã gỡ và registry xác minh không còn. UI dùng transport giả lập; không thay test Edge cá nhân, Windows sạch hoặc điện thoại thật. Model/guide experiment không được dùng để vượt qua reader lock, source-review hay quyền nội dung.

Lệnh/evidence mới: `npm run check`, `npm run test:ui`, `.venv\Scripts\python.exe -B -m pytest tests/python -q -p no:cacheprovider --basetemp <thư_mục_mới>`, `node scripts/browser-pipeline-smoke.mjs --direct-source --connect-only`. Python 877/1 trong 25,61 s không phải latency đọc truyện. UI screenshot tự tạo đã xem: system-temp `mangalive-speaker-review-final-5699c0a058664720b28be335ab78fe84`. Native status/ảnh settings: `mangalive-real-browser-NTEeX4\evidence`. Cần quyền registry đúng scope cho host QA; không giảm bảo mật hay thay host cá nhân để vượt lỗi quyền trước đó.

Browser plugin không có nên dùng Playwright/Edge riêng. Có thể cài Browser plugin để tiện kiểm thử frontend trực tiếp hơn; không phải điều kiện để chạy extension.

Đối chứng crop mới: [ocr-overlap-partition-20261014.md](ocr-overlap-partition-20261014.md). Giữ crop/source-key nguồn và raw OCR cũ; chỉ hộp inference mới được tách bằng pixel. Mọi vùng mới có review, không kế thừa dịch/plot trust. Toàn bộ vùng/nhãn đã đối chiếu; không có regression text ngoài b02 trong tập này, nhưng không thay acceptance dịch/lettering. Python 979/1; `npm run check` 51 TS/typecheck/build qua. Source runtime và build extension hiện là **`0.1.0-dev.d07a2886be4a`**; Native Messaging đã pass ở Edge profile cô lập, Edge cá nhân cần restart/reload; 4 cặp dàn chữ vẫn là hạng mục chưa giải quyết.
