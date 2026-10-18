# Giữ xưng hô đúng vùng nguồn

2026-10-14. Source `speaker-source-v1`; SQLite schema 4. Không tự xác định người nói bằng model mới.

## Lỗi đã tái hiện

Khi reading order đổi, vùng đã xác nhận chuyển từ `r001` sang `r000`.
Lưu lựa chọn theo ordinal làm mất cặp người nói/người nghe của vùng thật, hoặc gán sang vùng khác.
Chỉ dịch đúng ngữ pháp/prompt không sửa được lỗi định danh này.

## Quy tắc hiện tại

- Cặp người nói/người nghe gắn với source key hiện có: ảnh nguồn và crop geometry, kèm truyện, page ID và cutoff. Không gắn với wording OCR hoặc thứ tự đọc.
- Production pipeline và dịch lại từng vùng dùng cùng interface `Memory.bind_speakers`; duplicate key là mơ hồ, giữ `unknown`.
- Reader edit từ native phải khớp revision, chapter/page và một source anchor duy nhất. Sửa từ panel cũ bị từ chối trước khi thay bộ nhớ.
- Binding đã xác nhận tồn tại sau cache trang 24 giờ hết hạn. Lựa chọn chapter 80 không áp dụng khi đọc chapter 20.
- Đổi hình/crop không tự kế thừa speaker. Chưa hỗ trợ đối sánh hình học gần giống để chuyển lock; đây là giới hạn có chủ đích để tránh gán nhầm.

## Dữ liệu cũ và UX

Ordinal-only cũ không có bằng chứng ảnh/crop/revision. Migration giữ nguyên lựa chọn và lưu lịch sử riêng, **không đoán anchor từ cache hiện tại**. Khi có lựa chọn cũ phù hợp cutoff nhưng không có binding nguồn, vùng vẫn `unknown` và có lời nhắc không chặn việc đọc.

Mở panel không dịch/gọi API. Reader có thể xác nhận lại, kể cả giữ `unknown`, bằng “Lưu & dịch lại”; lần dịch lại có thể tính phí theo chế độ đã chọn. Footer thao tác sticky giữ nút lưu/đóng có thể bấm ở khung 390 px. Giữ dữ liệu cũ không có nghĩa tự áp dụng nó vào vùng mới.

Migration schema 3/4 dùng transaction tường minh. Thử chèn lỗi sau CREATE và lúc copy lịch sử: rollback bảng/mốc phiên bản, giữ lựa chọn cũ và khởi động lại được. Đây là DB fixture tự tạo, không phải thử hỏng DB người dùng.

## Kiểm chứng và giới hạn

Regression thực thi qua storage/pipeline: đảo ID, reuse ordinal, thay ảnh, dịch lại, cache hết hạn, cutoff tương lai, revision cũ, duplicate anchor và migration gián đoạn. UI QA dùng transport/OCR/dịch giả lập; Native Messaging status thật kiểm tra phiên bản mà không nạp model.

Không thay OCR, detector, weights, xưng hô reader đã khóa hoặc benchmark gold. Binding đúng chỉ bảo đảm lựa chọn đi vào đúng câu; không chứng minh model chọn đại từ hay dịch nghĩa đúng. Frozen companion/Edge cá nhân chưa cập nhật. Xem [kết quả nghiệm thu mới nhất](quality-review-20261014-latest.md).
