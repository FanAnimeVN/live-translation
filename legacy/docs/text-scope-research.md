# Chọn vùng cần dịch: không dịch mọi chữ nhìn thấy

Rà soát 2026-10-13. Nghiên cứu và đề xuất MVP; không phải chứng nhận classifier hay kết quả benchmark đã đạt.

## Kết luận

Thêm **text-scope routing** giữa detector và OCR/dịch. Detector trả lời “ở đâu có chữ”, không trả lời “chữ này có vai trò gì trong truyện”. Không thể khắc phục vấn đề chỉ bằng prompt dịch hoặc chỉ dịch chữ nằm trong bong bóng.

Trong ảnh người dùng gửi, mảng dày đặc góc dưới phải trông giống chuyên mục/phụ chú về ramen; đây là **nhận xét từ ảnh**, chưa phải nhãn đã được xác nhận. Hai khối chữ không có bóng ở phía trên lại là ứng viên nội tâm/lời dẫn, không được bỏ theo cùng quy tắc. Một bức thư, bảng nhiệm vụ hay tài liệu điều tra cũng có thể dày chữ nhưng cần thiết cho câu chuyện.

Baseline được đọc trong `companion/manga_live/ocr.py`: `group_regions` gán mọi vùng `type="dialogue"`; `recognize_regions` OCR tất cả vùng được đưa vào. Review OCR và kiểm tra mặt nền để dàn chữ **không phải** bộ phân loại vai trò ngữ nghĩa. Đây là khoảng trống trước khi bổ sung routing.

## Những giải pháp đã có — và giới hạn

- **Magi v2** thực sự có head phân loại chữ essential/non-essential. Thoại, nội tâm, lời dẫn được giữ; scene text, SFX, chú thích biên tập được xếp non-essential cho mục tiêu tạo *transcript*. Mô hình tận dụng hình thức/vị trí chữ; bài báo báo cáo AP trên PopManga-X. Tuy nhiên, bảng hiệu/SFX “không thiết yếu cho transcript” không đồng nghĩa “không cần dịch cho reader”. Không suy ra độ chính xác trên chữ Nhật viết tay, mảng chú thích của ảnh này hay tốc độ CPU của chúng ta từ AP đó. [Paper, mục 4/7/9](https://arxiv.org/html/2408.00298v1).
- Head phân loại của Magi nhỏ nhưng nằm trên backbone thị giác, không phải một classifier CPU siêu nhẹ độc lập. Ví dụ chính thức dùng CUDA và custom model code. Repo giới hạn models/datasets cho nghiên cứu học thuật; model card v2 cho personal/non-commercial và yêu cầu liên hệ cho trường hợp khác. **Không đưa weights vào bản thương mại mặc định khi chưa làm rõ giấy phép.** [Repo](https://github.com/ragavsachdeva/magi#license-and-citation), [model card](https://huggingface.co/ragavsachdeva/magiv2#license-and-citation).
- **manga-image-translator** có `ignore_bubble`. Heuristic kiểm tra tỷ lệ pixel đen/trắng ở viền crop, không hiểu ý nghĩa hay contour bóng thật. Source tự ghi các lỗi với nền trắng phẳng, vị trí và bóng nối; bởi vậy nó có thể giữ mảng chú thích nền trắng và bỏ chữ quan trọng trên tranh. CTC/32px có nhánh lọc trước recognition, nhưng không nên diễn giải thành mọi OCR backend đều tiết kiệm một forward cho mỗi crop bỏ. [Heuristic](https://github.com/zyddnys/manga-image-translator/blob/main/manga_translator/utils/bubble.py), [CTC caller](https://github.com/zyddnys/manga-image-translator/blob/main/manga_translator/ocr/model_48px_ctc.py), [32px caller](https://github.com/zyddnys/manga-image-translator/blob/main/manga_translator/ocr/model_32px.py).
- Source của manga-image-translator dùng GPLv3, không phải permissive code có thể chép mà bỏ nghĩa vụ phân phối; checkpoint và dữ liệu còn phải rà riêng. [License](https://github.com/zyddnys/manga-image-translator/blob/main/LICENSE).

## MVP đề xuất: bảo thủ, local, có thể đảo ngược

Tách `role` khỏi `action`. `role`: dialogue/thought/narration/scene_text/editorial/sfx/unknown. `action`: translate/defer/skip. Điểm detector không được đặt tên là confidence của role.

| Vùng | Hành động mặc định đề xuất |
|---|---|
| Thoại, nội tâm, lời dẫn; chữ nhỏ đi kèm lời thoại | Ưu tiên dịch, không phụ thuộc có bóng hay không |
| Thư, bảng nhiệm vụ, vật chứng hoặc bảng hiệu được nội dung đang đọc nhắc đến | Dịch khi có bằng chứng liên quan; không gán speaker cứng |
| Phụ chú biên tập/omake hoặc chữ trang trí có bằng chứng đủ rõ | Giữ nguyên; gom thành một nhóm có nút “Dịch phần phụ” |
| Chỉ nhìn thấy cụm nhỏ/dày, chưa biết ý nghĩa | `unknown/defer`, không tuyên bố đã nhận ra chữ không quan trọng; dễ bật dịch lại |
| Số trang/footer được xác định chắc, vùng reader đã chọn bỏ | Skip trước OCR; không xóa chữ gốc |

Luồng thực hiện:

1. **Trước OCR:** dùng metadata website nếu có, hình học vùng, contour đã xác minh, vị trí tương đối với panel và nhóm cột chữ. Chữ nhỏ/dày/ngoài panel chỉ là tín hiệu ứng viên, không phải điều kiện hard-skip. Các vùng bị reader khóa bỏ và footer xác định chắc mới được skip; mảng nghi phụ chú được *defer*, giữ tọa độ/lý do để phục hồi. Không hardcode góc dưới phải hay tọa độ ảnh mẫu.
2. **Sau OCR:** với ứng viên chưa rõ, kiểm tra heading/nội dung cùng vùng lân cận, cách liên kết với hội thoại hiện tại. Có thể dùng classifier local riêng đã kiểm thử; trước đó dùng quy tắc hẹp và cho phép unknown. Không mở request VLM cả trang mặc định, không cho text từ ảnh điều khiển công cụ.
3. **Trước cleanup/dịch/context:** chỉ xử lý những vùng action cho phép. Vùng defer/skip không bị tẩy nền, không tiêu credit dịch và không biến nội dung phụ thành sự kiện/quan hệ của truyện. Dịch phần phụ theo yêu cầu cũng không mặc nhiên ghi vào story memory.
4. **UX:** trạng thái nhỏ “Đang giữ nguyên phần phụ”, một nút dịch nhóm/vùng cụ thể và một nút khôi phục nguyên bản. Không hỏi yes/no cho từng chữ. Reader override ưu tiên cao nhất; thay đổi phải hủy/đánh dấu cache và patch phụ thuộc theo revision, không làm sống lại kết quả cũ.

**Tiết kiệm thật:** skip/defer trước recognition mới giảm số crop OCR; phân loại sau OCR chỉ giảm phần dịch, cleanup và memory. Không quảng cáo “tiết kiệm OCR” cho một bộ lọc vẫn OCR hết trang. Các quy tắc hình học trên là đề xuất CPU-friendly, **chưa có số đo latency hay mức tiết kiệm**.

## Quality gate bắt buộc

Ground truth OCR không đủ để nghiệm thu text-scope. File mẫu người dùng cung cấp có bbox/text nhưng không có role/action; page09 chỉ có hai crop được gán nhãn, không chứng minh phủ hết chữ trên trang. Manga109 chuẩn mô tả face/body/frame/text và transcription, không thể lấy việc không có bbox làm bằng chứng “chữ phải bỏ”. [Annotation schema](https://manga109.github.io/manga109-project-website/en/annotations.html).

- Gán nhãn bổ sung *toàn vùng chữ* trên các trang được phép dùng: role, translate/defer/skip, lý do và mức chắc. Không ghi đè nhãn OCR gốc. Tách riêng tập tựa truyện giữ lại để đánh giá.
- Test đối nghịch: độc thoại không bóng; lời dẫn sát mép; tiếng nói nhỏ; thư dày chữ; bảng nhiệm vụ; bảng hiệu là manh mối; ghi chú tác giả có bóng; trang quảng cáo/credit; SFX; số trang. Density hoặc không có bóng không được tự làm rớt thoại.
- Báo riêng tỷ lệ **bỏ nhầm nội dung quan trọng**, tỷ lệ dịch nhầm phần phụ, unknown/defer, số crop thực sự tránh OCR, và p50/p95 routing/end-to-end. Một nút phục hồi không thay thế yêu cầu giảm false omission.
- Ảnh chỉ nằm trong RAM; nhãn/output benchmark riêng tư không đóng gói phát hành. Xác minh subset và quyền sử dụng trước thử nghiệm thương mại: Manga109 toàn bộ và Manga109-s có điều kiện khác nhau, đều không phải nguồn ảnh để tái phân phối tự do. [Điều khoản chính thức](https://manga109.github.io/manga109-project-website/en/index.html#license).

Chốt: **ưu tiên nội dung câu chuyện + defer có lý do + reader override**, sau đó mới cân nhắc classifier thị giác thương mại được kiểm thử. Không hứa một heuristic sẽ tự hiểu mọi bảng chữ hoặc omake.
