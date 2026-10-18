# Kiểm tra nguồn giấy phép và bản quyền cho MVP

Đối chiếu ngày 13/10/2026. Đây là ghi chú nguồn phục vụ thiết kế MVP, không phải kết luận pháp lý cho mọi trường hợp. Giấy phép phần mềm/mô hình không cấp quyền đối với truyện đầu vào.

## Manga109 và Manga109-s

- **Manga109 (109 tập):** chỉ nghiên cứu học thuật tại tổ chức phi thương mại; cấm chuyển dữ liệu cho bên thứ ba.
- **Manga109-s (87 tập):** cho phép thí nghiệm ML/xử lý ảnh và thương mại hóa kết quả, gồm mô hình; phải công khai đã dùng dataset khi công bố kết quả.
- Vẫn cấm phân phối dataset, bán ảnh kèm kết quả, hoặc coi ảnh gốc/ảnh sửa đổi là sản phẩm dù miễn phí. Công bố nguyên trang để trình bày R&D giới hạn 20% mỗi tập và có yêu cầu ghi công.
- Hệ quả MVP: dùng Manga109-s làm benchmark nội bộ đúng điều kiện; không đóng gói ảnh truyện hoặc bản dịch ảnh thành thư viện/demo sản phẩm. Đây là suy luận triển khai từ điều khoản.

Nguồn: [Đại học Tokyo — License & Terms](https://manga109.github.io/manga109-project-website/en/).

## DeepSeek API: tích hợp và bán lại

- Open Platform Terms có hiệu lực 29/04/2026, §1.1 cho phép tích hợp vào ứng dụng phục vụ người dùng nội bộ và bên ngoài; §4.2 cho phép phát triển sản phẩm từ input/output theo luật và điều khoản. Không có cơ sở để ghi “mọi ứng dụng dịch có thu phí đều bị cấm”.
- General Terms cập nhật 27/03/2026, §3.6(4) cấm bán/chuyển nhượng/cho thuê/cấp phép lại dịch vụ khi chưa được DeepSeek cho phép. Tích hợp ứng dụng không đồng nghĩa quyền bán tài khoản, API key hoặc dịch vụ relay API; ranh giới mô hình bán lại cần xác nhận với nhà cung cấp.
- API §2.2 yêu cầu giữ kín key, không chia sẻ hoặc lộ trong browser/client code. §4.1 yêu cầu có quyền để DeepSeek xử lý input; quyền output không xóa quyền tác giả của truyện gốc.

Nguồn: [Open Platform Terms](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html), [General Terms](https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html). Phân biệt tích hợp và relay ở trên là suy luận triển khai, không phải chấp thuận riêng của DeepSeek cho gói kinh doanh cụ thể.

## Bản quyền tại Việt Nam

[Luật SHTT hợp nhất trong Công báo 10/04/2026](https://congbaocdn.chinhphu.vn/180507251028987904/2026/4/10/469197-1775632354_v1_1775783230_signed.pdf) đã gồm Luật 131/2025/QH15, hiệu lực 01/04/2026:

- Điều 4(8): dịch ngôn ngữ thuộc tác phẩm phái sinh. Điều 20: quyền này thuộc chủ thể quyền, trừ ngoại lệ luật định.
- Điều 25: sao chép nghiên cứu/học tập cá nhân có giới hạn; không cấp miễn trừ chung cho dịch toàn truyện. Ngoại lệ phải bảo đảm khai thác bình thường và lợi ích chủ thể quyền.
- Điều 7(5) mới: nghiên cứu/thử nghiệm/huấn luyện AI dùng dữ liệu công bố hợp pháp, có điều kiện và phụ thuộc quy định Chính phủ khi dữ liệu có bản quyền.
- Suy luận MVP: chọn nội dung tự tạo/được cấp phép cho benchmark/demo. RAM/offline giảm lưu trữ và truyền dữ liệu; không tự cấp quyền dịch. Không khẳng định “đọc riêng/offline luôn hợp pháp”. Áp dụng từng trường hợp cần xét riêng.

## Mã nguồn và trọng số đã đối chiếu

| Thành phần | Mã nguồn | Trọng số |
| --- | --- | --- |
| manga-ocr | [Repo LICENSE — Apache 2.0](https://github.com/kha-white/manga-ocr/blob/master/LICENSE) | [kha-white/manga-ocr-base — apache-2.0](https://huggingface.co/kha-white/manga-ocr-base) |
| Hy-MT2 | [Repo LICENSE.txt — Apache 2.0](https://github.com/Tencent-Hunyuan/Hy-MT2/blob/main/LICENSE.txt) | [Hy-MT2-1.8B LICENSE.txt — Apache 2.0](https://huggingface.co/tencent/Hy-MT2-1.8B/blob/main/LICENSE.txt) |
| Qwen3-4B-Instruct-2507 | Chưa xác minh riêng toàn bộ dependency/runtime trong phạm vi ghi chú này | [Checkpoint LICENSE — Apache 2.0](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/blob/main/LICENSE) |

Apache 2.0 cho phép sử dụng/phân phối trong sản phẩm thương mại với nghĩa vụ kèm giấy phép, giữ thông báo và đánh dấu sửa đổi khi phân phối; không cấp quyền nhãn hiệu hoặc bảo đảm không xâm phạm. Nguồn: [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).

Không áp điều khoản hạn chế lãnh thổ trong [giấy phép HY-MT1.5](https://github.com/Tencent-Hunyuan/HY-MT/blob/main/License.txt) cho Hy-MT2 hiện tại: đây là hai bản phát hành với giấy phép khác nhau. Các bản GGUF/quantization của bên thứ ba và dependency chưa kiểm tra; trước khi đóng gói phải chốt đúng artifact/revision và giữ bản giấy phép tương ứng. Ghi chú này không thẩm định toàn bộ dữ liệu huấn luyện hay quyền đối với mọi output.
