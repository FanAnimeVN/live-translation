# PP detector: preprocessing và ngưỡng thực sự — 2026-10-16

Phạm vi: đọc mã đang cài + nguồn chính thức; không inference, tải model/dataset, gọi cloud hoặc thay runtime default. Đây là follow-up hẹp cho `manga-accuracy-research-20261016.md`, không phải kết quả tăng chất lượng.

## Kết luận

- Hạ bộ lọc **sau output** từ 0,35 xuống 0,25 không tăng recall khi upstream vẫn `box_thresh=0.6`: những box đó đã bị DB postprocessor bỏ trước khi trả `dt_scores`.
- Trong bản đang cài, `predict(limit_side_len=1280/1600)` **được sử dụng**, không bị YAML `resize_long:960` vô hiệu hóa. Nhưng `limit_type=max` là giới hạn trên, **không ép upscale**. Hai cap cao hơn kích thước nguồn có thể cho đầu vào giống nhau.
- Không thấy phép gán lưu override resize/threshold giữa các lần gọi trên runner path đã kiểm tra. Đây là kết luận static, chưa phải test sequence/runtime isolation.
- Giữ default hiện hành; candidate phải thay đúng upstream parameter và ghi kích thước tensor thực tế trước khi diễn giải số đo.

## Snapshot có thể tái kiểm tra

Metadata cài đặt: `paddleocr 3.7.0`, `paddlex 3.7.2`, `paddlepaddle 3.3.1`.

| Tệp local | SHA-256 |
|---|---|
| `.venv/Lib/site-packages/paddlex/inference/models/text_detection/predictor.py` | `145d99a714a6cfa7a5d95ce823a78b218de2d1a53cdf427e26e9190c2675b0e6` |
| `.venv/Lib/site-packages/paddlex/inference/models/text_detection/processors.py` | `b23f2349e9e3439d748548730443459d7ed43a4f5e5beb04903f3e5ad58be7c1` |
| `models/detector/inference.yml` | `98069072e1b6b37d727fd9d9f11725faa46d6ea0de012f2ed26caea011c37699` |

Config local: `PP-OCRv5_mobile_det`; YAML `resize_long:960`; `thresh:0.3`; `box_thresh:0.6`; `unclip_ratio:1.5`; `max_candidates:1000`. `input_shape` không được companion truyền. Cần snapshot lại khi dependency hoặc frozen companion thay đổi; không suy diễn rằng mọi version/backend có cùng hành vi.

## Ba ngưỡng không tương đương

| Tham số | Tác động | Dùng cho comparator |
|---|---|---|
| `thresh` | Ngưỡng pixel trên probability map để hình thành binary contour | Giữ 0,3 khi khảo sát box recall; đổi nó có thể thay đổi/sáp nhập contour |
| `box_thresh` | Bỏ candidate theo điểm trung bình probability map trong polygon/box | Thử upstream `predict(box_thresh=...)` để khôi phục candidate trước đây bị lọc |
| Bộ lọc companion `dt_scores >= 0.35` | Lọc lần nữa các output **đã qua** upstream | Không thể phục hồi candidate upstream đã bỏ |

Định nghĩa API thuộc [PaddleOCR TextDetection](https://www.paddleocr.ai/v3.6.0/en/version3.x/module_usage/text_detection.html). Kiểm tra code cho thấy `DBPostProcess.process()` tạo segmentation trước, rồi `boxes_from_bitmap()`/`polygons_from_bitmap()` so `box_thresh` với score, sau đó mới unclip và trả scores. Còn size tối thiểu, candidate cap và hình học cũng có thể làm mất box; giảm box threshold không khôi phục mọi missing region. [DBPostProcess v3.7.2](https://raw.githubusercontent.com/PaddlePaddle/PaddleX/v3.7.2/paddlex/inference/models/text_detection/processors.py)

## Vì sao YAML `resize_long:960` không đồng nghĩa type-2

Installed `TextDetRunnerPredictor.build_resize()` lấy 960 từ YAML, xác định model v5 là `max`, rồi **truyền rõ `limit_side_len`** vào `DetResizeForTest`. Constructor ưu tiên key đó trước `resize_long`, nên chọn type-0. `process()` chuyển per-call override đến processor. [Predictor v3.7.2](https://raw.githubusercontent.com/PaddlePaddle/PaddleX/v3.7.2/paddlex/inference/models/text_detection/predictor.py)

Type-0 `max`: chỉ downscale nếu cạnh dài vượt cap; sau đó làm tròn mỗi chiều tới bội số 32. Type-0 cũng hỗ trợ nội bộ `resize_long` để ép cạnh dài và `min` để upscale cạnh ngắn; không tự động thay `max` thành các mode đó khi đổi số. Type-2 trực tiếp từ YAML lại ép cạnh dài rồi ceil bội số 128; **đây không phải path runner đang dùng**. [Processor v3.7.2](https://raw.githubusercontent.com/PaddlePaddle/PaddleX/v3.7.2/paddlex/inference/models/text_detection/processors.py)

Ví dụ toán học, không phải đo dataset: ảnh H×W=1000×700 dưới `max` cho 960×672 ở cap 960, nhưng 992×704 ở cả cap 1280 lẫn 1600. Vì vậy kết quả hai comparator giống nhau chưa chứng minh tăng resolution vô ích: cần biết nó có thực sự tăng tensor hay không. Cũng không được gọi `max=1600` là “upscale lên 1600”.

## Override có rò sang lần gọi sau không?

PaddleOCR wrapper chuyển `predict` kwargs đến PaddleX; base predictor chuyển tiếp kwargs vào `process`, không lưu chúng thành defaults. Batch size có mutate sampler, nên không suy rộng thành thread-safe. [PaddleOCR wrapper v3.7.0](https://raw.githubusercontent.com/PaddlePaddle/PaddleOCR/v3.7.0/paddleocr/_models/base.py), [PaddleX base predictor v3.7.2](https://raw.githubusercontent.com/PaddlePaddle/PaddleX/v3.7.2/paddlex/inference/models/predictors/base_predictor.py)

Trong installed runner/processor, `limit_side_len`, `limit_type`, `thresh`, `box_thresh` được resolve bằng biến local; không gán override vào `self` trong per-call path. Nếu comparator tự sửa `pre_tfs["Resize"]`/`post_op` hoặc constructor defaults thì đó là state mutation khác, phải restore hay dùng instance riêng. Source inspection không thay cho test A → candidate → A, gồm cả trường hợp candidate lỗi.

## Comparator tiếp theo đề xuất

1. Đóng băng baseline/config/hash; chưa sửa default trong companion hay package.
2. Thử **một biến** upstream `box_thresh=0.5` (hoặc 0,45), giữ pixel threshold/unclip/resize và post-output floor hiện hành. Không gọi nó là thử `thresh=0.5`.
3. Lưu raw polygon, raw score, effective threshold, source membership và review state; không cấp quyền erasure/memory cho vùng đáng ngờ chỉ vì tăng recall.
4. Với resize, ghi `resize_type`, `limit_type`, source H/W, actual tensor H/W và ratio. Chỉ gọi là higher-resolution candidate khi tensor thực tăng; không so hai cap tương đương rồi kết luận về upscale.
5. Thêm tests không dùng weights: kwargs đúng upstream; default không đổi; shape của synthetic dimensions; A → candidate → A không leak, cả error path. Không bypass metadata/model pinning để đạt test.
6. Trên bộ riêng, báo assigned coverage/exact/CER, missing/overmerge, low-score region count và cold/warm latency. Region count tăng không phải recall đã tăng; annotation thiếu không cho phép kết luận mọi unmatched region là false positive.
7. Không promote nếu mất nguồn, tăng overmerge/hỏng tranh hoặc chỉ đổi metric mà không kiểm tra ca thật. Không ghép threshold/resize/grouping cùng một candidate.

Không có benchmark mới hoặc tuyên bố cải thiện độ chính xác trong tài liệu này.
