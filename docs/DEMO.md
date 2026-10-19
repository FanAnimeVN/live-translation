# Demo cho nhóm — Live translation (19/10/2026)

Mục tiêu 12–15 phút: cho nhóm thấy bản dịch chạy thật, chữ hòa vào tranh, bộ nhớ truyện, và các con số đo được; sau đó thống nhất hướng đi và phân công.

## Chuẩn bị (10 phút trước giờ demo)

1. Đóng ứng dụng nặng; ổ C: càng trống càng tốt (máy đang thiếu bộ nhớ ảo).
2. Mở hai cửa sổ terminal ở thư mục dự án:
   ```bash
   npm run demo
   ```
   ```bash
   npm run server
   ```
   Giữ cửa sổ server mở suốt buổi demo. Máy có GPU: thêm `INPAINT_DEVICE=dml` vào `.env.local` để vẽ lại nhanh hơn (LaMa cho nền gạch chéo, nạp ngầm ~20 s sau khi bật server).
3. Vẽ sẵn nền tranh cho các trang đã dịch (chạy trên máy, không tốn API, ~1 phút):
   ```bash
   npx tsx tools/eval/src/prepare-demo.ts --warm
   ```
4. Mở http://127.0.0.1:8787 — chọn trang bất kỳ: trang mở ngay từ bản dịch đã lưu (model mặc định Claude Haiku 5.5; bản lưu cũ dịch bằng Gemini 3.1 Flash-Lite vẫn mở được khi chọn model đó).

Muốn dịch lại cả chương từ bộ nhớ sạch (~2 phút, ~$0,06): `npx tsx tools/eval/src/prepare-demo.ts`.

## Kịch bản

| Phút | Làm gì | Nói gì |
|---|---|---|
| 1 | Giới thiệu | Mở manga raw tiếng Nhật, đọc tiếng Việt như bản scan làm sẵn: đúng nghĩa, chữ hòa vào tranh, nhớ truyện, không spoil. |
| 2 | Trang 5 (đã dịch sẵn). Giữ **Space** để so bản gốc ↔ bản dịch | Chữ trong bóng nổ, chữ trên nền tranh được xóa và vẽ lại bằng MI-GAN chạy trên máy; tranh không bị hỏng (nét vẽ, mắt nhân vật được bảo vệ); tiếng động (SFX) giữ nguyên như bản scan, bấm vào vẫn xem được nghĩa. |
| 2 | Chọn model **DeepSeek V4.1 Flash 1017 (nhanh)**, mở trang 7, bấm **Dịch lại trang** | Bóng hiện dần sau ~3 giây; nền tranh được vẽ lại song song trong lúc model dịch; tab **Số đo**: thời gian, token, chi phí (~$0,0007/trang). |
| 2 | Bấm một bóng thoại | Chữ Nhật gốc, bản dịch, người nói → người nghe; sửa bản dịch ngay tại chỗ. |
| 1 | Bật **Dịch trước 2 trang kế (~$0,0009/trang)**, dịch một trang rồi lật sang trang sau | Trang kế đã dịch sẵn trong lúc đọc: mở lại ~4 ms. Tính năng tốn credit cho trang chưa mở nên phải bật thủ công, giá hiện trước. |
| 2 | Tab **Bộ nhớ truyện** | Nhân vật, cách xưng hô có hướng A→B, nút Đúng/Đổi/Bỏ; tóm tắt chạy nền bằng model rẻ; đọc lại trang cũ không lộ diễn biến sau. |
| 2 | Bảng số đo bên dưới | Vì sao chọn model này; chi phí; tốc độ. |
| 1 | Giới hạn và kế hoạch | Mục "Còn thiếu" và lộ trình. |

## Số đo thật (bộ GT 10 trang, 19/10)

| Hạng mục | Kết quả |
|---|---|
| Tìm vùng chữ | 81/81 vùng có nhãn |
| Dàn chữ | 93/93 vùng dịch được đều vẽ lại; tràn 0, chồng chữ 0, lọt ngoài bóng 0; 1 vùng còn sót nét (SL-01) |
| Vẽ lại nền tranh | ~0,9 s/vùng với GPU (MI-GAN + LaMa cho nền có kết cấu), ~1,15 s/vùng CPU; chạy song song lúc dịch; nét gạch chéo quanh chữ được giữ nguyên |
| Mở lại trang đã dịch | ~3 ms (không gọi model) |
| Bộ nhớ truyện | Mỗi trang gửi tối đa ~2.100 token bộ nhớ; thử truyện 1.000 chương / 300 nhân vật vẫn trong trần |

Mặc định hiện tại là **Claude Haiku 5.5** (giá trước: ~$0,001/trang; trên 25 trang của nhóm ngang DeepSeek 1017 về chrF và ít lỗi nặng hơn khi tự chấm; Gemini 3.1 Flash-Lite cao hơn rõ (chrF 43,4 so với 38,1) nhưng đắt ~7 lần). Bảng dưới là lần chấm mù đầu tiên (109 vùng, giám khảo GPT-5.6, tên model bị ẩn và xáo trộn mỗi trang; một lượt, là tín hiệu sàng lọc, chưa thay được người chấm):

| Model | Đúng nghĩa (0–3) | Lỗi nghiêm trọng | Bóng đầu (trung vị) | Cả trang | $/trang |
|---|---|---|---|---|---|
| Gemini 3.1 Flash-Lite (tùy chọn chất lượng) | **2,64** | 4% | 10,6 s | 12,1 s | $0,0048 |
| Gemini 3.8 Flash | 2,59 | **3%** | 7,6 s | 11,5 s | $0,0094 |
| Claude Haiku 5.5 | 2,50 | 9% | 5,1 s | 9,0 s | $0,0009 |
| DeepSeek V4.1 Flash 1017 (nhanh) | 2,28 | 15% | **2,8 s** | **6,6 s** | **$0,0007** |
| DeepSeek V4.1 Flash | 1,75 | 33% | 3,4 s | 8,5 s | $0,0019 |

Tóm tắt truyện chạy nền: DeepSeek V4.1 Flash 1017 trung thành nhất trong 5 model (chấm mù, cùng đầu vào).

## Chấm mù cùng nhóm (sau buổi demo)

Mở `http://127.0.0.1:8787/judge` trên máy đang chạy server (server chỉ nghe trên chính máy đó, nên mọi người chấm lần lượt trên máy này). Mỗi người nhập tên,
chấm các bản dịch ẩn danh của từng ô thoại (có cả bản dịch của nhóm làm đối chứng ẩn). Mỗi người ~60–100 ô là đủ để thấy khác biệt
giữa model mặc định, model nhanh và model chất lượng; nút **Kết quả** cho bảng tổng hợp.

## Còn thiếu (nói thẳng)

- Chưa chạy trên trang web thật: extension Chrome/Edge là mốc tiếp theo.
- Tốc độ chưa đạt mục tiêu p95 (bóng đầu < 5 s, trang < 8 s): Haiku bóng đầu p50 7,4 s; đã có dịch trước trang kế (bật thủ công) và model nhanh DeepSeek 1017.
- Chế độ offline: model dịch chữ trên máy đã đo (Hy-MT2 7B đạt ~87% điểm chrF của Haiku), model đọc ảnh trên máy còn đang tải để đo.
- Chất lượng dịch mới được AI chấm; cần nhóm chấm mù để chốt.
- Nhãn chữ rất nhỏ nằm ngoài vùng (tên nhân vật cạnh hình) mới hiện dưới dạng ghi chú.
- Bộ dữ liệu lớn: chờ quyền Manga109-s; OpenMantra (CC BY-NC 4.0, 214 trang, có bản dịch Anh) dùng được ngay cho đồ án.

## Bản quyền

Ảnh Manga109 chỉ dùng cho học thuật: demo chạy trên máy, không đăng ảnh lên mạng, slide ghi "courtesy of [tác giả]".
