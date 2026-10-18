# Chạy thử MVP cloud · 2026-10-16

**Bản development để thử trên máy hiện tại**, chưa phải bản store/Windows sạch.
Mốc MVP hiện tại chỉ Windows + Edge/Chrome; tạm gác phát triển điện thoại.
Các test responsive cũ vẫn được giữ, không có nghĩa bản mobile đã đạt nghiệm thu.
Tạm dừng tối ưu model local. Mặc định cloud dịch text, OCR local. Có thêm OCR crop
cloud **thử nghiệm, opt-in riêng**, chưa chứng minh tốt hơn trên toàn bộ mẫu thật.

## Mở demo

1. Vào `edge://extensions`, Reload extension từ `D:\Projects\Live translation\dist\extension`.
   Build **`0.1.0-dev.ae423bfce5e4`**. Reload cả trang đọc/options cũ.
2. Nhấp đúp `deliverables\Start demo.cmd`, hoặc vào <http://127.0.0.1:65303/chapter/1> trong Edge.
   Launcher chỉ mở localhost, không tự bật dịch/gọi API/đọc key/đổi đăng ký companion.
3. Quay lại tab manga rồi bấm biểu tượng extension để mở popup. Chọn BYOK →
   OpenRouter → DeepSeek V4.1 Flash. Giữ key đã lưu nếu hợp lệ; xác nhận truyện/chapter
   và bắt đầu. Trang Cài đặt không đoán tab trước đó; nếu chưa có tab đọc, nút bắt đầu
   bị khóa và có hướng dẫn quay lại manga. Popup khóa tab/URL đã xác nhận; đổi trang
   trước hoặc trong khi chờ companion phải xác nhận lại, không áp context cũ.
4. Alt+T xem gốc; bấm chữ để sửa OCR. Thử cuộn, resize, đọc lại để kiểm tra cache.

Trong Dịch ngay có **Chuẩn bị engine · không tốn credit**: chỉ nạp engine trên máy,
không gửi ảnh/text/API; lần đầu vẫn tốn thời gian/RAM. Lỗi cho phép bấm thử lại,
không tự lặp. Mở Options hoặc lưu cấu hình không tự nạp engine hay tính phí.
Popup đọc vẫn chuẩn bị engine khi cấu hình đã đủ; đây không phải dịch trước bằng API.

Nếu muốn thử tuyến OCR cloud vừa đo: Cài đặt → BYOK/OpenRouter → Nhận chữ →
Gemini Flash-Lite, xác nhận riêng gửi crop và phí OCR, giữ đồng ý gửi text/context,
Lưu cấu hình rồi bắt đầu lại. Không đổi detector mặc định; OpenCV chưa đạt cho manga.
Lưu key/cấu hình không gọi API. Chế độ này không chạy manga-ocr, nhưng vẫn phải tải
detector local lần đầu. Xem [đánh giá OCR cloud và chi phí](cloud-image-ocr-results-20261016.md).
Không bắt buộc bật; mặc định vẫn giữ ảnh trên máy.

Server thử riêng trước đó có <http://127.0.0.1:65303/private-reader> với MN109-08
do người dùng cung cấp; chỉ dùng khi phiên server đó còn chạy. Không phát dataset
ra LAN. Restart bằng launcher chỉ nạp ảnh tự tạo, không tự nạp bộ manga riêng.
HKCU Edge thật đã đọc được và trỏ đúng manifest trong `dist/windows`; origin vẫn
`epcjjhbilmmmbojldhnfblgmgiamajpl`. Chưa xác minh kết nối trong Edge cá nhân.
Companion là development launcher, cần `.venv`, source và model OCR hiện có.
Chẩn đoán mới: Edge cá nhân vẫn báo NOT_FOUND sau reload ở đúng build
`beea32c92a47`; không còn căn cứ đổ lỗi build cũ. Probe Edge tạm qua bridge production
ở build mới `ae423bfce5e4` cũng kết nối, engine vẫn cold. Chưa kết luận nguyên
nhân trong profile cá nhân. Xem [đối chiếu kết nối](native-host-diagnosis-20261016.md).

## Thay đổi dàn chữ

Giữ chữ tích hợp trong bóng khi đủ chỗ và có erasure an toàn. Vùng chồng nhau,
không fit ở cỡ sàn hoặc thiếu erasure an toàn giữ tranh gốc, đưa **đủ text, đúng ID**
vào bảng đọc cạnh trang. Đây là fallback rõ ràng, **không phải nghiệm thu scanlation**.
Bảng thu gọn được; số tại nguồn mở đúng bản dịch rồi có thể xem/sửa OCR. Chỉ hiện
vùng nguồn trong viewport. Màn hình hẹp dùng drawer và không để lớp chữ dịch khác
bị đè phía dưới. Không gộp/sửa source key, speaker binding hay memory để chữa layout.
Xem gốc ẩn toàn subtree đồng bộ; text/patch cập nhật chỉ hiện sau khi định vị/clip.

## Số đo và chi phí mới

Companion thật qua framing → detector/OCR local → DeepSeek, bốn bóng tự tạo:

| Lượt | Đến native result | Riêng dịch cloud |
|---|---:|---:|
| Cold | 39,32 s | 2,09 s |
| Warm, page ID mới | 5,35 s | 1,73 s |
| Cache | 32,05 ms | Không request |

Không phải browser E2E/p95. Cold gồm detector/import/load 28,55 s, OCR 8,61 s.
Không gọi là tức thì. Đây là baseline text-only trước khi có xác nhận gửi ảnh.

Lượt mới Gemini OCR crop + DeepSeek, bốn bóng tự tạo qua companion thật: cold
**25,55 s**, warm **4,76 s**, cache **30,99 ms**. Riêng detector cold **20,35 s**;
không phải E2E browser/p95 hoặc so sánh engine có điều kiện kiểm soát. Dàn chữ từ
chính output này được replay trên Edge riêng desktop/mobile: không lồi chữ Nhật,
không chồng/tràn, xem gốc/dừng khôi phục đúng pixel. Chưa xác minh Edge cá nhân.

Lượt **browser E2E thật mới**, MV3 -> Native Messaging -> detector -> Gemini OCR
crop -> DeepSeek -> dàn chữ, không replay/native giả lập:

| Lượt | Browser báo hoàn tất | Riêng native |
|---|---:|---:|
| Cold, 4 bóng | 25,624 s | 25,221 s |
| Warm, page ID mới | 6,196 s | 5,893 s |
| Cache cùng trang | 319 ms | 2,420 ms |

Browser dùng polling hoàn tất 250ms; đây không phải phép đo first paint/p95 và
chưa chứng nhận cache p95 <200ms. Warm có cache token **phía provider** nhưng
không phải cache dịch local. Cả 4 vùng tích hợp, cuộn không lệch, 390px không
tràn ngang, console sạch, QA host gỡ sau chạy. Một trang tự tạo không chứng minh
chất lượng manga hay UX activeTab của bản cài cá nhân. Ảnh lượt E2E không xem
được do pipe RAM bị Windows từ chối; không lưu ảnh hoặc tính thêm phí để chụp lại.
Replay từ output cloud native trước đó đã được xem lại trong RAM desktop/mobile
và vẫn qua cổng chữ Nhật dư, fit, pixel gốc. Không đánh tráo replay với E2E mới.

Pilot text tự tạo 4 nhóm/model: DeepSeek, Haiku, Gemini Lite đều accepted/check hẹp
4/4; Qwen accepted 4/4, check 3/4. Trung vị response lần lượt 1,58/2,28/2,18/2,94 s.
Không chấm mù nghĩa Việt, không đủ xếp hạng manga; giữ default DeepSeek hiện có.
Hai harness mới có trần tổng 0,13 USD trong hạn mức 0,50 USD, reservation 0,0673507 USD.
18 request, provider-reported tổng **0,006987998 USD**, chưa phải hóa đơn đối soát.
Các số trên là lượt text-only cũ. Sau khi người dùng cho phép ảnh: đã gửi crop/trang
mẫu riêng qua OCR cloud, không gửi gold hay tra cốt truyện. Tích lũy reservation hiện
**$0,496429** trong $0,50, gồm mọi lỗi mạng/unknown billing; provider báo thành công
**$0,055663252**, chưa đối soát hóa đơn. Còn $0,003571 reservation; không đủ một
lượt pipeline mới theo mức dự trù hiện tại. Không coi request lỗi là miễn phí.

Đây là **hạn mức test tự đặt**, không phải bằng chứng tài khoản/key hết tiền.
Khoản dự trù giữ cả trần input/image/output của request đã thành công và các lần
không biết billing; vì vậy nó lớn hơn tổng usage thành công được provider báo.
Không tự giải phóng khoản chưa đối soát hoặc reset ngân sách. Lượt sửa desktop
hiện tại không gọi cloud, không tăng reservation hoặc chi phí được báo ở trên.

## QA và giới hạn

- Lượt cuối: **58 TS/typecheck/build qua**; Python full gần nhất **1204 qua, 1 skip** (31,98 s),
  gồm cap 3.000 ký tự đồng bộ native/extension và test biên.
- Regression desktop mới: tab/URL đã xác nhận phải khớp trước request native,
  tab đổi/đóng trong khi chờ hoặc khi inject bị từ chối; content không xác nhận
  bắt đầu thì xóa session mới, không lưu cấu hình. Target tạm không vào story/cache.
- `npm run test:desktop`: React production 1280×900, engine chuẩn bị/lỗi/thử lại,
  chặn click trùng, start chỉ một operation có target, thiếu tab đọc được giải thích;
  không gọi image/text/metadata/settings do chuẩn bị engine. Ảnh đã xem trong RAM.
  Native được mock; test không chứng nhận inference hay kết nối profile cá nhân.
- Test Python cloud warmup riêng qua lại: không khởi động LLM local/gọi provider.
- Options và connection UI QA qua: save không inference/charge, status lỗi/chờ,
  CSP, retry, late reply, private diagnostics. Script connection đã chuyển ảnh sang
  RAM-only; 6 PNG giao diện giả lập của lượt trước đã xóa đúng tên, không đụng dataset.
- Full reader UI 1280/760/390 px qua: cuộn/nested scroll, resize/object-fit, sửa OCR,
  review/reader lock, retry, stale context, prefetch ≤2, nguyên bản/late patch, console.
  Native/API giả lập; Browser plugin không có nên dùng Playwright/Edge riêng.
- Output native/cloud mới được render lại: 4 bóng desktop/mobile, ID/text, không
  glyph Nhật lồi/chồng hộp, original/stop khớp pixel. Browser transport là replay.
- MN109-08 replay desktop: hết giao nhau, bảng đọc đủ chữ/không xóa tranh,
  collapse → marker → source detail qua, held RAF ẩn ngay; original/stop khớp pixel.
  Không phải fresh OCR sau sửa renderer và không nghiệm thu nghĩa/clean background.
- **Mobile private exact-pixel FAIL:** 14 pixel lệch tối đa 1 mức màu cả sau stop,
  dù so cùng source/viewport geometry. Chưa kết luận compositor hay renderer;
  giữ gate, không nới tolerance để gọi đạt. Hoãn xử lý theo phạm vi desktop mới.
  Đối chứng mới: 4 vòng raw scroll/return trước khi nạp extension khớp pixel và
  cùng geometry, nhưng sau bật/tắt vẫn lệch đúng 14 pixel. Chưa đủ chứng minh
  lỗi chỉ do screenshot/compositor; không sửa production hoặc hạ gate theo phỏng đoán.
- OCR còn thêm `「` ở 2 câu tự tạo; giữ review/source, không strip toàn cục.
  Đây là baseline manga-ocr cũ; lượt Gemini OCR native mới không có lỗi đó ở 4 câu.
  Manga riêng còn lỗi OCR/gom câu, thiếu Việt gold/nền sạch. Chưa chứng nhận
  perfect, ≤2% lỗi nghĩa, frozen companion, Edge cá nhân hoặc máy sạch.

Ảnh QA chỉ RAM. Evidence text riêng trong `artifacts/` (không ship):
`cloud-mvp-model-pilot-20261016/cloud-benchmark.json`,
`authored-cloud-native-20261016-budget001.json`,
`authored-render-mvp-cloud-20261016.json`, `reader-ui-mvp-cloud-20261016.json`,
`private-reading-fallback-20261016-final.json`,
`private-reading-fallback-mobile-20261016.json`.

Evidence mới: `cloud-image-*/report.json`, `cloud-image-native-20261016/result.json`.
Lượt browser/cost mới: `cloud-image-browser-20261016/report.json`.
Cloud crop benchmark Gemini đủ 78 nhãn: **39/78 exact, CER 13,31%** theo nhãn cung cấp;
chưa vượt local, có nhãn nguồn cần rà. Không tuyên bố perfect hoặc tự đổi default.
