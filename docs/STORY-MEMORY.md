# Bộ nhớ truyện toàn cục và "P/S nhắc tình tiết" — thiết kế

Cập nhật 19/10/2026. Trạng thái: **thiết kế, chưa cài**. Phần "đã có" là code hiện tại (context v3).

## 1. Mục tiêu

- Tên, xưng hô, thuật ngữ nhất quán suốt bộ truyện; cảnh hồi tưởng vẫn biết chuyện cũ.
- Chi phí và độ trễ mỗi trang **không tăng theo độ dài truyện**: prompt có trần token cố định.
- Không spoil (chỉ dùng điều đã biết trước vị trí đang đọc), mọi dữ kiện có bằng chứng trang/vùng, khóa của người đọc luôn thắng.
- "Tinh tế" như team dịch: khi nhân vật nhắc lại chuyện cũ, có dòng P/S chỉ chương/trang để đọc lại.

## 2. Đã có trong code (context v3)

| Thành phần | Nội dung | Vào prompt |
|---|---|---|
| Thực thể | nhân vật, xưng hô có hướng A→B, thuật ngữ; trạng thái auto/confirmed/locked, bằng chứng, mốc hiệu lực | luôn, chọn theo người đang xuất hiện, trần 1 200 token |
| Thoại gần | các câu vừa đọc (ja, vi, người nói→người nghe) | luôn, trong trần 900 token |
| Kho lưu trữ | mỗi lần cập nhật nền (~24 câu) thêm một bản ghi: đoạn tóm tắt ≤ 60 từ, ≤ 4 sự kiện có bằng chứng; **chỉ ghi thêm, không sửa** | đoạn gần nhất |
| "Truyện tới giờ" | ≤ 120 từ, model nền gộp bản cũ với đoạn mới | luôn |

Điểm yếu: "Truyện tới giờ" là **tóm tắt của tóm tắt** (mỗi lần gộp lại mất chi tiết); sự kiện cũ không bao giờ được lôi ra lại; không có tóm tắt theo chương.

## 3. Thiết kế: bốn tầng, không tóm tắt chồng tóm tắt

| Tầng | Nội dung | Ai viết, khi nào | Vào prompt | Trần |
|---|---|---|---|---|
| L0 Gần đây | K câu thoại gần nhất, nguyên văn | tự động | luôn | ~600 token |
| L1 Thẻ sự kiện | sự kiện, ai tham gia, mức quan trọng 1–3, loại (sự kiện / tiết lộ / đổi quan hệ / lời hứa / hồi tưởng), từ khóa ja+vi, bằng chứng trang/vùng | model rẻ chạy nền, mỗi ~24 câu | **chỉ khi được gọi lại** (mục 4) | ≤ 400 token |
| L2 Tóm tắt chương | dựng từ thẻ L1 của chính chương đó | khi hết chương | chương liền trước | ≤ 150 token |
| L3 Toàn truyện | dựng lại từ các L2, **không** từ L3 cũ | khi có chương mới | luôn | ≤ 200 token |
| Thực thể | như hiện có | | luôn | ≤ 1 200 token |

Ba nguyên tắc chống mất dữ kiện:

1. Dữ kiện quan trọng nhất (tên, xưng hô, quan hệ, thuật ngữ) nằm trong **bảng có cấu trúc**, không bao giờ bị tóm tắt; chỉ được chọn lọc theo nhân vật đang xuất hiện.
2. Thẻ L1 là bản gốc chỉ-ghi-thêm, giữ vĩnh viễn và có bằng chứng. Mỗi tầng trên chỉ tóm tắt **một cấp** từ tầng ngay dưới và luôn dựng lại từ nguồn — lỗi không cộng dồn qua nhiều vòng.
3. Trần cố định ≈ 2 500 token context mỗi trang dù truyện 10 hay 500 chương: chi phí và độ trễ phẳng. Phần lớn lịch sử nằm ngoài prompt, chỉ được gọi khi cần.

## 4. Model tự quyết khi nào cần nhớ lại

- Thoại thường ngày: chỉ L0 + thực thể + L3 (rẻ, nhanh).
- Khi một câu nhắc chuyện cũ (あの時, 約束, 前に, "còn nhớ không…", khung hồi tưởng viền đen/mờ), model đọc trang trả thêm một dòng, ví dụ
  `{"recall":{"regions":["r7"],"who":["Nana"],"keys":["約束","lễ hội"]}}`.
- Server truy hồi thẻ L1 **trước vị trí đang đọc** theo nhân vật + từ khóa + mức quan trọng. Có thẻ khớp thì chạy **một lượt sửa nhỏ chỉ cho các vùng đó** (giống lượt sửa ID hiện có) kèm thẻ, cập nhật bản dịch và tạo P/S. Chỉ tốn thêm ở trang cần (ước tính 5–10% số trang; phải đo).
- Hỏi đáp trong khung chat ("chuyện X là gì?", "Tóm tắt đến đây"): cùng bộ truy hồi, trả lời có trích chương/trang, không vượt vị trí đang đọc.
- Sau này: truy hồi theo nghĩa bằng một model embedding nhỏ chạy trên máy khi từ khóa không đủ.

## 5. P/S nhắc tình tiết

- Nguồn: chỉ thẻ L1 có bằng chứng ở chương/trang **trước** vị trí đang đọc. Ví dụ: "P/S: lời hứa ở lễ hội — chương 3, trang 12."
- Vị trí: tìm dải trống giữa các khung tranh (gutter, trắng hoặc đen) bằng hồ sơ chiếu theo hàng/cột, chọn dải gần bóng thoại nhắc chuyện cũ và đủ chỗ. Không có chỗ thì hiện một chấm nhỏ bấm để xem — không bao giờ đè lên tranh.
- Cài đặt: Tắt / Kín đáo (chấm bấm xem, mặc định) / Hiện. "Xem bản gốc" ẩn toàn bộ P/S.

## 6. Điểm ngọt (sweet spot): đo, không đoán

- Biến số: K câu ở L0 ∈ {0, 10, 20, 40, 80}; số câu mỗi thẻ L1 (hiện 24); độ dài L3.
- Dữ liệu: các truyện có trang liên tiếp trong bộ của nhóm (set1) và 10 trang GT, đọc tuần tự.
- Số đo: chrF với bản dịch chuẩn của nhóm, lỗi xưng hô/người nói (tự chấm), token vào, thời gian tới bóng đầu, $/trang.
- Chọn K **nhỏ nhất** đạt ≥ 98% chất lượng của K lớn nhất. Chi phí thử ước tính ~$0,2 (Haiku, 5 cấu hình × ~40 trang).

## 7. Thứ tự cài đặt

1. Mở rộng sự kiện L1: `who`, `importance`, `kind`, `keys`; prompt cập nhật nền trả các trường này (tương thích dữ liệu cũ).
2. Tóm tắt chương L2, dựng L3 từ L2; bỏ việc gộp "truyện tới giờ" nối tiếp.
3. `recallEvents(memory, vị trí, truy vấn)` trong `packages/core` (thuần, có test chống spoil).
4. Trường `recall` trong prompt đọc trang (v4) + lượt sửa có thẻ; đo tỉ lệ kích hoạt và chi phí.
5. `findGutters(ảnh)` + vẽ P/S trong renderer + cài đặt.
6. Thí nghiệm điểm ngọt, chốt K.
