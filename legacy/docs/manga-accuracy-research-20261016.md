# Nâng độ chính xác manga và giữ tốc độ đọc live — nghiên cứu nguồn gốc

Ngày đối chiếu: 2026-10-16. Phạm vi: desktop Windows + Edge/Chrome, máy 16 GB
không GPU rời, cloud-first. Đây là nghiên cứu và thiết kế thử nghiệm, **không
phải kết quả benchmark mới, thay engine mặc định, train hoặc bản phát hành**.
Không tải model/dataset, gửi ảnh riêng, chạy API trả phí hay thuê GPU trong lượt này.

## Kết luận quyết định

Giải pháp phù hợp nhất hiện nay là **pipeline chuyên biệt có truy vết từng vùng,
hai tầng chất lượng**, không phải một VLM lớn làm mọi thứ hoặc liên tục fine-tune
trên bộ kiểm tra. Sửa ownership/crop trước; thử OCR chuyên dụng trên cùng crop;
chỉ nâng tuyến vùng khó có bằng chứng; dịch cả lượt thoại với context đúng cutoff;
xóa chữ bằng mask độc lập; dàn chữ theo bóng và giữ khả năng khôi phục ảnh gốc.
Đây là khuyến nghị kỹ thuật của dự án, không phải tuyên bố đã đạt chất lượng.

Baseline không đổi: **35/78 exact**, 269/939 edits, CER 28,65%, 132 vùng nguồn,
62/78 containment alignment. Exact hiện có normalization NFKC/whitespace của
harness, không phải chứng nhận giữ nguyên mọi cấu trúc biểu cảm. GT-crop với
manga-ocr đạt 48/78, CER 9,37%; đó là phép chẩn đoán điều kiện crop tốt hơn,
không phải trần tuyệt đối của model hoặc bằng chứng chỉ cần gom hộp là xong.
8 trang đang được sửa lặp lại phải gọi là **development/regression set**, không
phải held-out chưa từng nhìn. Nhãn Nhật chưa rà độc lập, 0 Việt gold hợp lệ,
không clean-background gold. [Kết quả hiện hành](quality-upgrade-20261016.md).

Đối chiếu chỉ đọc giữa `private-benchmark-crop-20261015.json` và
`private-pages-production-v20-20261016.json` (cùng fingerprint, đủ 78 khóa
`page/id`, reference khớp; không chạy inference mới) cho thấy: 33 nhãn đúng ở
cả crop và full-page; 15 đúng ở crop nhưng mất khi chạy full-page; 2 sai ở crop
nhưng đúng ở full-page; 28 sai ở cả hai. Vì vậy khoảng 48 → 35 là **net 13**,
không phải đơn giản “13 lỗi detector”. 16 nhãn không có page assignment (10
trong số đó crop-exact), 16 nhãn gán nhiều region. Đây chỉ là diagnostic
assignment trên metric normalized hiện có, chưa phải kết luận 16 detector misses
nếu chưa rà ảnh từng ca.

## 1. Phát hiện quan trọng nhất: ground truth Manga109 đã thay đổi

Manga109-v2026 sửa khoảng 29.000 nhãn thoại: chép sai, hộp quá lớn, thiếu chữ,
chồng SFX và gộp nhiều bóng. Cùng hệ OCR được chấm lại có E2E H-mean
48,5 → 62,9; **đây là thay đổi đánh giá do nhãn, không phải model tăng 14,4 điểm**.
Tác giả dùng OCR để tìm bất đồng rồi kiểm tra thủ công, không coi OCR là gold.
[Paper gốc](https://arxiv.org/html/2605.21182v1).

Hub chính thức hiện cấp Manga109-s-v2026; `PrayerHaNemurenai` đã đổi kích thước
và scale annotation. Manga109Dialog không nằm trong release này; v2023 còn riêng.
Vì vậy không trộn tọa độ/nhãn giữa bản mới và bộ riêng hiện tại.
[Thông báo release](https://huggingface.co/datasets/hal-utokyo/Manga109-s).

**Áp dụng đề xuất:** giữ fingerprint/baseline cũ bất biến; lập crosswalk
`source_release + book + page + image_size/hash + annotation_revision` và một
bản rà nhãn riêng. Mọi sửa gold phải có bằng chứng, người rà và lịch sử; không
tự thay nhãn cho khớp prediction. Nếu không có đúng nguồn/bản, đánh dấu unknown.

## 2. Các công cụ thực sự làm gì

| Nguồn đã đọc | Kỹ thuật có bằng chứng | Học được / không được suy diễn |
|---|---|---|
| [manga-image-translator: pipeline](https://github.com/zyddnys/manga-image-translator/blob/main/manga_translator/manga_translator.py) | Tách detection → OCR → textline merge → translation → mask refinement → inpaint → rendering. | Chất lượng là tích nhiều khâu; repository không chứng minh đạt tốc độ desktop của chúng ta. Không bê nguyên download runtime/log/debug image vào companion. |
| [MIT: grouping](https://github.com/zyddnys/manga-image-translator/blob/main/manga_translator/textline_merge/__init__.py) | Đồ thị khoảng cách/hướng/cỡ chữ, chia nhóm qua minimum spanning tree. | Là geometric heuristic, không tự hiểu hai người nói hoặc hai câu ở gần nhau. Cần chấm overmerge/split, không chỉ số vùng. |
| [MIT: mask refinement](https://github.com/zyddnys/manga-image-translator/blob/main/manga_translator/mask_refinement/__init__.py) | Kết hợp raw mask và textline, fit/fill mask, resize và dilation. | Detector bbox không bằng glyph mask; nới mask để hết lồi chữ có thể xóa nét tranh. Không áp dụng ignore-bubble như phân loại vô nghĩa. |
| [comic-text-detector](https://github.com/dmMaze/comic-text-detector) | Block/line/mask cùng pipeline; ~13k training ảnh, weak supervision từ Manga109-s, DCM và synthetic. | Tác giả không có quyền chia sẻ toàn bộ ảnh/font; provenance không tự được giải quyết bằng GPL source. Đã có comparator nội bộ, không chạy lại như phát hiện mới. |
| [BallonsTranslator](https://github.com/dmMaze/BallonsTranslator/blob/dev/README_EN.md) | Auto modules cộng biên tập mask, redraw/inpaint, WYSIWYG và style/font presets; ước lượng bố cục từ nguồn. | Công cụ hỗ trợ người làm bản dịch, có đường sửa thủ công. Ví dụ đẹp không chứng minh mọi trang được tự động hóa hoàn toàn. |

CTD/MIT/BallonsTranslator có mã GPL; dùng thương mại không đồng nghĩa được phép
đóng gói vào mọi sản phẩm với mọi giấy phép. Review code, weights, runtime và
fonts riêng trước phân phối. Kiểm tra detector trước đây còn chỉ ra CTD chậm
hơn PP trên máy này và block detector có thể giảm vùng nhưng mất coverage.
[Audit detector đã có](detector-alternatives-20261014.md).

### Kites, extension thương mại và scanlation — đối chiếu source

Đã đọc Kites ở commit `4acebe6dd3bd253aafaf38b24d849f9b40ba94e0`:
grouping/furigana/MST và phục hồi dấu lẻ nằm ở
[OcrManager](https://github.com/Unheat/Kites/blob/4acebe6dd3bd253aafaf38b24d849f9b40ba94e0/src/offscreen/services/OcrManager.ts);
dịch và cleanup chạy đồng thời trong
[orchestrator](https://github.com/Unheat/Kites/blob/4acebe6dd3bd253aafaf38b24d849f9b40ba94e0/src/offscreen/services/PipelineOrchestrator.ts).
[InpaintManager](https://github.com/Unheat/Kites/blob/4acebe6dd3bd253aafaf38b24d849f9b40ba94e0/src/offscreen/services/InpaintManager.ts)
nhận polygon detector, không phải mask nét chữ dù tên gọi dễ gây hiểu nhầm.
[TypesetLayout](https://github.com/Unheat/Kites/blob/4acebe6dd3bd253aafaf38b24d849f9b40ba94e0/src/offscreen/utils/typesetLayout.ts)
fit font bằng binary search và cân dòng, nhưng có quy tắc hyphen tiếng Anh.
Không copy nguyên filter bỏ vùng nghiêng/lề/score thấp hoặc log raw text: trái
coverage/privacy của ta. GPL và phép đo thực tế vẫn cần review; mô tả hiệu năng
trong README không thay benchmark end-to-end.

[Scan Translator FAQ](https://scan-translator.com/faq) tự thừa nhận có thể thiếu,
gộp hoặc tràn chữ. [Trang tác giả Ichigo](https://ichigo.gumroad.com/l/ichigo-reader)
nhắc OCR/dịch trả phí nhưng không công khai đủ engine, corpus hoặc số đo để
kết luận công nghệ bí mật nào làm họ chính xác. Không lấy marketing làm ground truth.

Một [hướng dẫn của người làm scanlation](https://github.com/murk-sy/manga-pr-guide/blob/master/Guide.md)
tách translator, proofreader, cleaner/redrawer, typesetter và QC. Ảnh hoàn thiện
có thể gồm nhiều lượt sửa người làm, không phải bằng chứng hệ live cũng hoàn hảo.
Không áp dụng quy tắc đơn giản hóa dấu câu của guide cho yêu cầu sát raw của ta.

### Vì sao nền tranh có thể trông nguyên vẹn

Chữ mới nằm trên ảnh nguồn đã xóa nét chữ cũ bằng mask; nền phẳng chỉ cần fill
màu/texture phù hợp, còn tranh bị che cần nội suy hoặc redraw. LaMa/AOT/PatchMatch
là các nhánh trong BallonsTranslator; không phải mọi inpaint đều dùng image API
hoặc tính token. Nền thật phía dưới chữ không quan sát được, nên phục hồi phức
tạp là ước lượng, không bảo đảm khôi phục đúng nguyên tác.
[Danh sách inpainter của tác giả](https://github.com/dmMaze/BallonsTranslator/blob/dev/README_EN.md#inpainting).

Nghiên cứu [structure-preserving manga editing của Mantra](https://github.com/mantra-inc/structure-preserving-manga-editing)
và [paper](https://arxiv.org/abs/2603.27790) sửa trajectory của image-edit model để
giữ cấu trúc. Đây là hướng optional cho tranh khó, không là bằng chứng CPU 16 GB
chạy nhanh; overhead nhỏ so với model lớn không có nghĩa tổng runtime nhỏ.
Giữ fill/mask local an toàn mặc định; neural reconstruction phải có opt-in riêng.

## 3. OCR nào đáng thử tiếp, OCR nào chưa nên đổi mặc định

Các chỉ số bên dưới là **công bố tác giả**, khác tập/protocol/hardware;
không xếp chung thành bảng vô địch và không gán cho sản phẩm hiện tại.

| Ứng viên | Bằng chứng chính | Quyết định nghiên cứu |
|---|---|---|
| [manga-ocr](https://github.com/kha-white/manga-ocr) | Multi-line/vertical/furigana; tác giả cảnh báo crop dài dễ sai và ảnh trống có thể sinh câu. | Giữ đối chứng. Crop ownership, blank/review gate và giới hạn retry quan trọng hơn ép output có vẻ đúng tiếng Nhật. |
| [PaddleOCR-VL-For-Manga](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga) | 1,5M synthetic + Manga109-s; 90/10 chia ngẫu nhiên crop, tác giả báo ~70% exact. Apache-2.0 declaration. | Ưu tiên comparator chất lượng crop sau audit runtime; random-crop split không chứng minh unseen-title. Không mặc định chạy mọi vùng CPU. |
| [Baberu OCR](https://huggingface.co/genshiai-daichi/baberu-ocr) | 115M; ONNX 122/243 MB; distillation; lCER 3,59% trên 2k Manga109-v2026 theo tác giả. Input224²; dài >~190 chữ có lỗi. | Ứng viên nhẹ đáng preflight. lCER bỏ khoảng trắng/ký hiệu nên không thay raw-expressive metric. Size file không phải peak RAM/tốc độ. Apache declaration không xác minh quyền corpus tư. |
| [Hayai Nova](https://huggingface.co/JustANormalTinkerer/hayai-ocr-v2.5-nova) | Patch compression/KV-cache, budget384/512; benchmark card trên GPU, custom code và corpus riêng. | Đã thử local 43/78 và42/78, thấp hơn48/78 GT-crop; không lặp lại chỉ vì card mới. Không nhập normalization xóa biểu cảm. [Kết quả](hayai-resize-results-20261016.md). |
| [Paddle VL1.6 manga SFT](https://github.com/boomerkuigi/paddleocr-vl-1.6-manga-sft) | Split theo book80/10/10, giữ raw metrics/hash; V1 frozen, V2 thất bại do punctuation/form drift. | Recipe hữu ích cho thiết kế train/eval; model mới chưa đo trên tập riêng. V2 là minh chứng fine-tune tiếp có thể tệ hơn. |
| [sorryhyun Paddle1.6 manga LoRA](https://huggingface.co/sorryhyun/paddleocr-vl-1.6-manga-lora) | v4 tập trung SFX; có runaway; pseudo-label từ fan-translated pages, v3/v4 khác files. | Sau thoại thường, không ưu tiên MVP. Review provenance và raw punctuation; công bố normalized/heart-blind không tương đương sát raw. |
| [manga-ocr-base-2025](https://huggingface.co/jzhang533/manga-ocr-base-2025) | Card phần lớn là template thiếu training/eval. | Chưa đủ căn cứ cho ưu tiên cao, tên2025/nhẹ hơn không chứng minh tốt hơn. |
| [NAR preview](https://huggingface.co/muscgab/manga-ocr-nar-preview) | Một forward dùng129 queries, tối đa128 chữ; tốc độ công bố AppleMPS, không phải WindowsCPU; weights CC BY-NC-SA. | Học kiến trúc one-pass/distillation, chưa đưa vào sản phẩm thương mại hoặc mặc định. Không suy từ throughput GPU sang first-bubble latency. |

Tập [JMangaBench_Mixed](https://github.com/muscgab/JMangaBench_Mixed) báo
manga-ocr CER4,683% và Paddle-manga2,910%, nhưng đo trên RTX4090, crop-only,
không model-load/detector/render. 1.286 crop thật từ Manga109-s, 2.000 synthetic;
normalization bỏ whitespace và có metric bỏ punctuation. Không dùng các số này
làm SLA máy hiện tại hoặc train trực tiếp lên benchmark. Model đã dùng Manga109
trong phát triển có nguy cơ overlap; cần thêm unseen-title/author có quyền.

### Không nhầm hai “MangaOCR”

MangaOCR của [MangaVQA/MangaLMM](https://manga109.github.io/MangaVQA_LMM/)
là benchmark full-spread dialogue + COO, có split theo tác giả; không phải engine
kha-white. MangaLMM là Qwen2.5-VL fine-tune.
[Repo](https://github.com/manga109/MangaLMM) mô tả train4×A10080GB;
[model card](https://huggingface.co/hal-utokyo/MangaLMM) khai MIT. Khối lượng này
không phù hợp mặc định desktop. Điểm OCR gần0 của general VLM trong protocol
full-page không có nghĩa nó không đọc được crop riêng. MIT code/weight không
đổi quyền của ảnh fullManga109 dùng huấn luyện.

## 4. Dataset: chọn đúng nhãn và đúng quyền

Không có bộ OCR nào tự cung cấp đủ gold Nhật, Việt, speaker, glyph mask và nền
sạch. Không tự tải/đưa corpus vào train trong nghiên cứu này.

| Nguồn | Nhãn hữu ích | Quyền và hạn chế cần giữ |
|---|---|---|
| [Manga109 / Manga109-s](https://manga109.github.io/manga109-project-website/en/index.html#license) | Text/face/body/frame; -s87volumes, bản2026 đã sửa thoại. | Full109 học thuật/phi thương mại; -s cho phép kết quả/pretrained model thương mại có ghi nguồn, không redistribute corpus hoặc biến ảnh sửa thành sản phẩm. Gated access không bằng quyền upload bên thứ ba. |
| [COO](https://github.com/ku21fan/coo-comic-onomatopoeia) | 61.465 polygons SFX, 2.261 links chữ bị ngắt. | Tách hard-SFX benchmark; ảnh phải lấy theo Manga109. Chọn giao-s87book và kiểm tra quyền annotation, không coi mọi SFX là bỏ qua. |
| [MangaSeg](https://huggingface.co/datasets/MS92/MangaSegmentation), [license](https://huggingface.co/datasets/MS92/MangaSegmentation/blob/main/LICENSE) | Instance segmentation frame/text/face/body/balloon/onomatopoeia. | License annotation cho academic+commercial với credit; quyền manga pixels vẫn riêng. Kiểm tra mask semantics/resolution: instance region không mặc nhiên là glyph mask an toàn. |
| [450 mask labels](https://zenodo.org/records/4511796), [owner code](https://github.com/juvian/Manga-Text-Segmentation) | Pixel text segmentation easy/hard; pre/postprocess khác nhau. | Nguồn ảnh Manga109 lấy riêng. License grant của masks phải xác minh rõ trước train thương mại; trang Zenodo không hiện đủ điều khoản trong lần đọc. Không phải clean-background gold. |
| [JMangaBench_Mixed](https://github.com/muscgab/JMangaBench_Mixed) | Crop/transcript; synthetic có body-text mask không bao furigana. | Dùng evaluation recipe sau cổng bộ riêng; code/assets GPL, fonts có notice riêng, nền Manga109-s không redistribute. Synthetic không là paired background thật của trang manga. |
| [OpenMantra](https://github.com/mantra-inc/open-mantra-dataset), [license](https://github.com/mantra-inc/open-mantra-dataset/blob/master/LICENSE.md) | 5series; JA với professional EN/ZH, bbox thoại. | CC BY-NC4.0; không có VI. Không mặc nhiên dùng train thương mại hoặc pivotEN làm Vietnamese gold. |
| [AnimeText](https://huggingface.co/datasets/deepghs/AnimeText), [OCR derivative](https://huggingface.co/datasets/JustANormalTinkerer/animetext-ocr) | Detection blocks/hard negatives; derivative có OCR pseudo-label. | CC BY-NC-SA4.0 và provenance đa nguồn. Không đưa vào sản phẩm/train thương mại chỉ vì model downstream ghi Apache; pseudo-label không là gold độc lập. |
| [MangaOCR benchmark](https://huggingface.co/datasets/hal-utokyo/MangaOCR) | Full-spread detection+recognition, không chỉ crop. | Dẫn xuất fullManga109 cần rà điều khoản gốc; phù hợp học protocol/author split, không tự nhập tất cả vào product training. |

[Synthetic generator của manga-ocr](https://github.com/kha-white/manga-ocr/tree/master/manga_ocr_dev/synthetic_data_generator)
có dọc/ngang, multiline, furigana, tate-chu-yoko và nền; đây là hướng tự tạo cặp
text/mask/background bằng font và tranh được cấp quyền. Nên bổ sung unequal
columns, quotes xuyên bóng, dấu kéo dài, crop lệch và no-text negatives.
Recipe upstream ghi file ảnh: không chạy nguyên xi trong reader RAM-only.

## 5. Thứ tự thử nghiệm đề xuất — không nới gate

Đây là thiết kế mới của dự án; số lượng/tỷ lệ bên dưới không là kết quả đạt được.

1. **Rà gold trước.** Hai người có khả năng đọc Nhật rà 78 nhãn bất đồng, crop
   geometry và split/merge ownership; giữ uncertain labels. Bổ sung Việt tham
   chiếu có chủ thể/phủ định/xưng hô/honorific, không ép mọi bản dịch cùng câu chữ.
   Thêm ROI glyph/phần tranh bảo vệ và nền sạch thủ công cho ca khó có quyền.
   Điểm nhãn cũ/mới tách riêng, không sửa mẫu để đạt điểm.
2. **Thay từng biến.** Giữ ảnh/crop/engine cố định để chấm grouping; giữ crop
   cố định để chấm OCR. So text-line PP với learned paragraph/bubble guide nhưng
   retain raw class/score/source members. Không chấp nhận mất chữ để ít vùng hơn.
   Nhóm unknown/split/overmerge cần report riêng; bubbles không bằng utterances.
3. **OCR hai tầng có giới hạn.** Sau preflight license/hash/runtime, ưu tiên
   Paddle-manga comparator chất lượng và Baberu comparator nhẹ. Routing dựa crop
   cắt biên, length/repetition anomaly, disagreement và confidence đã calibration;
   không dùng xác suất token/tiếng Nhật “tự nhiên” như sự thật. Chỉ retry vùng lỗi
   một lần; bất đồng còn lại giữ nguồn và review. Không chạy 3 OCR mọi crop.
4. **Dịch semantic unit, render source unit.** Context đủ các lượt thoại gần,
   member→utterance map rõ; output giữ ID và nguồn quote/dấu/nhịp. Term/pronoun
   locks có cutoff, speaker chưa biết vẫn unknown. Không hợp thức hóa OCR bằng
   một câu Việt mượt nhưng sai nguồn. Nghiên cứu
   [COLING2025](https://aclanthology.org/2025.coling-main.232/) hỗ trợ thử context
   trên manga, nhưng JAEN/JAPL không chứng minh chất lượng JAVi.
5. **Mask và lettering độc lập.** Chỉ glyph evidence cho phép xóa, giữ vùng
   bất định/ảnh nguyên. Fit typography theo shape/cỡ chữ/contrast và Vietnamese
   diacritics; không bắt cùng pixel size nếu gây tràn/khó đọc. Đo leakage,
   art-change ngoài mask, collision, tiny-font và exact original restoration;
   glyph gold không chứng minh nền dưới glyph đã redraw đúng.
6. **Sau khi chất lượng cải thiện mới tối ưu critical path.** Prewarm resident
   model, request batch nhỏ theo trang/lượt, cleanup an toàn chạy cùng translation,
   prefetch hữu hạn ảnh DOM đã tải và accessible; revision cancellation, bounded
   concurrency/RAM và exact cache keys. Giữ interactive priority, không trả bản
   nháp rồi âm thầm đổi lời. Đo first usable bubble/page/peakRSS, cold/warm/cache
   riêng; speed paper/GPU/token-per-second không là SLA app.

Các hướng warm worker, bounded retry, cache/prefetch và cutoff đã xuất hiện
trong ghi chú MVP hiện tại; không tính là tính năng mới được thực hiện bởi bản
nghiên cứu này. Nếu sau này tối ưu adapter local, tài liệu
[ONNX Runtime quantization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)
cảnh báo quantization có thể làm mất độ chính xác và phụ thuộc hardware;
[thread tuning](https://onnxruntime.ai/docs/performance/tune-performance/threading.html)
cần tránh oversubscription. Đây là cổng thử nghiệm sau khi quality-equivalent,
không phải lý do đổi ưu tiên cloud-first hoặc mặc định INT8.

### Ma trận nghiệm thu mỗi candidate

| Trục | Bắt buộc ghi nhận |
|---|---|
| Detection/grouping | Recall/precision có annotation; missing, duplicate, split, overmerge, ownership, thứ tự; cả text_free/unknown/SFX |
| OCR | Raw/expressive exact và CER; diagnostic normalized tách riêng; ký tự tên/phủ định, quote/pause; failures vẫn trong denominator |
| Translation | Người Nhật–Việt chấm lỗi nghĩa/chủ thể/phủ định/xưng hô/honorific và độ tự nhiên; không dùng LLM judge làm chứng nhận duy nhất |
| Artwork/layout | Glyph leakage, mask precision/recall, ngoài-mask pixel changes, protected-art ROI, overflow/collision/minfont, synchronous conceal và exact restore |
| Runtime | Cold/warm/end-to-end first bubble/page, stages, network/API cost và timeout; p50/p95 với cỡ mẫu/cấu hình rõ; peak RSS/thrashing trên 16 GB |
| Policy | Offline 0 network; RAM-only image; no text/key logs; cutoff/spoiler locks/source anchors; cache/edit invalidation và stale result tests |

Không lấy việc sửa đúng một crop hoặc điểm tổng giảm để đổi mặc định. Candidate
phải thắng ở ca mục tiêu mà không làm mất chữ, hỏng tranh, đổi dấu biểu cảm,
speaker bindings hoặc restoration của phần còn lại. Chất lượng chưa có gold
phải báo **chưa biết**, không chuyển thành pass.

## 6. “Liên tục train” nên là chu kỳ có kiểm soát, không học nóng khi đọc

Sau cổng bộ riêng, mới mở training corpus có quyền và tập **title/author-held-out
mới, không động tới trong tuning**. Group theo title/author và hash/perceptual
duplicate, không random crop cùng trang/font sang train/test. Giữ text dài,
furigana, SFX, nền tối/trống và hard negatives thành slice riêng.

Thứ tự hợp lý: lựa chọn/routing pretrained → cải thiện labels/ownership →
fine-tune detector nếu thiếu vùng → fine-tune OCR nếu sai glyph trên crop đúng.
LoRA/full-SFT/distillation chỉ khi error taxonomy cho thấy cần; fine-tune không
chữa context-spoiler, việc lấy nhầm crop, mask xóa mồ hôi hoặc chữ tràn bóng.

Reader correction mặc định là bộ nhớ riêng; không tự gom về server/training.
Muốn đóng góp dữ liệu cần opt-in rõ quyền và khử định danh; review Nhật độc lập,
không lấy prediction chưa xác nhận làm gold. Freeze champion/challenger, lưu
manifest/data/license/model/hash/preprocessing/evaluator; chạy regression rồi
human review trước promotion; rollback được. GPU/chi phí training cần kế hoạch
và chấp thuận riêng, không dùng máy người đọc 16 GB làm training worker.

**Kết luận hiện tại:** có nhiều đường nâng chất lượng đáng làm, nhất là gold
v2026 + crop/ownership + selective OCR. Chưa có bằng chứng đủ để hứa hoàn hảo,
chốt một model mới hoặc nói personal Edge đã được cập nhật. Bản nghiên cứu này
không đổi production, không mở rộng dataset và không tiêu credit.
