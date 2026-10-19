# Hướng đi mới — Live translation

Cập nhật 19/10/2026 (tối). Tài liệu cho buổi họp nhóm: thống nhất sản phẩm, kiến trúc, lộ trình và phân công.
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
 → xóa chữ cũ (trong bóng: tô lại lòng bóng; trên tranh: vẽ lại bằng MI-GAN, LaMa cho nền có kết cấu khi có GPU;
   chữ trang trí/logo: giữ nguyên tranh + chấm bấm xem bản dịch) → dàn chữ Việt theo hình bóng
 → hiện dần từng bóng; cache văn bản (không lưu ảnh); dịch trước 2 trang kế (bật thủ công, hiện giá trước)
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
| Xóa chữ trên nền tranh | **Vẽ lại trên máy** (không tốn API): MI-GAN mặc định; LaMa cho vùng nằm trong nền có kết cấu khi có GPU. 10 trang: 27 vùng, 31,1 s trên CPU → 24,5 s với GPU, vùng còn sót nét 2 → 1 | Mask chỉ lấy nét chữ: mắt, mảng tô đặc, nét tranh cắt ngang và **nét gạch chéo (hatching)** được bảo vệ; chữ nhỏ được dò lại khung trên ảnh phóng to |
| Demo trên trình duyệt | Trang 7: 11/11 vùng; bóng đầu 7,1 s; $0,00099; vẽ lại nền 2 vùng trong 2,8 s; mở lại từ bản lưu 3,5 ms | Một lượt, Claude Haiku 5.5, 19/10 |
| Dàn chữ (10 trang, Haiku, dịch lại 19/10 tối) | **93/93 vùng dịch được đều vẽ lại**; tràn 0, chồng chữ 0, lọt ngoài bóng 0; 1 vùng còn sót nét (SL-01, bóng dính viền khung) | Chấm tự động + xem ảnh; $0,00095/trang, bóng đầu p50 7,4 s, trang p50 12,5 s |
| Bộ nhớ truyện v3 | Lưu trữ mọi bản tóm tắt (có mốc trang, model) + bản rút gọn gửi mỗi trang có trần ~2.100 token; truyện 1.000 chương / 300 nhân vật vẫn trong trần | Unit test; prompt mỗi trang ~3–6k token, rất xa ngưỡng 100k |
| Unit test | 41/41 pass | `npm run check` |

### Bake-off model (một lượt, 10 trang GT, 18/10)

| Model | Khớp nhãn GT | CER so với nhãn | Bóng đầu p50 | Cả trang p50 | $/trang | Lỗi tuân thủ hướng dẫn |
|---|---|---|---|---|---|---|
| Claude Haiku 5.5 | 31/81 | 27,0% | 5,05 s | 8,31 s | $0,0010 | 0 |
| Gemini 3.1 Flash-Lite | 35/81 | 22,3% | 4,91 s | 6,32 s | $0,0048 | 6 (để nguyên "Goshujin-sama", chèn chú thích trong ngoặc) |
| Qwen3-VL 235B | 32/81 | 24,4% | 5,31 s | 17,63 s | $0,0017 | 0 |
| DeepSeek V4.1 Flash | 28/81 | 27,9% | 5,88 s | 6,82 s | $0,0031 | 0 |
| Gemini 3.7 Flash | 31/81 | 23,9% | 4,30 s | 8,05 s | $0,0098 | 0 |

Cách đọc: nhãn GT có lỗi (ví dụ nhãn ghi ぎっそく, ảnh là さっそく), nên CER chỉ là chỉ báo đọc chữ, **chưa phải điểm chất lượng dịch**. Một lượt mỗi model, chưa phải p95.
**Quyết định cuối 19/10 (giá trước, rồi chất lượng và tốc độ):** mặc định **Claude Haiku 5.5** (~$0,0013/trang đôi; trên 25 trang của nhóm chrF 38,1 so với 38,4 của DeepSeek 1017, CER 14,5% so với 19,6%, tự chấm 3 so với 8 lỗi nặng). Lựa chọn nhanh **DeepSeek V4.1 Flash 1017** (bóng đầu ~2,2 s, ghim nhà cung cấp InferenceNet/DeepInfra vì Relace giá $0,05/$0,15 đọc ảnh sai 58% ký tự). Gemini 3.1 Flash-Lite là tùy chọn chất lượng cao: cùng 25 trang chrF **43,4** (cao nhất), CER 16,3%, nhưng $0,0093/trang đôi (~7 lần Haiku) và bóng đầu p50 11 s. Nhóm chấm mù cả ba ở `/judge` để chốt. Gemini 2.5 Flash-Lite/Flash bị loại (bỏ sót vùng, CER 37–44%). Chi tiết: [DEMO.md](DEMO.md).

**Ứng viên mới (19/10, một lượt, 10 trang, cùng điều kiện):** Gemini 3.8 Flash đọc chữ tốt nhất (CER 24,0%) nhưng ~$0,009/trang; MiMo-V2.6-Flash đọc kém nhất (CER 40%) và chậm (29 s/trang); Qwen3.7-Flash và Qwen3.8-Omni-Flash (chỉ Alibaba phục vụ) từ chối 2–3/10 trang truyện bình thường vì bộ lọc nội dung. Muse Spark loại vì giá và vì bản rẻ cho Meta dùng dữ liệu để huấn luyện.

**Model tóm tắt nền (chấm mù bằng GPT-5.6, cùng đầu vào):** DeepSeek V4.1 Flash 1017 trung thành nhất (2,0/3, 4 lỗi, ~10 s, ~$0,0005 mỗi lần) — dùng làm mặc định; DeepSeek V4.1 Flash bản thường 1,5–2,0 nhưng chậm (40–80 s); Haiku, Gemini Flash-Lite, MiMo, GLM 1,0–1,5; Qwen3.7-Flash kém nhất (0,5/3).

**Đọc chữ so với nhãn:** 29/81 nhãn có hai model khác hãng đọc giống nhau nhưng khác nhãn (nghi nhãn sai trước); 14/81 là ca khó thật. Bảng phân xử riêng: `.private/eval/ocr-audit.json` (không sửa dataset).

**Còn yếu (ca khó, báo riêng):** trang tiểu luận viết tay dày đặc (SL-01: khung chữ chỉ bao phần trên khối cột, phần dưới không bị xóa); bóng dính viền khung để sót kana ở mép; nhãn tên rất nhỏ ngoài vùng (model báo được nhưng ước vị trí lệch ~150 px nên chỉ hiện dạng ghi chú). Độ trễ bóng đầu trung vị ~5,5–6,7 s, có lần chờ 28 s do nhà cung cấp; chưa đạt mục tiêu < 5 s p95. Mục tiêu tham chiếu (chưa phải kết quả): bóng đầu < 5 s, trang ≤ 12 bóng < 8 s, mở lại từ cache < 200 ms.

### Vẽ lại: MI-GAN hay LaMa (19/10)

40 lỗ cắt vào tranh thật có đáp án + 10 vùng chữ thật, RTX 4060 Laptop / CPU Ryzen 7 7840H (`tools/eval/src/inpaint-bench.ts`).

| Engine | Sai số điểm ảnh (MAE) | Thời gian/vùng GPU | Thời gian/vùng CPU | Nạp lần đầu | Dung lượng | Giấy phép |
|---|---|---|---|---|---|---|
| MI-GAN | 25,7 | **86 ms** (DirectML) | 0,87 s | 0,7–0,9 s | 28 MB | MIT |
| LaMa (big-lama ONNX) | 26,9 | 0,43 s (WebGPU; DirectML lỗi) | 4,9 s | 21–26 s | 208 MB | Apache-2.0 |
| LaMa bản OpenCV | 27,5 trên CPU; **hỏng trên WebGPU** (trả ảnh trắng) | — | 5,6 s | 18 s | 93 MB | Apache-2.0 |

Sai số điểm ảnh ngang nhau, nhưng nhìn bằng mắt: ở nền gạch chéo MI-GAN để lại bóng mờ hình chữ cũ, LaMa nối tiếp nét gạch tự nhiên; ở nền giấy trắng hai bên như nhau.
**Chốt:** MI-GAN mặc định (nhanh, nhẹ, hợp chạy trong trình duyệt); LaMa cho lỗ nằm trong nền có kết cấu khi có GPU; CPU-only chỉ dùng MI-GAN.
Lỗi lớn nhất lại nằm ở **mặt nạ**: nét gạch chéo trong khung chữ bị coi là chữ và bị xóa. Đã sửa bằng phép thử "trường gạch" (hướng gạch đọc từ ngoài khung, lan vào trong theo từng nét song song): độ phủ lỗ trang 2 giảm 0,34 → 0,23, vùng gạch giữ nguyên.
Học từ manga-image-translator: họ dùng LaMa huấn luyện thêm trên manga (MIT) — việc tiếp theo là thử bản này ([so sánh](reference/compare-manga-image-translator.md)).

### Model chạy trên máy (máy 16 GB RAM, 19/10)

Dịch thuần văn bản 120 bóng thoại của nhóm (chữ Nhật lấy từ nhãn, tức OCR hoàn hảo), RTX 4060 Laptop 8 GB, Ollama (`tools/eval/src/mt-text.ts`):

| Model | Dung lượng | chrF so với bản dịch chuẩn | Thời gian/bóng | Giấy phép |
|---|---|---|---|---|
| Claude Haiku 5.5 (cloud, mốc so sánh) | — | **38,7** | 1,5 s | thương mại, $0,0033/120 bóng |
| Hy-MT2 7B Q4 (Tencent, model dịch chuyên dụng) | 4,6 GB | **33,8** | 0,40 s | Apache-2.0 (theo khóa model) |
| Hy-MT2 1.8B Q6 | 1,5 GB | 26,9 | 0,19 s | Apache-2.0 |
| Qwen3 4B Instruct 2507 Q4 | 2,5 GB | 24,4 | 0,19 s | Apache-2.0 |
| Gemma 4 E2B (đọc ảnh) | 7,2 GB | loại: bịa chữ không có trên trang | 7–9 s/ô | Apache-2.0 |

Hy-MT2 dịch nhầm câu ngữ cảnh khi kèm "background" (chrF 7B tụt còn 26,3) → gọi từng câu riêng. Model dịch chữ không nhìn được tranh nên **không biết ai nói với ai** — chế độ local cần một model đọc ảnh (Qwen3-VL 8B / Qwen3.5 / Gemma 4 E4B đang tải, sẽ đo cùng điều kiện).

Bộ nhớ truyện toàn cục và "P/S nhắc tình tiết": thiết kế ở [STORY-MEMORY.md](STORY-MEMORY.md).
Backend cloud cho desktop và mobile: thiết kế ở [CLOUD.md](CLOUD.md).

### Chấm mù cho nhóm

Mở `http://127.0.0.1:8787/judge` khi server đang chạy. Mỗi ô thoại có viền đỏ trên ảnh cắt, kèm các bản dịch ẩn danh xếp
thứ tự khác nhau cho từng người chấm: các model và **bản dịch của nhóm làm đối chứng ẩn**. Chấm Đúng nghĩa (0–3), Tự nhiên (0–3),
Lỗi nặng, chọn bản tốt nhất; nút **Kết quả** cho trung bình, tỉ lệ lỗi nặng kèm khoảng tin cậy 95% và mức đồng ý giữa người chấm.
Bộ hiện có: 419 ô thoại trên 25 trang của nhóm (`?run=team25`). Điểm lưu ở `.private/judge/` (không commit); ảnh không rời máy.

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
2. **Ổ C:** còn ~4,8 GB trống (19/10 tối); nên giữ ≥ 10 GB. Model Ollama nằm ở `D:\ollama_models`.
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
Tùy chọn: `INPAINT_DEVICE=dml` (vẽ lại trên GPU Windows), `INPAINT_ENGINE=auto|migan|lama`, `LOCAL_LLM_URL` (mặc định Ollama `http://127.0.0.1:11434/v1`, chỉ chấp nhận localhost).
Kiểm tra: `npm run check`, đo tìm vùng: `npm run detect`, so sánh model: `npm run eval`.
