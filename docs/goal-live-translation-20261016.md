# Goal liên tục — Live translation desktop cloud-first

## Tuyên bố mục tiêu

Hoàn thiện Live translation thành một MVP Windows cho Edge/Chrome, cloud-first,
dịch manga Nhật → Việt theo thời gian gần thực với nghĩa đúng, xưng hô/văn hóa
đúng ngữ cảnh, chữ dàn hòa vào tranh và đọc liên tục ổn định. Trong giai đoạn
này **không chạy thử Edge cá nhân**. Edge chỉ được mở lại một lần ở cổng nghiệm
thu cuối sau khi các bằng chứng thuật toán và hồi quy đã đạt yêu cầu.

Mọi kết quả phải được chứng minh trên dữ liệu manga có quyền, không suy ra chất
lượng thương mại từ synthetic test, schema test, isolated browser hay số star
của dự án khác.

## Phạm vi cố định

- Windows desktop; cloud là tuyến chính, BYOK/subscription adapter giữ tách biệt.
- Ảnh và patch chỉ ở RAM; SQLite là dữ liệu chuẩn, Markdown là context ngắn đã
  lọc cutoff, JSON là backup đầy đủ.
- Pipeline: `RAM image → detector/scope → grouping/utterance → OCR → biểu cảm
  và cấu trúc nguồn → context cutoff/reader locks → JA→VI → cleanup/mask →
  integrated lettering → cache/prefetch → regression`.
- Manga-image-translator là comparator kỹ thuật chính ở commit/model đã pin;
  Comic Translate là comparator phụ; Kites chỉ tham khảo UX. Không sao chép GPL
  vào bundle sản phẩm.

Ngoài goal hiện tại: mobile, tối ưu LLM local, chat/quick-remind, community
memory, thanh toán/subscription, fine-tuning lớn và phát hành store.

## Nguyên tắc không được phá

1. Correct meaning → integrated lettering → continuous reading → extra features.
2. Không mất text nhỏ/dày/không bubble; detection không đồng nghĩa irrelevant.
   Vai trò dialogue/thought/narration/scene text/SFX/decorative/unknown phải
   tách riêng; chỉ skip khi có bằng chứng hoặc reader exclusion.
3. Detector box không phải glyph mask và không có quyền xóa tranh. Grouping phải
   giữ source members, polygon, raw score, source key và review reasons.
4. Context chỉ dùng lịch sử trước chapter/page cutoff. Speaker thiếu bằng chứng
   vẫn là `unknown`; không đưa future fact/spoiler vào context cũ.
5. Giữ họ/tên và sắc thái Nhật (senpai/sama/chan/kun, nee-chan/onii-chan không
   chồng thành “chị/anh nee-chan”), ngập ngừng, kéo âm, khoảng cách, quote,
   ellipsis, CAPS và cách nói từng chữ. Tên/thuật ngữ AI đề xuất chỉ là proposal
   cho tới khi reader xác nhận; lock có thể sửa và có lịch sử.
6. Cleanup local an toàn, bounded, reversible và default-on chỉ khi phân tách
   chữ đủ chắc. Neural/cloud inpainting là opt-in riêng, phải báo cost/latency/
   visual risk trước request đầu tiên; không gửi bubble phẳng đi tạo ảnh vô cớ.
7. Original view phải khôi phục exact và đồng bộ; kết quả trễ/stale không được
   sống lại trên revision khác. Offline không được gọi cloud hoặc metadata.
8. Không thêm paid request nếu chưa đối soát ledger ngân sách; không lưu key,
   private dataset, ảnh hay story memory vào repo/bundle/log.

## Cổng chất lượng bắt buộc

Chỉ chuyển sang cổng Edge cuối khi tất cả điều kiện sau có bằng chứng trên held-out
đã rà độc lập:

- serious translation error ≤2% trên ≥500 lượt thoại ordinary, reviewer độc lập,
  báo khoảng tin cậy 95%; không vi phạm phủ định, chủ thể, speaker, honorific,
  reader lock hay future cutoff;
- ordinary detection recall ≥98%, không overmerge/mất câu trên regression hard;
- ≥95% ordinary bubbles đọc được, fit và integrated; khó/SFX/chữ trên tranh
  báo riêng, không gộp vào điểm đẹp;
- protected art không đổi; erasure/cleanup và original restoration exact;
- warm first bubble p95 <5s; trang cloud ≤12 bubble p95 <8s; cache đã định vị
  p95 <200ms; RAM không thrash trên máy 16GB;
- không stale result, future context, key leak, offline network, silent paid
  request, unbounded memory hay schema migration không rollback được.

Các con số trên là **acceptance targets**, không phải kết quả hiện tại.

## Trình tự triển khai liên tục

### A — Trustworthy benchmark trước

- Fingerprint/quyền/duplicate/size audit private dataset.
- Rà độc lập nhãn Nhật; tạo Vietnamese reference, speaker/role, reading order,
  protected-art và clean-background gold; tách development/regression/held-out.
- Không gọi OCR label là translation gold hoặc clean-background gold.

### B — Tách lỗi end-to-end

- Harness đỏ có thể tái lập, chạy RAM-only adapter và lưu diagnostics không chứa
  text/key/ảnh ngoài artifact private.
- Đo riêng detector, grouping, OCR, context/translation, cleanup, lettering,
  restoration, latency và RAM; mỗi candidate phải chứng minh không mất câu,
  không overmerge, không sai speaker, không hỏng tranh.
- Bắt buộc phân tích các ca detector partial/miss và grouping mismatch thay vì
  chỉ tối ưu CER trung bình.

### C — Detector/scope/grouping/OCR

- Xây cheap pre-OCR page-hardness signal từ geometry, score distribution,
  fragment density và partition evidence; không dùng gold để route.
- Thử selective CTD trước/đồng thời baseline hoặc prefetch trang kế tiếp; giữ
  unmatched text là unknown, không tự coi irrelevant.
- Cải thiện vertical/rotation/multi-scale, union crop và seam partition; bounded
  repair chỉ các ID lỗi, giữ source ownership.
- Mọi candidate được paired benchmark với production và comparator; không promote
  chỉ vì exact/CER đẹp hơn nếu mất nội dung hoặc chậm vượt ngân sách.

### D — Dịch và bộ nhớ nhất quán

- Dịch theo utterance đã gom, không theo cột hẹp; cùng OCR/context cho mọi model.
- So model bằng meaning, naturalness, register, honorific, expression fidelity,
  latency, output length, timeout/retry/cache và cost; không chốt model từ quảng
  cáo hoặc vài câu demo.
- Reader confirm/edit/keep-later cho canonical weapon/clan/skill/organization;
  binding theo source key + cutoff, không theo ordinal geometry.

### E — Lettering hòa tranh

- Tách geometry, glyph mask và erasure authority. Bubble phẳng dùng màu/mask có
  bằng chứng, không dùng thẻ trắng chữ nhật; chữ trên nền cảnh giữ nguyên art nếu
  không chứng minh được cleanup an toàn.
- Fit font/dòng/dấu Việt theo vùng, ưu tiên giống raw nhưng giữ sàn readability.
- Cleanup local reversible mặc định; neural inpainting chỉ opt-in có đo chất
  lượng/độ trễ/chi phí và license.

### F — Đọc liên tục và tối ưu

- Cache OCR 24h, translation accepted 30 ngày/100 MiB LRU, không lưu ảnh; key
  theo source/page/revision/context/model.
- Ưu tiên trang hiện tại, prefetch tối đa hai trang tiếp theo khi có xác nhận;
  không crawl hidden endpoint, tự cuộn chapter hoặc chụp liên tục.
- Đo cold/warm/cache, p50/p95, RAM và provider/version; tối ưu tốc độ sau quality
  gate, không dùng latency để che mất nội dung.

### G — Regression và phát hành

- Full Python/TypeScript/build/package; timeout, quota, retry, crash, cancel,
  delayed result, resize/lazy-load/scroll, source restore, reader edit/lock.
- Mỗi vòng: `real failure → hypothesis → red test → patch → paired benchmark →
  regression → artifact/evidence → update runtime package`.
- Khi tất cả gate xanh: đóng gói cloud-first, rồi mới dùng Edge một lượt để kiểm
  tra connection, OCR→dịch→lettering, cuộn, xem gốc, retry và cache. Nếu rớt gate,
  quay về bước A–F; không gọi đó là release.

## Trạng thái bằng chứng hiện tại (2026-10-16)

- Production PP-OCRv5 + manga-ocr: 132 vùng, 62/78 assigned, 35/78 exact,
  CER 28.65%; chưa đạt quality gate.
- CTD line comparator: 80 vùng, 63/78 assigned, 44/78 exact, CER 16.72%; 8
  threads nhanh hơn nhưng vẫn chưa đạt cloud/live target và chưa được promote.
- Hybrid router dùng `baseline.review_count`: 48/78 exact, 70/78 assigned;
  chỉ là probe vì tín hiệu xuất hiện sau baseline OCR.
- Private dataset: 10 ảnh/81 nhãn cung cấp, 8 trang/78 nhãn hợp lệ sau audit;
  0 Vietnamese gold, 0 clean-background gold, Japanese labels chưa rà độc lập;
  vì vậy chưa phải held-out và không đủ để tuyên bố dịch chuẩn.
- Python/TypeScript tests đang bảo vệ contract/runtime; test xanh không đồng
  nghĩa manga quality đạt.

Lượt xác nhận code hiện tại: Python `1313 passed, 1 skipped` (40,82 s, basetemp
riêng); TypeScript `59 passed`, typecheck và build extension đều qua. Đây chỉ là
regression/code-health evidence, không thay thế quality gate trên manga thật.

## Việc tiếp theo đang được ưu tiên

1. Hoàn tất audit/gold protocol và tách development khỏi held-out.
2. Phân tích 14 partial + 2 miss detector, 10 grouping mismatch, 17 OCR mismatch;
   ưu tiên giữ nội dung và source ownership.
3. Thiết kế/probe pre-OCR hardness signal và selective CTD/prefetch không dùng gold.
4. Đo paired lettering/restoration trên các ca balloonless/background text và
   giữ fallback review khi không đủ bằng chứng.
5. Chỉ sau các bước trên mới benchmark cloud translation có ngân sách đã đối soát;
   không tạo thêm paid request trong lúc ledger còn thiếu hạn mức.

### Checkpoint mới — pre-OCR hardness probe

Đã thêm `companion/manga_live/page_hardness.py`, field
`pre_ocr_hardness` trong benchmark và router diagnostic
`scripts/probe_preocr_hardness_router.py`. Tín hiệu chỉ dùng geometry/score
trước OCR, không đọc gold/OCR/context và không có quyền skip/erase.

Fresh đo lại: baseline vẫn `35/78 exact`, `62/78 assigned`, CER `28,65%`; CTD
line/8-thread vẫn `44/78 exact`, `63/78 assigned`, CER `16,72%`. Router hardness
ngưỡng 0–20 chọn CTD toàn bộ và chỉ đạt `44/78`; ngưỡng 30 đạt `38/78`; ngưỡng
≥50 quay về baseline. Candidate chưa được promote. PaddleOCR-VL comparator đã
pin nhưng fail-closed trước load vì free RAM dưới guard 7 GiB.

Sau thay đổi: Python `1313 passed, 1 skipped`; TypeScript/typecheck/build đã
được xác nhận ở checkpoint trước. Kết quả mới chứng minh instrumentation không
regression, không chứng minh chất lượng manga đã đạt.

Đã thêm replay `scripts/probe_missing_region_fusion.py`: chỉ dùng comparator thứ
hai khi primary chưa gán region và secondary có đúng một region; không thay text
đã có. Fresh PP→CTD replay tăng assigned `62→74/78`, exact `35→45/78`, CER
`28,65%→18,85%`. Vì CER vẫn kém CTD whole-page và secondary chưa được xác minh
ownership, đây là review-only candidate, chưa phải production default.

### Checkpoint mới — OCR quality ceiling

Đã chạy comparator PP box threshold `0,45`: `63/78` assigned, `34/78` exact,
CER `26,94%`; tăng vùng và giảm CER không bù được một exact row bị mất nên
không promote. Đã thêm probe `scripts/probe_ocr_preprocess_variants.py` chạy
trên 78 crop trong RAM với cùng weights/hình học: base và autocontrast đều
`48/78`, unsharp `44/78`, threshold `38/78`; oracle sau khi nhìn gold chỉ
`49/78`, CER `8,84%`, vì vậy không được dùng làm selector runtime.

Kết luận hiện tại được ghi ở [docs/ocr-ceiling-20261016.md](ocr-ceiling-20261016.md):
78/78 không thể đạt trung thực bằng một filter/threshold/route nhỏ. Crop
recognizer control chỉ 48/78, và nhãn Nhật chưa rà độc lập; cần vòng audit gold,
recognizer được train/adapt trên dữ liệu có quyền và detector/grouping riêng
trước khi tuyên bố tiến gần 78/78. Không có Edge test, paid request hoặc đổi
production default ở checkpoint này.

Đã thêm `scripts/build_ocr_training_manifest.py` và test fail-closed: manifest
chỉ được tạo khi fingerprint/quyền/audit khớp, nhãn Nhật đã review độc lập,
mọi dòng có reviewer + geometry + split và có cả train lẫn title-held-out.
Chạy trên draft hiện tại bị từ chối trước khi tạo file; không có đường tắt để
fine-tune trên nhãn chưa kiểm chứng.

Lượt regression sau thay đổi: Python `1319 passed, 1 skipped` (37,68 s),
TypeScript `59 passed`, typecheck/build qua. Đây là bằng chứng contract và
leakage guard; chưa phải bằng chứng OCR đạt 78/78.

Mục tiêu vẫn `active`; chưa được đánh dấu hoàn tất và chưa được phép phát hành.

## Checkpoint 2026-10-16 — không có đường tắt 78/78

Đã chạy hai candidate geometry-only trên 78 crop riêng:

- Xoay crop dọc 90°: 57 ứng viên, chỉ 1 exact; edit tăng 61→671.
- Tách line/column bằng projection: 29 ứng viên, exact trên nhóm đó 19→9;
  edit tăng 28→72.

Cả hai bị loại và không chạm production default. Đã thêm
`scripts/build_ocr_review_queue.py` để gom ba recognizer đã chạy (manga-ocr,
Hayai Nova, Baberu) thành queue rà Nhật–geometry–reading-order; artifact chỉ ở
`artifacts/`, không được dùng làm route/runtime gold. Queue hiện có 9 ca ba
model cùng lệch nhãn cung cấp, 14 ca ba-way disagreement, 19 ca disagreement
một phần và 36 ca cùng khớp nhãn. Các ca cùng lệch phải được người đọc Nhật rà
trên pixel trước khi tạo training manifest; không được tự sửa gold bằng output
model.

Lượt xác minh sau checkpoint: Python `1321 passed, 1 skipped` (38,20 s),
TypeScript `59 passed`, `npm run typecheck` và `npm run build` đều qua. Đây là
bằng chứng harness/contract, chưa phải điểm OCR hay dịch; Edge và paid cloud
vẫn chưa chạy.

## Checkpoint 2026-10-17 — tách model context và hoàn tất đối chứng OCR48

Đã bổ sung model tóm tắt cloud độc lập với model dịch, consent/phí riêng,
evidence Nhật có cutoff và receipt chi phí bền vững; không tự chạy backlog khi
lưu cài đặt hoặc khởi động lại. Wiki chỉ hỗ trợ tìm danh tính truyện khi opt-in,
không nhập quan hệ/cốt truyện có thể spoil. Cold start không cần wiki; unknown
không biến thành sự thật do model suy đoán. Tài liệu triển khai và kiểm thử:
[context cloud](context-memory-cloud-20261017.md),
[đối chiếu nguồn model](context-multimodel-claims-primary-20261017.md).

Sau khi resource gate tự nhiên đạt, OCR48 đã thực sự đọc đủ tám trang, không
còn ở trạng thái chỉ chuẩn bị loader. Tiled tensor/scalar đều chỉ 20/78;
order-v2 sửa được mười edit ở hai nhãn nhưng không tăng exact. CTD được chạy
lại, giữ đủ 143 polygon và tái lập 44/78 không khác prediction/assignment.
OCR48 trên CTD chỉ 26/78. Không promote các tuyến kém này; baseline vẫn 35/78,
complement replay 49/78 vẫn review-only. Chi tiết:
[OCR48 đã đo](mit48-private-recognition-20261017.md).

Regression mới nhất: 1.452 Python passed / 1 skipped, 61 TypeScript passed,
typecheck/build qua. Không cài/nạp lại Edge cá nhân, không đóng gói release,
không thay gold hoặc lưu ảnh. Lượt OCR này không phát sinh request cloud.
Reservation tích lũy $0,49962719/$0,50 không phải actual billed spend; không
tự cấp thêm ngân sách. Goal vẫn active, chưa đạt release. Việc tiếp theo là
giải quyết source ownership chồng lấn bằng polygon đã giữ và rà những ca
pixel/nhãn xung đột, không tiếp tục chọn output theo gold hoặc chỉnh threshold
để làm đẹp điểm.

## Checkpoint 2026-10-17 — executed grouping ablations, no false promotion

Thử nghiệm đã đi hết từ red test tới recognition thật: union mọi polygon
32/78; support-component 36/78; cố định khối primary 26/78. Cả ba giữ đủ 357
member nhưng vẫn lặp chữ/gom sai hoặc đổi crop, nên đều bị loại. Complement
CTD + tiled PP đạt 49/78, 123 edit bằng replay, vẫn chưa thắng mọi gate so với
production. Không đưa candidate kém vào bản mặc định để làm như có tiến bộ.

Đã kiểm chứng có sẵn 46 proposal bóng thoại class-0 trong report ogkalu;
không cần tải lại cùng detector dưới tên RT-DETR. Predicate ownership chặt chỉ
cho 24/80 CTD và 26/140 PP unit một predicted owner duy nhất, còn lại unknown;
đây không phải accuracy đã chấm độc lập. Cần ownership/abstention có bằng chứng
trên các ca lỗi trước khi đổi partition tiếp. Bounding box vẫn không phải glyph
mask và không được quyền xóa tranh hoặc bỏ chữ phụ.

Đề xuất multi-model context đã được áp dụng phần có cơ sở: model tóm tắt tách
model dịch; evidence Nhật + cutoff; opt-in riêng, không tự chạy backlog hay
research wiki. Không tìm được wiki vẫn tạo truyện và tích lũy từ trang đã đọc.
Quan hệ/suy đoán/identity tương lai không tự nhập thành sự thật. Haiku/DeepSeek
vẫn là lựa chọn cần đo; GLM mandatory thinking chưa tự thêm vào runtime.

Tài liệu: [context implementation](context-memory-cloud-20261017.md),
[model source check](context-multimodel-claims-primary-20261017.md),
[grouping đã đo](recorded-source-union-probe-20261017.md),
[ownership source review](bubble-ownership-primary-20261017.md).

Lượt xác minh mới nhất: 1.472 Python passed / 1 skipped (49,78 s), 61 TypeScript,
typecheck/build qua. Không gọi cloud trả phí mới, không thay gold, không lưu
ảnh, không cài Edge/đóng gói release. Reservation ngân sách giữ nguyên;
goal vẫn **active**, production 35/78 chưa đạt chuẩn phát hành.

## Checkpoint 2026-10-17 — instance masks measured; context defect fixed

Đã thực thi hai ablation mask instance trên đủ tám trang: regrouping 41/78,
196 edit; cách ly nền crop nhưng giữ geometry gốc 44/78, 156 edit. CTD control
là 44/78, 157 edit. Một edit giảm ở cách ly crop không chứng minh tốt hơn:
recognizer bỏ dấu trái tim còn thấy rõ trong cả hai crop; nhãn cung cấp cũng
xung đột ở chỗ biểu cảm này. Cả hai candidate không promote; không sửa gold.
Mask container không phải đơn vị thoại, glyph mask hay quyền xóa tranh.
[Bằng chứng pixel và số đo](bubble-mask-private-probe-20261017.md).

Tiếp tục đề xuất multi-model bằng sửa lỗi context thực tế: thứ tự hai trang
bị đảo và dữ liệu polygon/lettering chiếm ngân sách thoại. Bản sửa giữ câu
gần nhất, đúng thứ tự đọc, cutoff từ page record và nguyên văn nguồn. Replay
độc lập mỗi trang trên text OCR thật giữ được 39→117 entry production và
18→70 CTD; không gọi đó là điểm dịch hay exact OCR. Không chạy wiki character
research hoặc tự suy đoán quan hệ. [Triển khai và kiểm thử](context-reading-order-replay-20261017.md),
[kiểm chứng model chính thức mới nhất](context-model-claims-revalidation-20261017.md).

Xác minh: 1.490 Python passed / 1 skipped (49,27 s), 61 TypeScript,
typecheck/build qua. Không paid request, không đóng gói hoặc test Edge cá nhân.
Reservation giữ nguyên $0,49962719/$0,50, không phải actual billed spend.
Goal active; production OCR vẫn 35/78, chưa đạt release.

## Checkpoint 2026-10-17 — member OCR completed; context proposal reconciled

Đã hoàn tất đọc từng polygon bằng cùng manga-ocr trên cả CTD và tiled PP,
không chỉ chuẩn bị harness. CTD member v2 đạt 44/78, 149 edit; sửa phiếu hướng
đọc của fragment gần vuông bằng replay v3 đạt 45/78, 145 edit. So với CTD whole
44/78, 157 edit vẫn có bốn nhãn tệ hơn và một exact giả do mất trái tim biểu
cảm đang thấy trên nguồn. PP member chỉ 26/78, 346 edit so với control 35/78,
265 edit; v3 không cứu được tuyến này. Không promote thay recognizer/crop
đại trà, không đổi gold hay reader binding. [Số đo, pixel review và giới hạn](manga-member-crop-probe-20261017.md).

Đề xuất wiki/dịch/tóm tắt được đối chiếu bổ sung, không triển khai một research
agent cốt truyện tự chạy: các route dịch/tóm tắt độc lập, evidence Nhật/cutoff,
cold-start unknown và consent riêng đã có. Không đủ bằng chứng để chốt Haiku
thắng Nhật–Việt/3,5 giây; GLM thinking và phí search phải tính đầy đủ. Adapter
hiện tại đã bỏ sampling cho Haiku; không cần một bản vá tương thích trùng lặp.
[Delta từ tài liệu chính thức](context-proposal-delta-20261017.md).

Xác minh mới nhất: **1.495 Python passed / 1 skipped** (47,37 s), **61 TS**,
typecheck/build qua. Không paid request, ảnh/crop trên đĩa, packaging hoặc
test Edge cá nhân. Reservation vẫn $0,49962719/$0,50, không phải actual spend.
Goal active; production OCR **35/78**, không phải 45/78, chưa đạt release.

## Checkpoint 2026-10-17 — actual-support lettering promoted, cache preserved

Đã đi từ lỗi thật, red test, replay đủ bộ và pixel QA tới native source default,
không dừng ở candidate: fresh Paddle dùng presentation v21. Integrated geometry
10→12 trên 132 vùng; source member/bbox/order/crop/scope và text không đổi,
production OCR vẫn 35/78, 269/939 edit. Hai vùng MN109-04:r011/MN109-07:r006
qua renderer desktop: glyph ROI samples về 0, protected ROI không đổi, cuộn
đúng và xem gốc khôi phục exact. Đây là replay geometry + bản Việt do QA cung
cấp, không phải inference/dịch gold hoặc clean-background certification.

Tách presentation khỏi identity nguồn/OCR: accepted cache và coverage cũ vẫn
đọc/resume với provenance thật, không bắt OCR/dịch trả phí lại. Reader bindings,
locks/history và schema không bị di chuyển. Bốn fallback MN109-03 còn nguyên;
390px dùng reading-card fallback, không tuyên bố mobile integrated/readiness.
[Thay đổi, phép thử và cổng còn đỏ](balloon-actual-source-support-20261017.md).

Xác minh: **1.504 Python passed / 1 skipped** (54,87 s), **62 TypeScript**,
typecheck/build và QA settings qua. Browser plugin không có; Edge Playwright
cô lập, ảnh/screenshot chỉ RAM. Không paid call, không sửa gold, không update
Edge cá nhân/đóng gói release. Reservation giữ $0,49962719/$0,50, không phải
actual billed spend. Đề xuất multi-model/cold-start/evidence/cutoff đã có ở
checkpoint trước; không tự thêm wiki character research hay chốt model từ
quảng cáo. Goal vẫn **active**, chưa đạt chuẩn phát hành.

## Checkpoint 2026-10-17 — blinded source reading completed

Đã thêm chế độ xuất `--blind` không lộ candidate JA/VI và thực sự đọc độc lập
từ pixel đủ **78/78 vùng, 8/8 trang**: 60 clear, 17 uncertain, 1 unreadable.
Đây là đề xuất rà của AI, không phải human gold, training data hay bộ Việt
được nghiệm thu. Khóa hash trước khi mở nhãn/prediction; giữ nguyên nguồn,
fingerprint, bbox và checkpoint ban đầu. Trong 60 proposal clear có 25 khác
nhãn cung cấp, gồm cả encoding biểu cảm; không tự sửa gold hoặc báo điểm mới.

Tách một ngộ nhận quan trọng: 16 nhãn không có prediction được gán, nhưng 14
vẫn giao bbox vùng nguồn đã giữ. Một số câu thực sự có trong output recognizer
nhưng nằm trong overmerge hoặc không qua containment; không gọi mọi alignment
trống là mất chữ detector. Hai vùng không giao bbox vẫn cần kiểm tra detection.
Đây là chẩn đoán, không nới matcher hoặc nhân đôi output để tăng điểm.
[Phương pháp, số đo và cổng còn thiếu](pixels-first-source-review-20261017.md).

Phần multi-model/context đã có: route dịch/tóm tắt riêng, evidence Nhật/cutoff,
cold-start không cần wiki và consent riêng; không tự nhập hồ sơ nhân vật hoặc
đoán quan hệ. Không đổi mặc định từ quảng cáo model. Tiếp theo ưu tiên ownership,
crop bị cắt và dấu biểu cảm trên các ca nguồn thật, không swap đại trà.

Xác minh **1.505 Python passed / 1 skipped** (54,65 s), **62 TypeScript**,
typecheck/build qua. Không request API trả phí mới, không lưu raster hoặc cài
Edge cá nhân/đóng gói release. Production vẫn **35/78, 269/939 edit** so với
nhãn chưa rà người; không gọi đó là chất lượng dịch. Reservation không đổi
$0,49962719/$0,50, không phải actual billed spend. Goal vẫn **active**.

## Checkpoint 2026-10-17 — disjoint source grouping and parent OCR frame

Đã tái hiện và tối giản lỗi gom hai lượt thoại thành một trên nguồn thật:
thước đo cột rộng cho phép nối vượt quá thước đo cột hẹp. Candidate min-scale
đơn thuần bị loại vì tạo thêm chữ từ tranh ở trang khác và mất dấu hỏi. Bản
sửa giữ parent khi child/source hoặc crop có lề chồng nhau, chỉ thử trong
cluster gốc; sau đó giữ chiều dọc/ngang của **crop suy luận thực của parent**
để không cắt mất dấu câu. Không nới bbox nguồn hay quyền xóa tranh.

Đã đưa phép giữ frame vào public seam `partition_ocr_boxes(source_parents=...)`,
không còn chỉ nằm ở probe. Parent partition được tính lại từ pixel; giữ đủ
member/score, không tin hint crop, không vượt reader exclusion/role/bubble.
Hai crop thay đổi chạy OCR thật bằng implementation mới; 131 vùng còn lại
chỉ reuse khi member, bbox và inference crop đều trùng. Đủ tám trang đạt
**36/78 exact, 250/939 edit (26,62% CER), 133 vùng**, so với production
35/78, 269/939 (28,65%), 132 vùng. Một nhãn cải thiện, không nhãn regressed,
một assignment thêm, không assignment mất. Không sửa gold/matcher; câu trái
được tách đúng nhưng vẫn chưa được containment gán, không tự nhận thêm exact.

Thêm red/green cho crop có lề chồng nhau dù source bbox rời; replay cuối
giữ nguyên inference input/kết quả trên cả bộ. Hai crop OCR fresh mất 1,83 s,
cold load 12,46 s; **không phải page latency hay p95**. Bản source grouping này
vẫn experimental, chưa nối vào native default: cần version/cache/source-key
compatibility và scope/lettering paired checks, không âm thầm gắn reader
history cũ sang child hoặc ordinal mới. [Bằng chứng và giới hạn](pair-scale-parent-frame-20261017.md).

Đề xuất context được rà delta bằng nguồn chính thức: các model là ứng viên
có thật nhưng chưa có paired manga Nhật–Việt/median 3,5 s; không đổi mặc định.
Route dịch/tóm tắt riêng, evidence Nhật/cutoff, cold-start unknown và consent
đã có; không tự nạp hồ sơ nhân vật wiki hoặc đoán quan hệ sau vài trang.
[Delta model/context](context-proposal-delta-20261017-r13.md).

Xác minh cuối: **1.531 Python passed / 1 skipped** (51,73 s), **62 TS**,
typecheck/build qua; 96 regression grouping/partition qua. Không paid call,
không lưu raster, sửa gold, cài Edge cá nhân hay đóng gói release. Reservation
không đổi $0,49962719/$0,50; không phải actual billed spend. Goal **active**;
production vẫn 35/78, chưa đạt chuẩn phát hành.
