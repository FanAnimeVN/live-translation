# Dàn chữ hòa vào manga

Cập nhật 2026-10-14. Ưu tiên: đúng nghĩa → hòa chữ → đọc liên tục → tính năng mới. Chưa cam kết redraw hoàn hảo mọi trang.

## Mặc định và chi phí

| Vùng | Cách xử lý | Chi phí thêm |
|---|---|---|
| Bóng thoại/narration nền phẳng có bằng chứng | Xóa theo nét chữ, đúng màu giấy/mực, chữ Việt nền trong suốt | Local, không token/credit |
| Chữ nhỏ trên tranh đủ rõ | Cleanup OpenCV có giới hạn, giữ pixel ngoài mask | Local; thêm CPU/thời gian |
| SFX, vùng lớn hoặc không tách chữ/tranh chắc | Giữ nguyên art, bản dịch dạng nhãn có thể ẩn | Không tự gọi tạo ảnh |

`artCleanup` mặc định bật ở hồ sơ mới/chưa có trường cài đặt; giữ nguyên `false` đã lưu. Lưu cài đặt không chạy dịch hoặc tính phí. Neural/cloud redraw chưa tích hợp; nếu thêm phải opt-in, cảnh báo chất lượng/độ trễ/giá và xác nhận trước thao tác.

## Bóng thoại: layout v20, giữ source footprint khi union chạm góc trống

### Bổ sung 2026-10-17: presentation v21 đã bật cho fresh Paddle

`balloon-mask-v21-actual-source-support` thử support thật của polygon detector
trước phần padding inference khi hai nhánh cũ không qua; vẫn cùng gate 8px/10%,
foreign-ink proof, interior và vùng bảo vệ. Replay native đủ tám trang tăng
vùng integrated 10 → 12, không đổi 132 nguồn/crop/OCR/scope; hai vùng mới qua
pixel QA desktop. Bốn fallback MN109-03 vẫn chưa sửa. Không coi bounding box
là glyph mask hoặc nới halo để ép qua.

`LAYOUT_VERSION` v20 giữ identity grouping/OCR/cache; presentation có version
riêng. Trang/OCR đã cache giữ geometry và provenance cũ, không bị bắt dịch lại
trả phí hoặc tự bịa source members. Native Paddle fresh bật v21; comparator
`group_regions` giữ control v20, OpenCV/cloud không tự nhận nhánh mới. Chưa
cập nhật companion cài trong Edge cá nhân. [Bằng chứng, cache và giới hạn](balloon-actual-source-support-20261017.md).

`balloon-mask-v20-source-footprint-corners` giữ nguyên grouping/merge veto v16
bên dưới. Khi union các cột dài/ngắn chạm cung viền ở một góc không chứa chữ,
chỉ thử lại nếu mọi footprint detector nguồn vẫn qua cùng giới hạn 10%/8 px
và mọi foreign ink trong union được chứng minh là outline/halo ngoài. Mask vẫn
clipped trong interior cũ, không repaint cả góc. Nhánh phục hồi chỉ chọn ink
components giao footprint, giữ nét chưa được giải thích cùng halo; nếu chúng
chiếm textBox hoặc không thể xóa đủ glyph thì fallback. Không coi detector box
là glyph mask và chưa áp dụng mask mới đại trà lên nhánh union vốn đã qua.

Fresh trên 8 trang: integrated 8 → 10, 132 vùng và OCR 35/78 exact không đổi.
Hai bóng có pixel QA trong Edge; chưa có clean-background/Việt gold hoặc
nghiệm thu toàn trang. [Bằng chứng và giới hạn v20](quality-upgrade-20261016.md).

### Nền tảng grouping v16 được giữ nguyên

Đối chứng mới nhất và lỗi còn lại: [quality review](quality-review-20261014-latest.md). Source scope v4 chỉ review dấu chấm thiếu bằng chứng ảnh, không tự xóa dấu câu hay cấp quyền xóa tranh. Gom cột chồng vùng v18 vẫn thử nghiệm; không phải engine mặc định.

`balloon-mask-v16-outer-notch-veto` giữ bbox OCR, tách vùng dàn chữ an toàn khỏi vùng xóa. Thử nghiệm v13/v14 gom chữ trên nền mở sửa được một câu nhưng gây lỗi ở các vùng khác, nên companion không bật. v15 từng khôi phục kết quả v12; v16 đã tách được trường hợp hai bóng tiếp xúc ở MN109-07 bằng viền ngoài. Đây chưa phải segmentation tổng quát hoặc redraw đúng mọi bóng nối nhau.

- Chỉ gộp khi **cùng một thành phần nền** chiếm ưu thế; không cộng nhiều nền rời nhau để nhận một bóng.
- Union nhiều crop trải quá xa được tách về các crop detector nhỏ, không bỏ tất cả cùng union. Vùng tách có cờ `layout_fragment` để người đọc đối chiếu, không tự nhận quyền xóa tranh.
- Nền nối liền không đồng nghĩa một thoại. Chỉ gom các dòng/cột lân cận theo overlap và thang kích thước chữ; các cụm xa nhau được tách, giữ bản gốc với ghi chú “vùng chữ đã tách để tránh gộp nhầm”. Chưa giải quyết mọi bóng nối nhau/chữ phụ hay mọi thứ tự panel.
- Điểm lõm ngoài chỉ veto gộp khi thành phần nền có giới hạn/đủ đặc, chữ cùng hướng, điểm lõm đủ sâu theo cỡ chữ, có gap cột/dòng thật và khối ngắn kết thúc ở điểm lõm trong khi khối kia còn tiếp. Đuôi bóng nằm ngoài toàn bộ chữ, lõm nông, viền chạm mép ảnh hoặc cut xuyên crop không tạo split. Mọi crop được giữ nguyên; fragment có review và **không nhận quyền erasure của cả nền**. Trên 8 trang chỉ một vùng gộp thay đổi; test có nền sáng/tối, chữ dọc/ngang và resize, không chứng minh mọi loại balloon.
- Nền phải có biên và đủ phẳng. Loại trừ ringing sát glyph bằng bán kính 2/3/4 px, vẫn giữ ≥20% thành phần để đo và cùng ngưỡng p95 6 mức màu. Không tìm một mảng sáng tùy ý để bỏ qua texture.
- ROI kiểm tra có vòng ngoài 8 px; writable mask vẫn bị cắt trong interior erosion 2 px, với outside local array được xem là không an toàn.
- Góc crop chỉ được ngoại lệ cho nền đồng màu hoặc outline được chứng minh: tối đa 10% crop và 8 px ngoài mặt kín. Viền/tail và vùng an toàn bị loại không được tô.
- Erasure là polygon nét chữ và halo dilation 9×9, không một tấm nền chữ nhật. Màu nền và mực được lấy từ nguồn. Trường hợp mơ hồ giữ tranh với nhãn, không âm thầm làm mất nét.

Font local Patrick Hand hỗ trợ dấu Việt; fit theo vùng an toàn và ưu tiên cỡ gần nguồn. Cỡ sàn 11 CSS px, line-height 1.25, bản dài mở đầy đủ khi bấm. Giữ ngắt đoạn, honorific, nói lắp/kéo dài/đánh vần; không ghép chữ hoặc cắt nghĩa để vừa khung. Không clone được mọi font Nhật.

## Chữ trên tranh: giới hạn local

- Crop tối đa 900 px mỗi chiều, 90.000 px² và 28% ảnh nguồn; không chạy với SFX/bóng đã xử lý/vùng cần review.
- `opencv-telea-v1`: mask lõi chữ/halo; chỉ tiếp nối texture đường song song khi profile màu giải thích ≥85% phương sai đã biết. Không phải model hiểu khuôn mặt/đồ vật, không phục hồi chắc chắn phần tranh bị che.
- PNG RGBA chỉ có alpha trong mask. Mỗi patch ≤384 KiB, tổng job ≤2 MiB, ≤64 ID trong extension.
- Patch chỉ đi bằng event `render-patch`; không vào Region, SQLite, cache text, log hay export context. Kiểm tra revision/nguồn/kích thước, hủy Blob khi dừng/đổi ảnh. Lỗi cleanup không hủy bản dịch hợp lệ.

## Bổ sung MVP cloud 2026-10-16

Vùng chồng hộp/không thể fit/thiếu erasure an toàn dùng bảng đọc cạnh trang,
không tiếp tục vẽ cột hẹp hoặc thẻ trắng trên tranh. Giữ đầy đủ từng ID/text,
nguồn gốc và khả năng sửa; không coi fallback là dàn chữ tích hợp đã đạt.
Chi tiết chạy thử, số đo mới và gate mobile còn đỏ:
[MVP cloud demo](mvp-cloud-demo-20261016.md).

## UX và bằng chứng hiện có (bao gồm các lượt lịch sử)

- Chữ/mask dùng chung transform và clip của ảnh; cuộn/nested scroll/resize không chạy lại OCR. `Xem gốc`/Alt+T ẩn đồng bộ, không chờ RAF; chữ/mask/PNG mới hoặc trả muộn bắt đầu ẩn và chỉ hiện sau khi tọa độ/clip cập nhật. Replay private đã khôi phục pixel chính xác cả khi RAF bị trì hoãn; chưa xác định nguyên nhân lỗi của inference nặng trước. Outline chỉ hover/focus; bấm để sửa OCR/tên và đọc bản đầy đủ.
- Edge QA riêng 1280/760/390 px qua UI/options/art. Browser plugin không có; dùng Playwright. Không phải Edge cá nhân hoặc điện thoại thật.
- Fixture lettering và replay bbox detector thật: tám ROI glyph còn 0 pixel nguồn desktop/mobile, exact source restoration. Bản dịch do QA cung cấp, không chấm nghĩa.
- Một bóng private được chọn thủ công: 365 pixel mực nguồn trong ROI → 0, không đổi ngoài halo; cuộn/390 px/xem gốc qua. Chỉ một bóng, không phải full-page coverage/clean-background gold.
- Source E2E mới trên trang **tự tạo** qua OCR/cloud thật, bốn bóng integrated. Ảnh desktop/mobile đã xem; còn dấu `「` ở hai câu từ OCR. Không lấy screenshot fixture đẹp làm chứng cứ model dịch đúng.
- Private toàn trang v12 mặc định: 8 vùng nền phẳng trong 131 vùng; 63 patch local. Đây là số vùng được nhận, không chứng minh nền phục hồi đúng. CER/alignment có cải thiện nhưng còn regression trên hai trang. [Cổng benchmark còn thất bại](private-ground-truth-audit.md).

Replay MN109-08 còn 4 cặp textBox giao nhau; ảnh RAM xác nhận các cột Việt chồng ở đầu trang. Cổng `--assert-no-lettering-overlap` **FAIL**. Đây là cổng dàn chữ riêng, không cấp quyền tự gộp OCR, thu font dưới sàn hoặc nới erasure mask. [Sửa xem gốc và giới hạn còn lại](renderer-visibility-review-20261014.md).

Đối chứng block mới chỉ trong harness: hai câu đầu MN109-08 gom đủ và replay cloud text mới có 0 box chồng, 10 lần xem gốc khớp pixel native-size. Khối dài bên trái vẫn là nhãn trắng rõ; nghĩa/cleanup chưa nghiệm thu. Default vẫn đỏ vì detector mới giảm coverage/exact toàn tập, guide PP cũng có regression. Giữ source-member/distrust và không cấp erasure từ learned box. [Quyết định mới nhất](quality-review-20261014-latest.md).

Không promote frozen companion từ QA source. Hạn chế và phiên bản runtime: [portable-testing.md](portable-testing.md).

Font revision `90abd17b4f97671435798b6147b698aa9087612f`, SHA-256 `0f173b3e6cb6d1af25babf7f0057c5ac4ee11f9992b0469bb817e967ef4ad0fc`, 214772 bytes; [metadata Việt](https://github.com/google/fonts/blob/90abd17b4f97671435798b6147b698aa9087612f/ofl/patrickhand/METADATA.pb), [OFL](https://github.com/google/fonts/blob/90abd17b4f97671435798b6147b698aa9087612f/ofl/patrickhand/OFL.txt).
