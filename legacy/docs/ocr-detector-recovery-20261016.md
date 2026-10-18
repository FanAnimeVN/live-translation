# Detector và phục hồi vùng bỏ sót — 2026-10-16

## Kết luận

Đã bổ sung thuật toán **disjoint multi-scale recovery** dưới dạng comparator:
giữ nguyên vùng/anchor cũ, chỉ bổ sung đề xuất nguồn không giao vùng cũ, không
overmerge, không tự xóa tranh hoặc ghi memory. Replay tăng containment assignment
62 → 63/78, giảm 269 → 265 edit, không label regression, nhưng exact vẫn 35/78.
**Chưa promote vào companion/Edge.** Rà ảnh còn thấy một proposal bắt nét lá cây
thành chữ; không thể dùng bảng 78 nhãn thiếu coverage để chứng nhận false-positive.

Hai phép đổi detector toàn trang cũng chưa thắng baseline: hạ upstream threshold
và ép resize lớn hơn đều giảm CER nhưng mất câu exact/regress ở nhãn khác. Không
đổi default để lấy chỉ số trung bình đẹp, không train/tải model hoặc mở rộng bộ dữ
liệu. Không API request, credit, telemetry, thay registry hay đóng gói companion.

## Nghiên cứu source: thử đúng tầng xử lý

Config PP đã pin có pixel `thresh=.3`, upstream `box_thresh=.6`; mã companion
lọc tiếp `dt_scores >= .35`. DBPostProcess đã loại box dưới .6 trước khi trả score,
nên chỉ hạ bộ lọc .35 không khôi phục được box. Candidate mới truyền **upstream
`box_thresh`**, không đổi pixel threshold, unclip hoặc grouping cùng lúc.
[Source DBPostProcess chính thức v3.7.2](https://raw.githubusercontent.com/PaddlePaddle/PaddleX/v3.7.2/paddlex/inference/models/text_detection/processors.py).

Resize `limit_side_len` ở mode `max` chỉ tăng trần downscale, không ép upscale.
Cả 8 ảnh hợp lệ đều 827×1170, dưới cap1280 và1600; hai cap đó có thể tạo cùng
shape. Kết quả thử `max=1600` trước không chứng minh ép upscale không hữu ích.
Probe mới truyền rõ `limit_type=resize_long`. Báo cáo ghi source H×W1170×827,
resize H×W1600×1120 từ **blank replay của đúng installed resize processor**,
không gọi đây là trace tensor network. Diagnostic replay không cần pixel riêng
và thời gian của nó nằm trong detector_ms.
[Source predictor](https://raw.githubusercontent.com/PaddlePaddle/PaddleX/v3.7.2/paddlex/inference/models/text_detection/predictor.py),
[đối chiếu installed version/hash](pp-detector-preprocessing-research-20261016.md).

`detect_raw` chỉ thêm kwargs probe có validation; lời gọi mặc định vẫn không
truyền override. Tests kiểm tra A → candidate → A, cả candidate ném lỗi. Không
lưu geometry trên detector runtime. Mọi raw score/member được giữ trong báo cáo
private; không dùng bbox làm glyph mask hoặc cấp thêm erasure authority.

## Kết quả trên bộ riêng

Cùng fingerprint `445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`.
10 trang khai báo, 8 trang/78 nhãn hợp lệ; một duplicate và một dimension mismatch.
Đây là development/regression set đã xem nhiều lần, không held-out độc lập.
Nhãn Nhật chưa rà độc lập; 0 Việt gold hợp lệ, không clean-background gold.
Exact/CER dưới đây dùng NFKC + bỏ whitespace của harness hiện hành; không
chứng nhận giữ mọi nhịp trình bày, dịch nghĩa hoặc chất lượng nền tranh.

| Cấu hình | Inference | Vùng | Có prediction gán /78 | Exact /78 | Edit /939 | CER |
|---|---|---:|---:|---:|---:|---:|
| Baseline v20 | Fresh đã ghi trước | 132 | 62 | 35 | 269 | 28,65% |
| Upstream box_thresh .4 | Fresh đủ 8 trang | 158 | 63 | 34 | 255 | 27,16% |
| Ép cạnh dài1600 | Fresh đủ 8 trang | 117 | 62 | 33 | 237 | 25,24% |
| Bổ sung disjoint từ hai report | Replay, không inference mới | 138 | 63 | 35 | 265 | 28,22% |

Đối chiếu **mọi nhãn**, không chỉ tổng:

- Threshold .4: 6 nhãn giảm edit, 5 tăng. Multi-region assignments16 →21;
  vùng review44 →72. Nhiều vùng hơn không có nghĩa recall/precision tốt hơn.
- Ép1600: 15 nhãn giảm, 15 tăng, 2 chuỗi đổi dù bằng edit. Có5 nhãn mới exact
  nhưng mất7 nhãn exact; assignment tăng5 đồng thời mất5 nên tổng62 che sự đổi
  coverage. Không chấp nhận thay toàn bộ baseline theo CER.
- Disjoint replay: chỉ MN109-04:b02 giảm7 →3 edit; không mất nhãn assigned/exact
  hiện có. Sáu vùng bổ sung vẫn **defer/review**, không phải sáu bản dịch mới đã
  hiển thị cho người đọc. Điểm trên chấm OCR proposals, không đọc-live acceptance.

### Chi phí local đo được, chưa có percentile

CPU4 threads, 1 lượt/8 trang. Baseline là lần chạy trước, không randomized A/B;
không có translation, native transport, browser paint hoặc peak-RSS trong số đo.

| Cấu hình | Detector lạnh | Detector warm/trang (7 trang) | OCR warm/trang |
|---|---:|---:|---:|
| Baseline đã ghi |23,11s|1,19–1,39s|5,64–14,44s|
| Threshold .4 |22,95s|1,41–1,62s|7,38–21,24s|
| Ép1600 |23,66s|3,39–3,70s|7,49–13,91s|

Phục hồi disjoint hiện cần hai report inference. Replay không có latency live;
không lấy thời gian đọc JSON làm tốc độ detector. Nếu làm hai pass lúc đọc sẽ
phải trả thêm detector/OCR và RAM, nên chưa tự bật hoặc quảng cáo real-time.

## Thuật toán source-preserving đã thêm

`scripts/probe_disjoint_recovery.py` chưa được gọi trong native pipeline:

1. Chỉ nhận hai report cùng fingerprint/gold/page coverage, cùng engine/layout/
   partition/scope; secondary phải là comparator resize-long đo thật. Kiểm tra
   raw polygon/score/member đúng nguồn, không member trùng hoặc ngoài ảnh.
2. Giữ nguyên tất cả primary record, source key, order, reader exclusion và
   speaker/listener confirmation. Không chép binding vào geometry mới.
3. Chỉ nhận bbox secondary hoàn toàn không giao primary, exclusion hoặc proposal
   đã nhận. Không nối một cột mới vào union cũ; không thay câu đã có.
4. Tối đa8 proposal và tổng64 vùng; proposal trùng/reader-owned/vượt budget có
   quyết định riêng, không bị coi là chữ vô nghĩa hoặc biến mất khỏi evidence.
5. ID recovery riêng, exact source members và OCR giữ nguyên; unknown speaker,
   overlay label nhưng `action=defer`, `review=true`, `memory=false`, không balloon
   hay erasure. Đây là review nguồn thứ cấp, không phải semantic filtering.
6. New proposals append order cho diagnostic; chưa xác minh thứ tự đọc toàn trang,
   chưa có UI mới hoặc quyền tự phát hiện speaker. Không dùng report này làm cache
   translation hay story history.

### Rà ảnh thật tìm thấy lỗi ngoài 78 nhãn

Đã xem nguyên trang04,06,08 và crop phóng lớn **trong RAM** của MN109-08,
ROI `[86,610,76,65]`. Candidate r008 `[95,619,57,45]`, raw score≈.7103,
bắt vào nét tán cây/hatch; ở crop không thấy glyph đọc được. Đây là quan sát
visual của agent, chưa là nhãn non-text độc lập đã được người đọc xác nhận.
Nó đủ để **không promote**: detector score cao, OCR nonempty và không regression
trên nhãn thiếu coverage không chứng minh đúng chữ.

Không hardcode bỏ ROI/trang này hoặc dạy model bằng prediction của nó. Proposal
vẫn có source/member/review trong report, không xóa nét cây hoặc lưu thành event.
Cần bộ role/action + no-text negatives độc lập để calibration; morphology hay
mật độ chữ một mình không xác định được tầm quan trọng hoặc đúng/sai ngữ nghĩa.

## Harness và kiểm thử

`scripts/compare_page_reports.py` đối chiếu fingerprint, đủ page/label identity,
reference không đổi, region assignment không dùng hai lần; tự tính lại edit từ
evidence. Báo cả gained/lost, regressions và chuỗi khác cùng edit count. Output
summary không copy thoại; `automatic_promotion=false` luôn vì metric không thay
được review manga/translation/artwork. Bản JSON mới chỉ được ghi private trong
artifacts, không overwrite evidence cũ.

- Suite cuối: **1256 Python pass /1 skip**, 36,28s; skip symlink Windows đã có.
- **58 TypeScript pass**, typecheck/build qua. Build extension không đổi:
  `0.1.0-dev.ae423bfce5e4`. Không cập nhật frozen companion/Edge cá nhân.
- Test có A/candidate/A và error isolation; invalid parameters fail trước inference;
  single-variable probes; raw member/score retention; unknown/reader exclusion/
  source keys; source geometry/64-region budget; không auto-memory/erasure.
- Pytest default ban đầu gặp ACL thư mục tạm cũ; dùng basetemp mới trong artifacts
  và chạy lại toàn suite, không đổi ACL, không bỏ test để lấy pass.
- Không ảnh/crop/mask/PNG trên đĩa từ lượt kiểm tra này. Báo cáo text/geometry riêng
  gitignored, không đưa vào package hoặc dataset training.

Evidence private: `private-pages-pp-box040-candidate-20261016.json`,
`private-pages-pp-force1600-candidate-20261016.json`,
`private-pp-box040-comparison-20261016.json`,
`private-pp-force1600-comparison-20261016.json`,
`private-disjoint-recovery-final-20261016.json`.
Lượt .4 đã ghi exact source members/scores của mọi raw line qua grouping; phần
raw list riêng được bổ sung vào probe sau khi process .4 đã khởi động, nên không
gọi artifact đó là report có raw-list trace riêng như lượt forced1600.

```powershell
.venv\Scripts\python.exe -B scripts/benchmark_pages.py --folder '<bo-rieng>' --detector-box-threshold 0.4 --output artifacts/<candidate-moi>.json
.venv\Scripts\python.exe -B scripts/benchmark_pages.py --folder '<bo-rieng>' --detector-resize-long 1600 --output artifacts/<candidate-moi>.json
.venv\Scripts\python.exe -B scripts/compare_page_reports.py --baseline artifacts/<baseline>.json --candidate artifacts/<candidate>.json --output artifacts/<comparison-moi>.json
.venv\Scripts\python.exe -B scripts/probe_disjoint_recovery.py --folder '<bo-rieng>' --baseline artifacts/<baseline>.json --candidate artifacts/<forced-resize>.json --output artifacts/<replay-moi>.json
```

## Bước tiếp theo chưa được thực hiện

Không chuyển sang training dataset lớn để che lỗi này. Trước hết rà label và
coverage của vùng chưa có nhãn (text vs art, SFX, punctuation, scene text), giữ
proposal uncertain. Sau đó đo selective recovery/recognizer trên crop có đúng
ownership; chỉ calibration bằng tập có nhãn độc lập, không token probability hay
“câu Nhật có vẻ tự nhiên”. Vẫn ưu tiên chất lượng input cho cloud translation;
không quay sang tối ưu model dịch local hoặc thuê GPU/fine-tune trong lượt này.

Default OCR/layout vẫn ở mức35/78 trên bộ hiện tại, chưa đạt chất lượng tổng thể
người đọc yêu cầu hoặc lỗi dịch nghiêm trọng≤2%. Không chứng nhận MVP đã hoàn thiện.
