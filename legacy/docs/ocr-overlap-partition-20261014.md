# Crop OCR dính cột — guarded production partition

## Kết quả đã đo

`scripts/probe_overlap_crop_partition.py` tách **hộp inference** tại khoảng trắng giữa hai crop cột/dòng chồng nhau. Hộp nguồn, thứ tự, ID và source-key không đổi. Không ghép/sửa chuỗi Nhật, không dùng gold để chọn phép biến đổi, không đổi weights/decoder và không cấp quyền xóa tranh.

Đã xem ảnh MN109-08 trong RAM: crop r004 rộng sang cột r005. Lệnh replay ban đầu với `--page MN109-08 --assert-label b02` đỏ: b02 có **5 edit**, OCR nguồn nối thành phần lời thừa. Các nguyên nhân được phân biệt: crop dính chữ cạnh bên; union có thể mất chữ ở trang khác; phép nối source không sửa được OCR; nhãn chưa được rà độc lập. Không dùng một nguyên nhân giải thích mọi lỗi.

Thử nghiệm tại seam x=311 thay riêng crop inference r004 `[302,65,43,141]` bằng `[311,65,34,141]`, r005 bằng `[283,66,28,169]`. Nhận dạng mới r004 không còn phần lời thừa; r005 giữ nguyên. Crop nguồn vẫn giữ để kiểm tra. Câu b02 chuyển **5→0 edit**. Hai crop đầu trang cũng được tách tại seam x=730; output OCR giữ nguyên.

| Phạm vi 8 trang / 78 nhãn | Baseline v16 | Crop partition |
|---|---:|---:|
| Vùng nguồn | 132 | 132 |
| Nhãn được containment gán | 62 | 62 |
| Exact trên nhãn chưa rà | 34 | 35 |
| Edit / 939 ký tự | 274 | 269 |
| CER chẩn đoán | 29,18% | 28,65% |

**10 crop inference mới**, thuộc MN109-02 (2), MN109-04 (4), MN109-08 (4); 122 crop còn lại dùng đúng output ghi nhận theo hộp nguồn. Đã đối chiếu mọi region và annotation: **chỉ MN109-08:r004 đổi text**, không có nhãn tăng edit, không có vùng ngoài annotation đổi text. ID/bbox/order/source-key của cả 132 vùng giữ nguyên. Đây là đối chứng với detector đã ghi, **không phải chạy lại toàn pipeline detector/native/cloud**.

Khác candidate gom v18 từng có cùng CER/exact: cách này giữ đủ 132 đơn vị nguồn, không tạo union/paragraph mới. Không lấy aggregate giống nhau làm bằng chứng hai tuyến tương đương về bố cục hay memory.

Lượt fresh có guard: phần crop mới trang cold MN109-02 **12,91 s** gồm import/load + 2 crop; MN109-04 **1,95 s/4 crop**; MN109-08 **1,85 s/4 crop**. Không phải latency full-page, mức tăng so runtime, p95 hoặc peak RAM. Một worker CPU 4 threads kết thúc không crash; không đóng ứng dụng reader. Không request cloud hoặc phí mới.

## Guard và hạn chế

- Chỉ crop `label`, hướng/cỡ và mốc đầu tương thích; không đụng balloon, fragment, reader exclusion hoặc speaker/listener đã xác nhận.
- Dùng dải trắng liên tục ít nhất hai pixel trên toàn chiều dài union. Đường tranh đi qua separator sẽ veto. Đây chưa phải tách glyph/furigana có hiểu ngữ nghĩa; nền tối/texture không được xử lý bằng phương án này.
- Pixel nguồn dưới mức xám 220 trong các hộp nguồn phải còn được phủ bởi các crop inference sau tách. Dấu nằm ngoài chiều dài crop hàng xóm cũng được bảo vệ. Ngưỡng này không chứng minh tất cả antialias mờ là glyph và không được dùng làm mask xóa tranh.
- Mọi output retry giữ raw record trong `sourceOcr`; không kế thừa `vi`, `expression` hoặc `ambiguous` cũ. Candidate có review và không được ghi thành plot memory; giữ source-key đã có, từ chối record legacy thiếu anchor thay vì tự tạo anchor.
- Crop trống sau retry vẫn được ghi là output trống, không âm thầm chép lại text cũ hoặc bỏ record để làm đẹp điểm.
- Toàn bộ ảnh/crop chỉ RAM. Báo cáo text nằm trong `artifacts/` gitignored; không ship dữ liệu, gold, key hoặc context reader.

**Đã promote có guard vào production path:** `Pipeline.process`, OCR cache v3 và
`scripts/benchmark_pages.py` đều dùng `partition_ocr_boxes` với phiên bản
`ocr-crop-partition-v1`. Build extension sau thay đổi là `0.1.0-dev.d07a2886be4a`.
Partition chỉ thay hộp inference trong RAM; bbox/source-key/order, speaker lock và
reader exclusion không đổi. Vùng thay hộp giữ `ocr_crop_partition`, bị review và
không được đưa vào story memory tự động. Điều này chưa sửa 4 cặp khung dàn chữ,
thẻ trắng trên tranh hay lỗi OCR khác. Dataset vẫn có 0 Việt gold hợp lệ và chưa có
clean-background/glyph gold; không đạt cổng “perfect”, không chứng nhận chất lượng
dịch hay scanlation.

## Replay production trên private 8-page set

Artifact riêng: `artifacts/private-pages-production-partition-20261014.json`.
Đây là lần chạy detector + partition + manga-ocr thật, không gửi ảnh/text lên
cloud. So với `private-pages-default-fresh-20261014-v4-scope.json`:

| Chỉ số chẩn đoán / 78 nhãn chưa rà | Baseline | Production partition |
|---|---:|---:|
| Vùng / nhãn được containment gán | 132 / 62 | 132 / 62 |
| Exact | 34 / 78 | 35 / 78 |
| CER | 29,18% | 28,65% |
| Label regression | — | 0 |
| Label cải thiện | — | `MN109-08:b02`, 5 → 0 edit |
| Crop tách / seam | — | 10 / 5 |

Độ trễ lần chạy production: trang lạnh `MN109-01` detector **59,71 s** và OCR
**8,23 s** (gồm import/load); các trang ấm detector **1,08–1,25 s**, OCR
**5,35–14,68 s**; cleanup p50 **81,22 ms**. Đây là benchmark CPU local theo
dataset này, không phải p95 toàn ứng dụng hay cam kết real-time. Kết quả vẫn chỉ
đánh giá containment/CER OCR; chưa chấm nghĩa Việt, xưng hô, nền phục hồi hoặc
chất lượng lettering.

## Kiểm thử và tái lập

25 test mới dùng pixel tự tạo: giữ source, vertical/horizontal, scale 0,5/1/1,5/2, đường tranh cắt separator, dấu ngoài crop hàng xóm, vùng near-duplicate/staggered, khóa reader, identity không duy nhất, geometry lỗi, output trống và không kế thừa plot trust. Test xanh không thay bằng chứng manga thật. Toàn Python: **979 qua / 1 skip** trong **29,62 s**; skip symlink Windows, không phải số đo tốc độ đọc. TypeScript **51 qua** và build Manifest V3 pass.

```powershell
.venv\Scripts\python.exe -B scripts/probe_overlap_crop_partition.py --folder 'C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001' --reference artifacts/private-pages-default-fresh-20261014-v4-scope.json --fresh --output artifacts/<private-output-moi>.json
```

Không chạy lại chỉ để đọc kết quả. Evidence hiện có: `private-overlap-partition-red-20261014.json`, `private-overlap-partition-mn10908-fresh-20261014.json`, `private-overlap-partition-guarded-all-fresh-20261014.json`. Lượt guarded là lượt fresh cuối; các artifact trước guard chỉ dùng lịch sử OCR, không được coi là đã có guard memory.

Bước tiếp: bổ sung Japanese gold đã rà độc lập, Việt reference và clean-background/glyph gold; sau đó mới đánh giá nghĩa/xưng hô/lettering. Partition phải luôn tính từ toàn layout, không từ batch con tùy lịch chạy; cache đã được làm mất hiệu lực bằng phiên bản, không xóa lựa chọn reader.
