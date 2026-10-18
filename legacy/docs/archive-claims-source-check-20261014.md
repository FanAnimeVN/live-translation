# Đối chiếu nguồn chính thức trong báo cáo của agent khác

Ngày kiểm tra: 2026-10-14. Phạm vi: sáu trang chính thức dưới đây, không chạy mã trong ZIP, không dùng API key, không gửi dữ liệu manga. Đây là kiểm chứng các khẳng định để đánh giá báo cáo, không phải kết luận tư vấn pháp lý hay giấy phép phát hành.

## 1. Manga109 / Manga109-s — đúng một phần, cần giới hạn rõ

Manga109 dùng cho mục đích học thuật, phi thương mại. Manga109-s gồm 87 tập và cho phép thí nghiệm ML/xử lý ảnh cùng việc thương mại hóa **kết quả thí nghiệm**. Tuy nhiên, cả hai không cho tái phân phối dataset; Manga109-s còn cấm coi bản sao/ảnh manga đã sửa là sản phẩm, miễn phí hay thu phí. Công bố nguyên trang/ảnh sửa nguyên trang nhằm trình bày R&D bị giới hạn 20% mỗi tập; có nghĩa vụ ghi nguồn/ghi công tùy cách sử dụng. Đây không phải quyền chung để dùng ảnh làm quảng cáo thương mại hoặc phát hành trang đã dịch. [Manga109 — License & Terms](https://manga109.github.io/manga109-project-website/en/index.html#license)

**Đánh giá:** lời khuyên dùng fixture tự tạo là hợp lý. Cụm “manga thuộc phạm vi cho phép công bố” chỉ chấp nhận sau khi kiểm tra đúng tập, đúng giấy phép và mục đích công bố; tên tệp `MN109-*` hay sự có mặt trong bộ benchmark không tự xác minh quyền. Nếu demo cửa hàng vượt phạm vi đã cấp, phải xin phép riêng.

## 2. Gemini Developer API — hạn chế tuổi đúng, yêu cầu chuyển Vertex bị nói quá

Điều khoản yêu cầu người dùng API từ 18 tuổi và cấm API client hướng tới hoặc có khả năng được người dưới 18 truy cập. Dịch vụ hướng tới developer xây sản phẩm chuyên nghiệp/kinh doanh; không có quy định mọi ứng dụng thương mại đều bắt buộc dùng Vertex. Với Paid Services qua project có billing hoạt động, prompt/response không được dùng để cải thiện sản phẩm, nhưng vẫn có logging thời hạn giới hạn vì an toàn/tuân thủ. Unpaid Services có thể dùng dữ liệu để cải thiện, có reviewer đọc. [Gemini API Additional Terms, Age Requirements / Use Restrictions / Paid Services](https://ai.google.dev/gemini-api/terms)

**Đánh giá:** cảnh báo tuổi là đúng và quan trọng với sản phẩm manga. Không nên viết “chuyển Vertex là đủ để bảo đảm hợp pháp/quyền riêng tư”; phải xác định thị trường, tuổi người dùng và hợp đồng cụ thể. **Không dùng dữ liệu huấn luyện ≠ không lưu dữ liệu.**

## 3. Vertex / Google Cloud — zero retention không mặc nhiên có

Trang Google Cloud mà tài liệu Vertex cũ dẫn tới hiện là hướng dẫn Gemini Enterprise Agent Platform. Google không dùng dữ liệu để huấn luyện/fine-tune nếu chưa được cho phép, nhưng ZDR đòi hỏi cấu hình/hành động riêng: logging chống lạm dụng có thể cần xin ngoại lệ, grounding có retention, implicit caching mặc định có thể lưu tới 24 giờ; một số tính năng nâng cao không thể ZDR. [Google Cloud — Zero data retention](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/zero-data-retention)

**Đánh giá:** “Zero Data Retention cho training” là thuật ngữ sai/lẫn hai thuộc tính. Chỉ được công bố retention sau khi xác nhận model, endpoint, hợp đồng và cấu hình thực tế; không suy ra quyền phục vụ người dưới 18 từ riêng trang dữ liệu này.

## 4. DeepSeek — tích hợp ứng dụng được hỗ trợ, không có safe harbor “thêm giá trị”

Open Platform §1.1 cho tích hợp model vào ứng dụng phục vụ end user; §4.2 cho dùng input/output vào sản phẩm phái sinh, có điều kiện. §2.2 yêu cầu bảo vệ key; §3.2–3.3 giữ trách nhiệm ứng dụng/dữ liệu ở nhà phát triển; §4.1 yêu cầu quyền xử lý input; §8.1 yêu cầu thông báo output do AI tạo và có thể sai. [DeepSeek Open Platform Terms](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html)

General Terms §3.6(4) cấm chuyển nhượng/bán/cấp lại toàn bộ hoặc một phần dịch vụ khi chưa được DeepSeek cho phép. Phạm vi câu này rộng hơn “chỉ cấm bán key hoặc relay thô”. [DeepSeek Terms of Use](https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html)

**Đánh giá:** managed translation có cơ sở tích hợp, nhưng thêm context/validation không phải một ngoại lệ pháp lý được ghi trong điều khoản. Cần xác minh mô hình gói credit với hợp đồng áp dụng trước thu phí. Test hiện đi qua OpenRouter còn có điều khoản router/provider riêng; phần đó chưa được xác minh trong lượt kiểm tra hẹp này.

## 5. Hy-MT2 — khẳng định Apache-2.0 được nguồn chính thức hỗ trợ

`Tencent-Hunyuan/Hy-MT2` hiện ghi rõ Hy-MT2 theo Apache License 2.0, không phải lý do để bác bỏ báo cáo về riêng model này. [Hy-MT2 — LICENSE.txt](https://github.com/Tencent-Hunyuan/Hy-MT2/blob/main/LICENSE.txt)

**Giới hạn:** kiểm tra trên `main` không thay cho kiểm toán giấy phép tại revision weights/GGUF đang đóng gói. Cần giữ nghĩa vụ license/notice tương ứng và rà từng dependency, font, model; license model không cấp quyền đối với manga đưa vào. Lượt này không xác minh toàn bộ khẳng định “mọi thành phần đều an toàn, chỉ cần LICENSE/NOTICE”.

## 6. Đối thủ, thị hiếu và lợi thế thương mại — chưa được chứng minh

Báo cáo khẳng định các đối thủ **đều** gửi toàn bộ ảnh và lưu ảnh cloud, thiếu tối ưu Nhật–Việt/spoiler, đồng thời dự án “vượt trội hoàn toàn”. Các đoạn được cung cấp không chỉ ra điều khoản retention, kiến trúc hay phép đo đối chứng riêng của từng sản phẩm. Lượt kiểm tra sáu nguồn này không audit các đối thủ; vì thế trạng thái là **chưa kiểm chứng**, không phải kết luận họ không lưu ảnh hoặc không có tính năng đó.

Tương tự, tỷ lệ rụng người dùng 80%, giảm CPU 45–60%, tiết kiệm server 95%, biên lợi nhuận 50–60% và thị hiếu thống nhất của độc giả Việt chưa có dữ liệu khảo sát/benchmark/giá vốn đủ để chốt. Có thể giữ làm giả thuyết cần thử; không dùng làm thông điệp quảng cáo hoặc quyết định nghiệm thu.

## Kết luận để xử lý báo cáo

Giữ các nhắc nhở về quyền input, key server, giấy phép, fixture có quyền. Sửa các câu khẳng định rộng về Manga109-s, Gemini/Vertex/ZDR và điều kiện bán lại DeepSeek. Không coi phần đối thủ/thị hiếu/giá bán là bằng chứng. Đánh giá bản vá code và test độc lập với phần nghiên cứu này; thông tin đúng trong báo cáo không chứng minh bản ZIP đã đạt cổng chất lượng.
