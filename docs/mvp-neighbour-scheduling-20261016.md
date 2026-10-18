# MVP: giữ context giữa các crop, không đổi quyền nguồn

Ngày xác minh: 2026-10-16. Desktop Windows + Edge/Chrome; không mở rộng mobile.
Lượt này có thay đổi **pipeline đang chạy**, không chỉ ghi chú nghiên cứu.
Không gọi API trả phí, không đổi key, bộ nhớ truyện, cấu hình hoặc đăng ký
Native Messaging của profile Edge cá nhân. Ảnh/crop/screenshot chỉ trong RAM;
các báo cáo chứa text riêng ở `artifacts/` được gitignore.

## 1. Đã đưa vào runtime

`companion/manga_live/translation_schedule.py` triển khai
`translation-schedule-v1-seam-neighbours`, được gọi bởi `Pipeline.process`.

Lỗi đã tái hiện ở seam thật Pipeline → translator, với SQLite thật và ảnh tự
tạo: hai cột có quan hệ crop được kiểm tra pixel bị giới hạn batch cố định
chia sang hai request. Test ban đầu đỏ với `[[other, right], [left]]`, sau sửa
xanh với `[[other], [right, left]]`. Đây là test cấu trúc request; reply OCR và
dịch trong test là fixture, không phải chứng nhận OCR hoặc tiếng Việt.

Thuật toán quy hoạch động chọn biên request ít cắt quan hệ crop nhất, rồi ưu
tiên ít lệch biên cũ, batch nhỏ và kết quả xác định. Giữ nguyên số batch của
lịch cũ, thứ tự nguồn và chính các object nguồn. Request đầu không vượt cấu
hình cũ 2/4 vùng; request sau tối đa 6; toàn job tối đa 64 nguồn. Không có lợi
hoặc evidence không hợp lệ thì giữ lịch cũ.

Chỉ nhận quan hệ có hai ID nguồn đã biết, hướng viết hợp lệ, coverage được
giữ và `erasure_permitted=false`. **Quan hệ crop không chứng minh cùng câu,
cùng người nói, hay cho phép xóa tranh.** Bản sửa không gộp region/anchor,
đổi OCR, xóa dấu, đổi render box, nâng trust bộ nhớ hoặc sửa speaker unknown.

### Replay dữ liệu thật, không gọi inference mới

Replay báo cáo production hiện có trên 8 trang / 132 region:

| Request đầu | Điểm cắt quan hệ trước → sau | Batch trước → sau |
|---|---:|---:|
| 4 vùng (mặc định) | 1 → 0 | 36 → 36 |
| 2 vùng | 2 → 0 | 40 → 40 |

Mọi nguồn vẫn giữ thứ tự và identity. Ở cấu hình mặc định chỉ một trang đổi
lịch `[4,4,4,4,4,4,4]` thành `[4,4,4,5,3,4,4]`. Các con số là batch của replay
trước bỏ vùng trống/deferred và trước retry, **không phải số request API đã
chạy hoặc bảo đảm giá token không đổi**. Chưa đo cải thiện ngữ nghĩa tiếng Việt
hoặc latency dịch từ thay đổi này. Không lấy thời gian tính lịch làm tốc độ
end-to-end.

### Cache và reader locks

Không đưa version scheduler vào khóa page cache: trang dịch đã được chấp
nhận vẫn đọc lại được, không buộc trả phí dịch lại chỉ vì đổi lịch request.
Cache hit giữ provenance lịch đã sinh bản dịch, không gắn nhãn phiên bản mới
cho kết quả cũ. Batch checkpoint vẫn khóa theo membership/context chính xác,
nên nhóm thay đổi không dùng nhầm checkpoint cũ. OCR cache, source keys,
cutoff và speaker confirmations không thay đổi. Kết quả mới có
`scheduleVersion`; status native trả version hiện hành để QA đối chiếu.

## 2. Thử Baberu, không đổi mặc định

Đã thêm comparator độc lập, không nối vào MVP hay đóng gói cùng companion:

- `scripts/install_baberu_probe.py`: chỉ tải data/ONNX/vocab/license đã pin,
  kiểm tra kích thước và SHA-256; không tải executable custom code.
- `scripts/baberu_probe_engine.py`: host loop ONNX local đã đối chiếu interface
  gốc; CPU 4 threads, whole-crop 224×224 và decode settings công bố; giữ output
  punctuation/whitespace và ghi cảnh báo decode riêng.
- `scripts/benchmark_baberu_probe.py`: cùng ảnh/crop với baseline, không dùng
  ground truth để chọn output hoặc routing, không lưu ảnh.

Nguồn: [Baberu của tác giả](https://huggingface.co/genshiai-daichi/baberu-ocr),
revision `fdf292a15dae9f5af37dd76bb408679dc4bcdfe4`;
[interface tham chiếu](https://huggingface.co/genshiai-daichi/baberu-ocr/blob/fdf292a15dae9f5af37dd76bb408679dc4bcdfe4/onnx_infer.py).
Model/code khai Apache-2.0; chưa phê duyệt provenance corpus hay phân phối lại.
Các checksum của khoảng 122 MB weights và vocab/license nằm trong installer.
Inference không tải thêm gì.

| Điều kiện cùng crop | manga-ocr hiện tại | Baberu comparator |
|---|---:|---:|
| 78 crop theo nhãn: normalized exact | 48/78 | 46/78 |
| Crop theo nhãn: CER | 9,37% (88/939) | 11,08% (104/939) |
| 132 crop nguồn production: normalized exact | 35/78 | 34/78 |
| Crop nguồn production: CER | 28,65% (269/939) | 27,80% (261/939) |

Trên crop production: 7 nhãn giảm lỗi, 8 nhãn tăng lỗi, 3 nhãn đổi chuỗi dù
cùng edit count; coverage không đổi. CER tổng giảm không bù được regression
exact/ca thật, nên **giữ manga-ocr**. Đây là phép thay recognizer trên crop cố
định, không phải một lượt detector/pipeline/overlay mới.

Timing crop Baberu trong một lượt CPU: GT-crop p50 392 ms, p95 473 ms; crop
production p50 368 ms, p95 435 ms. Load model khoảng 1,84 s ở lượt GT-crop.
Không phải p95 nhiều phiên, tốc độ trang hay hứa hẹn real-time. Không dùng
timing này để thay ưu tiên cloud-first hoặc bật thêm model khi người đọc dịch.

Một prototype tìm seam theo shared span cũng đã thử trên cả 8 trang nhưng
không đổi crop nào. Đã gỡ prototype khỏi production; không tính là nâng chất
lượng được giao.

## 3. Học gì từ các dự án khác

[Nghiên cứu pipeline đã đối chiếu source](utterance-pipeline-research-20261016.md)
đọc Kites tại `4acebe6dd3bd253aafaf38b24d849f9b40ba94e0` và
manga-image-translator tại `d6de6ab62a7be6afc0d07a3184149cdefbcd32f2`.
Điểm áp dụng là tách nguồn thành viên khỏi context nhóm và geometry render.
Lượt này tự triển khai lịch request phù hợp contract của ta, không sao chép
engine GPL hay bật merge/inpaint chưa được chứng minh an toàn.

Commercial Manga Scan/Scan Translator không công khai đủ engine/corpus để
kết luận họ dùng thuật toán nào. Không coi ảnh marketing hoặc scanlation đã
qua cleaner/typesetter/QC thủ công là bằng chứng tự động live hoàn hảo.
[Nghiên cứu OCR/dataset và giới hạn](manga-accuracy-research-20261016.md).

## 4. Kiểm thử cuối cùng

- Python: **1.275 passed, 1 skipped**, 43,18 s, sau thay đổi bảo toàn cache.
- TypeScript: **59 passed**; `npm run typecheck` và build MV3 thành công.
- Build extension: `0.1.0-dev.6d51b1c6f62b` trong `dist/extension`.
- Launcher development Windows: handshake + verify-runtime qua Native
  Messaging thành công, profile dữ liệu QA cách ly, không nạp model/API.
- Edge cách ly qua Playwright: đúng options URL/title, không blank/framework
  overlay, console sạch, điều hướng Cài đặt/Thư viện, runtime/version khớp
  source; host QA tạm được gỡ sau test. Screenshot RAM desktop đã xem.
  Browser plugin không có; dùng script Playwright sẵn của repo. Viewport desktop
  1280×900; giữ thêm regression 390×844, không tuyên bố mobile sẵn sàng.

Runtime package đã xác minh cuối:
`pkg-sha256:a0af548417d09d91c074b9c5f9fddee6fb415385eafd8ab8e387006639faa40e`.
Launcher development đọc source hiện tại; không suy rằng bộ portable/frozen cũ
đã được cập nhật. Không promote release hoặc sửa Edge cá nhân trong lượt này.

Các lệnh chính:

```powershell
.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --basetemp artifacts/pytest-mvp-schedule-cache-safe-20261016 -q
npm run check
.venv\Scripts\python.exe -B scripts/native_smoke.py --handshake-only --launcher --verify-runtime
node scripts/browser-pipeline-smoke.mjs --direct-source --connect-only
```

Lệnh Edge cần quyền ghi host QA tạm vào HKCU và tự gỡ; không đổi registration
extension cá nhân. Connect-only không chạy OCR/dịch hay chứng minh overlay
trên manga thật hoặc cài đặt Windows sạch. Evidence text trong temp QA và
artifacts riêng; không đưa transcript/ảnh vào tài liệu này.

## 5. Gate còn chưa đạt

Production OCR vẫn **35/78 normalized exact**, 62/78 assignment, CER 28,65%.
8 trang đang dùng lặp lại là development/regression set, không phải held-out.
Bộ gốc có ảnh trùng/kích thước lệch; nhãn Nhật chưa rà độc lập, 0 Việt gold hợp
lệ và không có clean-background gold. Không có cơ sở chấm lỗi nghiêm trọng
≤2%, khẳng định xưng hô hoàn hảo, tranh phục hồi đúng hoặc đạt SLA live.

Ưu tiên tiếp theo vẫn là lỗi crop/ownership đã quan sát, thử selective OCR trên
ca thật mà không mất coverage, rồi kiểm tra dịch Việt và dàn chữ bằng nhãn phù
hợp. Source-preserving utterance assembly vẫn là candidate chưa bật; không
promote chỉ vì ít thẻ hơn. Lượt này sửa một nguyên nhân context bị cắt, không
thể coi là hoàn thiện toàn bộ MVP hay chữa lỗi profile Edge cá nhân.
