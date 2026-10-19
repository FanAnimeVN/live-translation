# Hướng đi mới — Live translation

Cập nhật 19/10/2026. Tài liệu cho buổi họp nhóm: thống nhất sản phẩm, kiến trúc, lộ trình và phân công.
Đặc tả mong muốn đầy đủ: [WISH-FINAL-APP.md](reference/WISH-FINAL-APP.md).

## 1. Sản phẩm trong một câu

Extension Chrome/Edge: mở manga raw tiếng Nhật trên web, bấm dịch và đọc tiếng Việt như một bản scanlation làm sẵn.
Bản dịch đúng nghĩa, đúng xưng hô, chữ hòa vào tranh. Truyện có bộ nhớ riêng (tên, danh xưng, mạch truyện) và không spoil.

Thứ tự ưu tiên: **đúng nghĩa → chữ hòa vào tranh → đọc liên tục → tính năng thêm.**

## 2. Vì sao đổi hướng

| | Bản cũ (12–18/10) | Hướng mới |
|---|---|---|
| Hình thức | Extension + companion Python cài trên Windows (Native Messaging) | Chỉ extension, cộng một backend cloud mỏng cho gói credit |
| Đọc chữ | Detector PP-OCRv5 + manga-ocr, gom bóng bằng heuristic (v1→v21) | Detector chuyên manga (bóng/chữ trong bóng/chữ tự do), sau đó model vision đọc + dịch cả trang trong ngữ cảnh |
| Vấn đề gặp phải | Lỗi "không tìm thấy host" trên Edge thật; khởi động lạnh 25–40 s; gán được 62/78 vùng | Không cần cài thêm; detector tìm được 80/81 vùng (mục 4) |
| Cách đánh giá | Exact-match OCR trên nhãn có lỗi; hạn mức thử $0,50 nên gần như không thử được cloud | Đo trên trang thật: tìm vùng, CER, độ trễ, chi phí; chấm mù bản dịch; ngân sách thử $5 có sổ chi phí |
| Prompt | Chuỗi bản vá cho từng câu cụ thể | Bộ quy tắc gọn + ví dụ + bộ nhớ truyện |

Code cũ không bị xóa: nằm trong `legacy/` và tag git `legacy-v0`.

## 3. Kiến trúc

```
ảnh trang (chỉ trong RAM)
 → detector manga (ogkalu RT-DETR-v2, Apache-2.0, 11 MB): bóng thoại / chữ trong bóng / chữ tự do
 → gom vùng + thứ tự đọc phải→trái → ảnh trang có đánh số vùng (+ ảnh phóng to vùng chữ nhỏ)
 → model vision đọc chữ Nhật + dịch, kèm bộ nhớ truyện → trả về từng vùng (stream)
 → xóa chữ cũ (nền phẳng: tô lại; nền tranh/logo: giữ nguyên tranh) → dàn chữ Việt theo hình bóng
 → hiện dần từng bóng; cache văn bản (không lưu ảnh); chuẩn bị trước 2–3 trang kế
```

- **3 chế độ:** Cloud (đăng nhập + credit, key nằm ở server) · BYOK (key riêng của người dùng, ví dụ Gemini có free tier) · Local (Ollama/LM Studio chạy trên máy, offline không gọi mạng).
- **Bộ nhớ truyện:** nhân vật, tên/thuật ngữ, xưng hô có hướng A→B, tóm tắt chương, thoại gần nhất. Mọi mục đều có bằng chứng (trang + vùng) và mốc chương/trang, chỉ dùng những gì đã đọc. Tên AI đề xuất cần người đọc bấm **Đúng / Đổi / Bỏ**; tên đã khóa luôn thắng.
- **Một stack TypeScript:** `packages/core` (logic dùng chung cho trình duyệt và Node), `packages/render` (xóa + dàn chữ), `apps/server`, `apps/demo`, `tools/eval`; extension làm ở M1.

## 4. Đã làm được và số đo thật (19/10)

| Hạng mục | Kết quả | Điều kiện đo |
|---|---|---|
| Tìm vùng chữ trên bộ ground truth | **81/81 vùng (100%)** | 10 trang; bóng thoại chắc chắn (≥ 0,5) giữ cả chữ mờ bên trong (bóng chỉ có dấu "!" trước đây bị bỏ) |
| Thời gian tìm vùng | ~0,28–0,37 s/trang khi đã warm, ~1 s lần đầu | CPU Ryzen 7 7840H, onnxruntime 4 luồng |
| Dịch thật cả trang (5 model × 10 trang) | **107/107 vùng có bản dịch với mọi model**, 0 trang lỗi | Một lượt mỗi model, cùng detector, prompt và luồng bộ nhớ; tổng chi phí $0,20 |
| Xóa chữ trong bóng thoại | Loang lấy lòng bóng (flood fill): giữ viền bóng và tranh ngoài bóng | |
| Xóa chữ trên nền tranh | **Luôn vẽ lại bằng MI-GAN trên máy** (MIT, không tốn API), ~1,1 s/vùng trên CPU | Mask chỉ lấy nét chữ: mắt, mảng tô đặc và nét tranh cắt ngang khung chữ được bảo vệ; chữ nhỏ được dò lại khung trên ảnh phóng to |
| Demo trên trình duyệt | Trang 7: 11/11 vùng; bóng đầu 7,1 s; $0,00099; vẽ lại nền 2 vùng trong 2,8 s; mở lại từ bản lưu 3,5 ms | Một lượt, Claude Haiku 5.5, 19/10 |
| Dàn chữ (10 trang, Haiku, prompt v3) | **93/93 vùng dịch được đều vẽ lại**; tràn 0, chồng chữ 0, lọt ngoài bóng 0; 4 vùng nghi còn nét (chữ trên nền gạch chéo dày) | Chấm tự động + xem ảnh; câu hét trong bóng, chú thích, tiêu đề chương giờ được dịch |
| Bộ nhớ truyện v3 | Lưu trữ mọi bản tóm tắt (có mốc trang, model) + bản rút gọn gửi mỗi trang có trần ~2.100 token; truyện 1.000 chương / 300 nhân vật vẫn trong trần | Unit test; prompt mỗi trang ~3–6k token, rất xa ngưỡng 100k |
| Unit test | 37/37 pass | `npm run check` |

### Bake-off model (một lượt, 10 trang GT, 18/10)

| Model | Khớp nhãn GT | CER so với nhãn | Bóng đầu p50 | Cả trang p50 | $/trang | Lỗi tuân thủ hướng dẫn |
|---|---|---|---|---|---|---|
| Claude Haiku 5.5 | 31/81 | 27,0% | 5,05 s | 8,31 s | $0,0010 | 0 |
| Gemini 3.1 Flash-Lite | 35/81 | 22,3% | 4,91 s | 6,32 s | $0,0048 | 6 (để nguyên "Goshujin-sama", chèn chú thích trong ngoặc) |
| Qwen3-VL 235B | 32/81 | 24,4% | 5,31 s | 17,63 s | $0,0017 | 0 |
| DeepSeek V4.1 Flash | 28/81 | 27,9% | 5,88 s | 6,82 s | $0,0031 | 0 |
| Gemini 3.7 Flash | 31/81 | 23,9% | 4,30 s | 8,05 s | $0,0098 | 0 |

Cách đọc: nhãn GT có lỗi (ví dụ nhãn ghi ぎっそく, ảnh là さっそく), nên CER chỉ là chỉ báo đọc chữ, **chưa phải điểm chất lượng dịch**. Một lượt mỗi model, chưa phải p95.
Mặc định tạm thời: **Haiku 5.5** (rẻ nhất, không lỗi tuân thủ); tầng nhanh/chất lượng: **Gemini 3.7 Flash**. Chốt sau khi nhóm chấm mù bản dịch.

**Ứng viên mới (19/10, một lượt, 10 trang, cùng điều kiện):** Gemini 3.8 Flash đọc chữ tốt nhất (CER 24,0%) nhưng ~$0,009/trang; MiMo-V2.6-Flash đọc kém nhất (CER 40%) và chậm (29 s/trang); Qwen3.7-Flash và Qwen3.8-Omni-Flash (chỉ Alibaba phục vụ) từ chối 2–3/10 trang truyện bình thường vì bộ lọc nội dung. Muse Spark loại vì giá và vì bản rẻ cho Meta dùng dữ liệu để huấn luyện.

**Model tóm tắt nền (chấm mù bằng GPT-5.6, cùng đầu vào):** DeepSeek V4.1 Flash trung thành nhất (2,0/3, ít lỗi nhất), ~$0,0002–0,0003 mỗi lần khi chọn nhà cung cấp rẻ nhất; MiMo/GLM viết đủ ý hơn nhưng thêm thắt sai (1,0/3); Qwen3.7-Flash kém nhất (0,5/3). Giữ DeepSeek.

**Đọc chữ so với nhãn:** 29/81 nhãn có hai model khác hãng đọc giống nhau nhưng khác nhãn (nghi nhãn sai trước); 14/81 là ca khó thật. Bảng phân xử riêng: `.private/eval/ocr-audit.json` (không sửa dataset).

**Còn yếu (ca khó, báo riêng):** chữ trên nền gạch chéo dày (MI-GAN để lại dải nhạt, cần thử LaMa); nhãn tên rất nhỏ ngoài vùng (model báo được nhưng ước vị trí lệch ~150 px nên chỉ hiện dạng ghi chú). Độ trễ bóng đầu trung vị ~5,5–6,7 s, có lần chờ 28 s do nhà cung cấp; chưa đạt mục tiêu < 5 s p95. Mục tiêu tham chiếu (chưa phải kết quả): bóng đầu < 5 s, trang ≤ 12 bóng < 8 s, mở lại từ cache < 200 ms.

## 5. Tính năng theo mốc

| Tính năng | M0 (họp nhóm) | M1 (proposal tuần sau) | M2 (MVP, 2–3 tuần) |
|---|---|---|---|
| Tìm vùng chữ + dịch cả trang có ngữ cảnh | ✅ demo (chờ key để chạy model thật) | ✅ | ✅ |
| Bóng hiện dần khi đang dịch | ✅ | ✅ | ✅ |
| Xóa chữ + dàn chữ Việt trong bóng | ✅ | ✅ | ✅ + xóa chữ trên nền tranh (inpainting chạy trên máy) |
| Giữ Space để xem bản gốc | ✅ | ✅ (phím tắt trong extension) | ✅ |
| Bấm một bóng: xem JP gốc, sửa bản dịch | ✅ | ✅ | ✅ + dịch lại riêng bóng đó |
| Bộ nhớ truyện + Đúng/Đổi/Bỏ | ✅ cơ bản | ✅ | ✅ Side Panel, lịch sử, export/import |
| Extension chạy trên trang web thật | — | ✅ v0.1 | ✅ + trang raw nhóm chọn |
| Cloud: tài khoản + credit | — | — | ✅ (thanh toán chế độ test) |
| Local/offline (Ollama) | — | — | ✅ có hướng dẫn cài |
| Đọc file ZIP/ảnh của mình | — | — | ✅ |
| "Tóm tắt đến đây" không spoil | — | — | ✅ |
| Chat hỏi về truyện, mobile, thêm ngôn ngữ | — | — | Sau MVP |

## 6. Mô hình kinh doanh (giả thuyết, chốt sau khi đo chi phí thật)

- **Miễn phí:** BYOK với key Gemini free tier, hoặc chế độ local. Chậm hơn hoặc bị giới hạn lượt.
- **Gói credit cloud:** 1 credit ≈ 1 trang chế độ nhanh; chế độ chất lượng cao tốn nhiều credit hơn.
- Giá model (danh mục OpenRouter, USD/1 triệu token vào/ra): Haiku 5.5 0,10/0,50 · Gemini 3.1 Flash-Lite 0,25/1,50 · Gemini 3.7 Flash 0,75/3,75. Ước tính thô ~$0,001–0,01/trang, sẽ thay bằng số đo bake-off.
- Đối thủ tham khảo: Scan Translator (€12,99/tháng), Ichigo ($5,99–19,99/tháng), Kites (miễn phí, nguồn mở). Điểm khác biệt nhắm tới: chất lượng Nhật–Việt (danh xưng, xưng hô A→B), bộ nhớ truyện không spoil, chữ hòa vào tranh, giá phù hợp người Việt.

## 7. Phân công gợi ý

| Vai trò | Việc chính |
|---|---|
| Lead / sản phẩm / thuyết trình | Ưu tiên tính năng, deck proposal 5 phút, kịch bản demo |
| UI extension | Popup, trang cài đặt, Side Panel bộ nhớ (React) |
| Backend cloud | Đăng nhập, sổ credit, proxy gọi model, thanh toán chế độ test |
| Dữ liệu & đánh giá | Xin quyền Manga109 trên Hugging Face; dịch chuẩn tiếng Việt ~150 bóng; chấm mù; phân xử nhãn OCR sai (lưu riêng, không sửa file gốc) |
| Văn phong & độc giả | Khảo sát người đọc Việt (giữ chất Nhật đến đâu, xưng hô theo thể loại); bộ ca khó để kiểm thử |

Pipeline lõi và phần tích hợp: Claude làm, nhóm review.

## 8. Quy tắc dịch không đổi

- Giữ hậu tố/danh xưng Nhật có nghĩa (-san, -kun, -chan, -sama, senpai, sensei…). Không chồng danh xưng: viết "nee-chan", không viết "chị nee-chan"; viết "onii-chan", không viết "anh onii-chan". Hệ thống tự kiểm tra lỗi này.
- Xưng hô theo hướng A→B, không tự suy ra B→A. Chưa rõ thì lược hoặc dùng từ trung tính, không bịa giới tính/tuổi/quan hệ.
- Giữ nói lắp, kéo âm, dấu ba chấm, !?, chữ IN HOA, nói từng chữ.
- Không spoil: bộ nhớ chỉ chứa những gì người đọc đã đọc tới. Không tự tra wiki trong MVP.
- Không xóa tranh khi không chắc; không âm thầm bỏ chữ; không tính phí ngầm.

## 9. Việc cần làm ngay

1. Xóa biến môi trường Windows cũ `OPENROUTER_API_KEY` (key khác, limit $0) nếu không còn dùng; dự án đã ưu tiên `.env.local`.
2. **Giải phóng ổ C:** hiện chỉ còn khoảng 55 MB trống, bộ nhớ ảo gần cạn, đã làm lỗi khi xử lý ảnh. Nên trống ít nhất 10–20 GB trước buổi demo.
3. Gửi URL trang raw muốn demo, để kiểm tra cách trang đó tải ảnh.
4. Xin quyền truy cập Manga109 (`hal-utokyo/Manga109` trên Hugging Face) để có bộ đánh giá lớn hơn.
5. Lưu ý bản quyền: ảnh Manga109 chỉ dùng học thuật, trang demo chỉ chạy trên máy, slide ghi "courtesy of [tác giả]".

## 10. Chạy demo trên máy

```bash
npm install
npm run demo        # build giao diện
npm run server      # mở http://127.0.0.1:8787
```

Cần `.env.local` (không commit) gồm `OPENROUTER_API_KEY`, `DATASET_DIR` và `DETECTOR_MODEL`; xem `.env.example`.
Kiểm tra: `npm run check`, đo tìm vùng: `npm run detect`, so sánh model: `npm run eval`.
