# Hayai: kiểm tra resize đã kết thúc, chưa đổi OCR

2026-10-16. Chỉ harness/diagnostics; **không sửa OCR production, prompt, renderer,
model mặc định hoặc bộ cài**. Ảnh/crop/screenshot chỉ RAM. Không gọi API.

## Kết quả trên toàn bộ crop hợp lệ

| Cấu hình CPU FP32, batch 1 | Exact | Edit / ký tự | CER |
|---|---:|---:|---:|
| Manga-ocr baseline | 48/78 | 88/939 | 9,37% |
| Hayai PIL, 512 patches, lượt trước | 42/78 | 109/939 | 11,61% |
| Hayai PIL, 384 patches, lượt mới | 43/78 | 103/939 | 10,97% |
| Hayai tensor-resize-only, 512 patches, lượt mới | 42/78 | 109/939 | 11,61% |

Hai cấu hình mới đều đạt 13/13 trên mẫu tự tạo, nhưng **không vượt baseline trên
manga thật**. Không dùng gold để chọn engine theo từng crop. So với manga-ocr,
tensor-resize-only giảm edit ở 10 crop, tăng ở 20, bằng ở 48. Đã đối chiếu toàn
bộ prediction, gồm những lỗi thêm dấu câu, đọc dấu chấm thành chữ, lặp và mất chữ;
không bỏ các ca này khỏi metric. Nhật gold chưa được rà độc lập nên đây vẫn là
metric chẩn đoán, không chứng nhận bản dịch.

Tensor resize có thay đổi input ở 64/78 crop, nhưng cả 78 raw prediction và edit
đều **giống Hayai PIL 512**. Spatial/mask giữ nguyên ở cả 78; max absolute pixel
tensor difference 0,0078431964; trung bình mean-absolute-difference theo crop
0,00000482054. Thử nghiệm không ủng hộ việc dùng riêng kernel resize như lời giải
cho khoảng cách CER trong môi trường này. Không kết luận mọi runtime Hayai/Fast
đều tương đương: đây **không phải chạy torchvision/Fast đã xác minh parity**.
Xem [phân tích processor](hayai-processor-parity-20261016.md).

Fingerprint nguồn không đổi:
`445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`.
Vẫn 8 trang/78 nhãn đủ điều kiện cấu trúc, một trang lệch kích thước và một ảnh
trùng không vào partition; 0 Việt gold dùng được, không có clean-background gold.
Không sửa dataset, nguồn OCR hoặc nhãn để cải thiện điểm.

Lượt tensor-resize-only: load 11,59 s; p50 crop 1,452 s, p95 crop 1,852 s;
peak working set khoảng 1.214 MiB. Chỉ process comparator và crop cấp sẵn,
**không detector, không extension latency, không p95 nhiều phiên**. Socket guard
Python ghi 0 lần thử kết nối; không phải trace mạng toàn máy. Lượt 384 patches
riêng có p50 1,180 s / p95 1,580 s, không dùng nó làm bằng chứng đọc real-time.

## Quyết định

Không promote cả hai ứng viên, không chạy full-page chỉ để có thêm test xanh,
không thêm fallback hai OCR tự động, không thay dependency production. Giữ
manga-ocr; grouping, bản dịch và dàn chữ vẫn là các cổng chưa qua. Mẫu tự tạo
không thể thay tập thật hoặc điểm nghĩa Việt được rà độc lập.

Script mới `scripts/probe_hayai_tensor_resize.py` chỉ đổi resize, giữ nguyên
NaFlex geometry, PIL normalization/patch order/padding, weights/tokenizer và
generation. Trường thống kê `values_above_1e6` trong artifact ban đầu đếm
**chênh lệch >1e-6**, không phải >1e6. Đã sửa tên thành
`values_above_1e_minus_6` cho lượt tương lai và thêm test; không sửa artifact
gốc hay giả vờ inference đã chạy lại sau đổi tên.

Evidence text private nằm trong `artifacts/`, không ship:

- `private-hayai-nova-crops-384-20261016.json`
- `hayai-nova-tensor-resize-authored-512-audited-20261016.json`
- `private-hayai-nova-tensor-resize-512-20261016.json`

## Kiểm tra lại renderer: vẫn thất bại

Replay MN109-08 ngày 2026-10-16 dùng source/translation đã ghi và cleanup local,
không inference/API mới. Cổng `--assert-no-lettering-overlap` vẫn **FAIL**:
r000/r001 17×118 px, r001/r003 13×61 px, r004/r005 19×140 px. Ảnh RAM đã xem:
hai cụm cột Việt chồng thật và thẻ trắng dài bên trái vẫn rõ. Không có bản vá
dàn chữ trong lượt này. Trước đây có 4 cặp; current-scope defer dấu chấm cần
review nên còn 3 cặp, **không phải đã sửa lỗi còn lại**.

Đã kiểm tra ba giả thuyết qua cùng replay: bbox nguồn đã chồng theo chiều ngang
13/11/16 px ở ba cặp; `lettering_box` nới thêm thành 17/13/19 px. Vì vậy bỏ riêng
phần nới `source_size*3` cũng không giải quyết được nguồn bị chia thành các cột
giao nhau. Scroll transform qua và không giải thích các giao nhau đã có ở tọa
độ nguồn. Cần giải quyết đơn vị thoại/presentation giữ nguồn, không chỉ đổi z-index,
clip chữ hoặc ép font nhỏ. Đây là chẩn đoán trên output cũ đã ghi, **không phải
một lượt production detector/OCR mới sau partition**.

URL/title/nonblank, ID/wording, giữ tranh ở vùng review, cuộn, conceal trước RAF,
khôi phục đúng hash pixel nguồn khi xem gốc/dừng, console và không request ngoài
localhost đều qua. Đây là Edge headless cách ly (Browser plugin không có),
1280×900, nguồn native-size 827×1170; **không xác minh Edge cá nhân**, responsive
layout, fresh translation hoặc chất lượng cleanup toàn trang. Không truy cập
lại surface extension đã bị chặn. Bằng chứng:
`artifacts/private-overlap-repro-20261016-before-layout.json`.

Lượt cloud được đồng ý tối đa 0,01 USD đã kết thúc ở evidence
`authored-cloud-native-20261015-budget001.json`: cold 50,890 s, warm 6,370 s,
cache 37,41 ms tới native result; provider-reported 0,0021822 USD. Không phải
thời gian hiện chữ trong Edge hay p95. OCR vẫn thêm ngoặc giả ở hai câu tự tạo;
xưng hô unknown vẫn dao động. Không sửa bằng cách xóa dấu câu hay ép giới tính.
Không còn hạn mức thử mới từ lần đồng ý đó.

## Kiểm thử phần mềm sau thay đổi harness

40 test Hayai/comparator qua; toàn bộ Python **1167 pass, 1 skip** trong 31,75 s;
`npm run check` qua typecheck, **54 TS tests** và build. Các số này kiểm tra hợp
đồng phần mềm, không biến cổng manga/render còn đỏ thành xanh. Không package,
thay registry, thay cài đặt, gọi cloud mới hoặc xác nhận Edge cá nhân.
