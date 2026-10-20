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

### Vẽ lại: MI-GAN, LaMa hay model của manga-image-translator (19–20/10)

40 lỗ cắt vào tranh thật có đáp án (cả 40 nằm trong nền có kết cấu) + 10 vùng chữ thật, RTX 4060 Laptop / CPU Ryzen 7 7840H (`tools/eval/src/inpaint-bench.ts`). Mọi engine đo lại trong cùng một lượt ngày 20/10: MAE giống hệt lượt 19/10, thời gian dao động khoảng ±20%.
Ảnh so sánh: 10 trang GT vẽ lại bằng `tools/eval/src/render.ts` với `INPAINT_DEVICE=dml`, dùng bản dịch Haiku có sẵn (`fresh-20261019`), mỗi engine một lượt, cắt các ô có nền gạch / screentone / giấy trắng đặt cạnh nhau.

| Engine | MAE (0–255, thấp tốt hơn) | Nhìn bằng mắt (gạch / screentone / giấy trắng) | ms/lỗ GPU | ms/lỗ CPU | Nạp lần đầu | Dung lượng | Giấy phép |
|---|---|---|---|---|---|---|---|
| MI-GAN | **25,7** | Bóng mờ hình chữ cũ trong nền gạch, vệt mờ trong ô có nét dọc; giấy trắng sạch | **86** (DirectML) | 803 | 0,5–1 s | 28 MB | MIT |
| AOT (manga-image-translator, "default") | 27,8 | Giấy trắng sạch; nối nét gạch kém LaMa; để chấm lốm đốm ở vùng chữ viết tay dày | 110 (WebGPU), 222 (DirectML) | **496** | 0,5–0,8 s | 23 MB | GPL-3.0 (theo dự án) |
| LaMa (big-lama ONNX) | 26,9 | Nối tiếp nét gạch, nét tốc độ; giấy trắng sạch | 426 (WebGPU; DirectML lỗi) | 3 680 | 22–28 s | 208 MB | Apache-2.0 |
| LaMa manga (dreMaz/AnimeMangaInpainting) | 26,2 | Nối nét gạch như LaMa, ít "vá phẳng" nhất; **nhưng để bóng xám hình chữ trên giấy trắng** | 465–602 (WebGPU) | 3 658 | 23–32 s | 208 MB | MIT |
| LaMa-MPE (manga-image-translator) | 26,8 | Nối nét gạch như LaMa; trên giấy trắng chỉ còn bóng rất nhạt; vá hơi sáng và phẳng hơn (giữ kết cấu 0,83 so với 0,92) | 374 (WebGPU) | 1 841 | **1,0–1,2 s** | 112 MB | GPL-3.0 (theo dự án) |
| LaMa bản OpenCV | 27,5 trên CPU; **hỏng trên WebGPU** (trả ảnh trắng) | — | — | 5,6 s | 18 s | 93 MB | Apache-2.0 |

Không engine nào trả lỗ một màu (kiểm "dead fill" trong bench). Hai bản LaMa 18 khối cùng một mạng nên cùng tốc độ; LaMa-MPE chỉ có 9 khối nên nhanh gấp đôi trên CPU.

Cả 10 trang, ép mọi lỗ cho một engine (một lượt mỗi dòng, 20/10, cùng bản dàn chữ đã sửa, 25 vùng được vẽ lại):

| Engine | Vùng còn sót nét | Cờ "vá lộ" (vá phẳng trong nền có kết cấu) | Vùng phải vẽ lại cả khung |
|---|---|---|---|
| MI-GAN | 1 | 5 | 2 |
| AOT | 2 | 4 | 3 |
| LaMa | **0** | 3 | 3 |
| LaMa manga | 1 (MN109-05 r14: bóng chữ "ら" trên giấy) | **2** | 3 |
| LaMa-MPE | **0** | 4 | 2 |
| auto: MI-GAN + LaMa cho nền có kết cấu | **0** | 3 | 3 |

Thời gian vẽ lại 10 trang không đưa vào bảng: lượt 20/10 có tiến trình khác dùng chung GPU nên dao động 15–150 s; dùng ms/lỗ của bench ở bảng trên. Lượt 19/10 (trước khi sửa dàn chữ) có thêm vùng SL-01 r5 nên số hơi khác.

LaMa manga: checkpoint PyTorch (pickle) được đọc **không cần torch, không chạy mã trong file** (bộ unpickle chỉ cho phép tensor), 989/989 tensor ghép vào đồ thị `lama_fp32.onnx` (BatchNorm gộp như bản xuất gốc); tương quan trung vị với trọng số big-lama 0,935, đúng là bản fine-tune cùng mạng.
Ghim: repo @`2953a4e9`, `lama_large_512px.ckpt` sha256 `11d30fbb…c935`, ONNX `lama_manga_fp32.onnx` sha256 `114ac0ca…cbf2` (`apps/server/src/lama.ts`). Cũng đã thử cho LaMa nhìn cửa sổ 512 px đúng tỷ lệ trang thay vì phóng to crop: kém hơn ở cả hai bản (MAE 28,3 / 27,4) nên giữ cách cũ.

AOT và LaMa-MPE (20/10): `inpainting.ckpt` và `inpainting_lama_mpe.ckpt` từ release `beta-0.3` của manga-image-translator; sha256 khớp giá trị dự án công bố (`878d541c…149f`, `d625aa1b…86cc`).
Trọng số đọc bằng `torch.load(weights_only=True)` (chỉ tensor, không chạy mã trong file) vào mạng viết lại. Xuất ONNX bằng torch 2.5.1 CPU trong môi trường riêng (`.cache/venv-export`, chỉ dùng lúc xuất, không dùng lúc chạy).
Phép FFT của LaMa được thay bằng nhân ma trận DFT, lệch 0,0002/255 so với `torch.fft`. Để kiểm mạng viết lại, nạp trọng số LaMa manga vào đó rồi so với `lama_manga_fp32.onnx`: lệch trung bình 0,0001/255. ONNX so với torch: AOT lệch tối đa 0,02/255, LaMa-MPE 0,0004/255.
LaMa-MPE có thêm phần "mã hóa vị trí trong lỗ" (số bước từ mép lỗ vào và hướng vào). Hệ số học được của phần này chỉ ~0,001, nên nó đổi kết quả dưới nửa mức xám (trung bình 0,09/255); runner đưa 0 vào.
Ghim: `aot_manga.onnx` `285d51b1…1234` (`apps/server/src/inpaint.ts`), `lama_mpe_fp32.onnx` `0f8a9a05…d624` (`apps/server/src/lama.ts`). Bật bằng `INPAINT_ENGINE=aot` hoặc `INPAINT_LAMA=lama-mpe`.
Phát hiện phụ về thời gian nạp: big-lama chờ 22–28 s phần lớn do cách xuất của bản Carve (tính ma trận DFT lúc chạy, 17 480 nút). Xuất lại LaMa manga 18 khối qua mạng viết lại cho kết quả giống hệt (lệch 0,0025/255), đồ thị 6 542 nút, nạp trên CPU 11,6 → 4,4 s (onnxruntime Python), chạy 2,75 / 3,0 s. Trên WebGPU chưa đo.

**Chốt:** MI-GAN mặc định (nhanh, nhẹ, hợp chạy trong trình duyệt); `auto` dùng big-lama cho lỗ trong nền có kết cấu khi có GPU; CPU-only chỉ dùng MI-GAN.
LaMa manga **chưa thay** big-lama: MAE thấp hơn chút và ít vá phẳng hơn, nhưng để lại bóng chữ trên giấy trắng — đúng lỗi người đọc thấy rõ nhất. Để tùy chọn `INPAINT_LAMA=lama-manga`, đo lại trên bộ 50 trang của nhóm.
AOT **không dùng**: sai số cao nhất trong các engine chạy được, còn sót nét 2 vùng, nối nét gạch kém LaMa. Nó chỉ nhanh hơn MI-GAN trên CPU (0,5 / 0,8 s).
LaMa-MPE là **ứng viên thay big-lama**: chất lượng ngang (0 vùng sót nét, MAE 26,8 / 26,9), nhanh gấp đôi trên CPU, nạp ~1 s thay vì ~25 s. Trước khi đổi cần: đo trên 25 trang nhóm, và biết dữ liệu học (dự án không ghi, xem bảng dữ liệu học bên dưới).
Việc nên làm sớm, không phụ thuộc chọn model: xuất lại big-lama qua mạng viết lại để bỏ thời gian chờ nạp.

**Các bước vẽ lại khác của manga-image-translator (đọc mã nhánh `main`, 20/10).**
- **Nới mặt nạ:** nét chữ được nới ra quanh nét theo cỡ chữ: hình elip rộng 0,3 × (cỡ chữ + 20) (`mask_dilation_offset` mặc định 20), rồi thêm 3 px. Với chữ 20 px, lỗ nới ra khoảng 7 px; chữ 40 px khoảng 10 px. Mình nới cố định 3 px.
  Đã thử bằng `INPAINT_GROW` (auto + big-lama, một lượt mỗi dòng; số trong ô là sót nét / vá lộ / vẽ lại cả khung):

  | Nới quanh nét | 10 trang GT | 25 trang nhóm |
  |---|---|---|
  | 3 px (đang dùng) | 0 / 3 / 3 | 7 / 20 / 11 |
  | 0,15 × cỡ chữ (ít nhất 3 px) | 0 / 3 / 3 | 7 / 19 / 11 |
  | Như manga-image-translator | 1 / 4 / 4 | 7 / **15** / 10 |

  Nhìn ảnh cắt cạnh nhau không thấy cách nới rộng sạch hơn rõ. Ở vài chỗ nó vẽ lại thêm tranh quanh chữ (vệt xám cạnh tai mèo ở ARMS-006, mảng mờ rộng hơn trong nền tone). Cờ "vá lộ" giảm trên bộ nhóm một phần vì vòng đo quanh lỗ dời ra xa. **Giữ 3 px**; `INPAINT_GROW=text|mit|<px>` để thử.
- **Lọc mặt nạ:** họ chia nét của model thành từng mảng liền, gán mỗi mảng cho dòng chữ gần nhất, bỏ mảng to hơn dòng chữ hoặc nằm xa nó. Sau đó họ làm khít mép bằng dense CRF trên ảnh đã lọc bilateral. Phần gán mảng và bỏ mảng lớn giống luật "nằm ≥ 80% trong khung, cỡ giống chữ" của mình. Dense CRF nặng và mặt nạ của mình đã bám mép theo độ sáng, nên chưa làm.
- **Độ phân giải vẽ lại:** họ vẽ lại cả trang một lần, ở đúng tỷ lệ gốc (cạnh dài tới 2 048 px, mặc định `lama_large` = LaMa manga). Ở trên đã đo: cho LaMa nhìn tranh đúng tỷ lệ (cửa sổ 512 px) kém hơn phóng crop lên 512. Vẽ cả trang một lần chủ yếu đỡ số lần gọi model, không làm sạch hơn, nên giữ cách vẽ từng vùng.
- **Bóng thoại trắng:** họ không xử lý riêng, chữ trong bóng cũng do LaMa vẽ lại. Mình tô lòng bóng bằng đúng màu giấy (chính xác tuyệt đối với bóng phẳng), chỉ bóng có tone/chuyển màu mới qua bước vẽ lại. Các bản LaMa chính là loại để lại bóng xám trên giấy trắng, nên giữ cách của mình. Bước "retouch" bóng thoại đang làm trong `packages/render`.
- **Lọc chữ ngoài bóng (`ignore_bubble`):** tùy chọn bỏ qua chữ không nằm trong bóng trắng/đen. Không hợp với mình, vì mình dịch cả chữ tự do trên tranh.
Lỗi lớn nhất lại nằm ở **mặt nạ**: nét gạch chéo trong khung chữ bị coi là chữ và bị xóa. Đã sửa bằng phép thử "trường gạch" (hướng gạch đọc từ ngoài khung, lan vào trong theo từng nét song song): độ phủ lỗ trang 2 giảm 0,34 → 0,23, vùng gạch giữ nguyên.

**Mặt nạ học máy (thử nghiệm, tắt mặc định, bật bằng `INPAINT_TEXTMASK=1` hoặc `ctm`, hay `ctd`).** Đã thử hai model.
Model thứ hai (20/10) là **comic-text-detector**, lớp mặt nạ mà manga-image-translator dùng: GPL-3.0, dùng nguyên file ONNX dự án công bố (release `beta-0.3`, sha256 `1a86ace7…718f`, 95 MB). Nó chạy một lần cho cả trang (1024×1024), không chạy theo từng vùng. Koharu SAM-TS-L (Apache-2.0) nặng 0,3 tỷ tham số → chưa thử.
Dùng **TareHimself/comic-text-mask** (MIT, U-Net ResNet-18, 14,3 triệu tham số, 57 MB, crop 384×384; @`ebd37f1a`, safetensors sha256 `ab28dd84…f988`): đọc crop vùng chữ, trả xác suất từng điểm ảnh là chữ. Đồ thị ONNX dựng lại từng phép từ safetensors, không chạy mã tải về (182/182 tensor; sha256 `e8b5cb31…fcd01`).
Lưu ý giấy phép: dữ liệu học là chữ tổng hợp vẽ lên nền tự sinh và "trang truyện thật đã làm sạch" không nêu nguồn — hỏi tác giả trước khi đưa vào gói trả phí.

| Đo trên 10 trang GT (54 vùng chữ trên nền tranh) | Luật (`artTextMask`) | Luật + comic-text-mask | Luật + comic-text-detector |
|---|---|---|---|
| Model trùng luật (trung vị) | — | 95% nét model nằm trong lỗ của luật; 90% lỗ của luật có nét model | 67% / 90% (mặt nạ cả trang có cả chữ vùng bên cạnh; luật chỉ nhận nét nằm trong khung) |
| Khung chữ nhật dự phòng (không tách được nét) | 3 | 2 | 2 |
| Điểm ảnh lỗ | 682 777 | 682 869 (+47 954 nét chữ luật bỏ sót, −47 862 chấm tone/khung dự phòng) | 662 062 (+17 617 / −38 332) |
| Vẽ lại cả trang (auto + LaMa, một lượt 19/10): sót nét / vá lộ / vẽ lại cả khung | 1 / 5 / 4 | 1 / 4 / **1** | — |
| Như trên, đo lại 20/10 với code hiện tại | 0 / 3 / 3 | 0 / 2 / **0** | 0 / **1** / 2 |
| Khung chữ Việt chạm nhau | 0 | **0** sau khi sửa dàn chữ (trước đó 2: MN109-02 r1+r2, MN109-05 r7+r8) | 0 |
| Thời gian model | — | 33 ms/vùng DirectML, 136 ms CPU | 253 ms/trang DirectML, 1,6 s/trang CPU |

Đo lại trên bộ của nhóm: 25 trang đã có bản dịch Haiku lưu sẵn (`team25`; 25 trang còn lại của bộ 50 chưa có bản dịch lưu nên chưa đo). Vẽ lại cả trang bằng auto + big-lama, `INPAINT_DEVICE=dml`, mỗi chế độ một lượt, cùng bản dàn chữ đã sửa:

| 25 trang nhóm (416 vùng có chữ Việt) | Luật | Luật + model |
|---|---|---|
| Sót nét dưới chữ Việt | 10 | **8** (sạch thêm 3, sót mới 1: ARMS-008 r10) |
| Vá lộ | 28 | **24** |
| Vẽ lại cả khung (nét lọt mặt nạ) | 14 | **11** |
| Khung chữ nhật dự phòng | 2 | **0** |
| Khung chữ Việt chạm nhau | 1 | 1 (cùng một cặp ở cả hai chế độ: hai bóng thoại chồng lên nhau, UchiNoNyan'sDiary-006 r4+r5, không do model; đã sửa 20/10, xem dưới) |
| Thời gian vẽ lại 25 trang | 63,8 s | 61,4 s |

Đo lại 20/10 với code hiện tại, thêm comic-text-detector (cùng 25 trang, auto + big-lama, `INPAINT_DEVICE=dml`, một lượt mỗi cột):

| 25 trang nhóm (416 vùng có chữ Việt) | Luật | + comic-text-mask | + comic-text-detector |
|---|---|---|---|
| Sót nét dưới chữ Việt | 7 | 7 | 7 |
| Vá lộ | 20 | **15** | 21 |
| Vẽ lại cả khung (nét lọt mặt nạ) | 11 | 10 | **8** |
| Khung chữ nhật dự phòng | 2 | **0** | 1 |
| Khung chữ Việt chạm nhau | 0 | 0 | 0 |

Model chỉ là tín hiệu thứ hai, không nới phép bảo vệ nào: nó **thêm** nét luật bỏ sót (chữ dính nét tranh, mực nhạt) chỉ khi là mực cùng chiều với chữ, nằm ≥ 80% trong khung, không thuộc vùng bảo vệ (mắt, mảng tô đặc, trường gạch) và không phải nét thẳng dài hơn một chữ;
**thay** khung chữ nhật dự phòng bằng nét chữ khi luật không tách được; **bỏ** "nét" luật mà model hoàn toàn không thấy (chấm screentone) khi model thấy rõ chữ trong khung. Chữ trang trí nét đậm vẫn giữ là tranh (quyết định trước model). Bước kiểm sót nét sau vẽ lại vẫn chạy như cũ.
Hai cặp khung chạm nhau là lỗi ở bước dàn chữ mà model chỉ làm lộ ra (xóa chữ ở hai vùng đó vẫn sạch). Chữ Việt của lời tự do được nới vào giấy trống tới sát khung vùng bên cạnh. Vì vậy hai cột cạnh nhau có thể cùng chiếm một khe: ở MN109-02, nét model làm khung nét r1 gần bằng khung vùng, nên r1 bắt đầu từ khung vùng và nới sang trái đúng vào khe r2 cũng nới tới. Khung của lời nghĩ cũng có thể chui dưới góc chữ của bóng bên cạnh: ở MN109-05 r7, không có model thì chỉ hở 1 px.
Đã sửa trong `packages/render`: sau khi dàn xong, lời tự do nào chạm chữ đã đặt thì được dàn lại, bắt đầu từ phần khung không chạm chữ đó và không nới vào nó. Trên 10 trang GT chỉ 3 vùng đổi: có model, MN109-02 r2 giảm 34 → 29 px và MN109-05 r7 giảm 13 → 11 px; không model, MN109-05 r7 dời xuống 8 px, giữ cỡ chữ. Trên 25 trang nhóm chỉ 1 vùng đổi: có model, UchiNoNyan'sDiary-000 r4 giảm 34 → 32 px (cùng trang với MN109-02).
Từ 20/10 bước này xét cả bóng thoại: bóng xếp trước, lời tự do sau, theo thứ tự đọc. Hai bóng vẽ chồng nhau thành một vùng giấy (UchiNoNyan'sDiary-006 r4+r5) có khung trong lấn vào nhau, nên chữ hai bóng giành phần giữa. Bóng sau được dàn lại trong khung trong của nó, bỏ phần chữ bóng trước đã chiếm: r5 dồn sang nửa trái bóng, giữ cỡ 15 px.
Đo lại 20/10 (vẽ lại cả trang auto + big-lama, `INPAINT_DEVICE=dml`, một lượt mỗi chế độ; cây mã lúc đo có thay đổi vẽ lại chưa commit của phiên chính): **0 cặp khung chữ chạm nhau** trên 10 trang GT và 25 trang nhóm, cả khi tắt lẫn bật model (`.private/qa/balloon-*`). Kiểm thử ở `packages/render/test/layout.test.ts` có ba ca: hai cột chung một khe, lời nghĩ chui dưới góc bóng, và hai bóng chồng nhau. Mỗi ca đều hỏng với code trước khi sửa; ca hai bóng hỏng cả với bản chỉ xét lời tự do.
**Chốt:** về chất lượng, model đã đáng bật. Trên 10 trang GT, vẽ lại cả khung giảm 4 → 1 và vá lộ 5 → 4. Trên 25 trang nhóm, sót nét giảm 10 → 8, vá lộ 28 → 24, vẽ lại cả khung 14 → 11. Ở cả hai bộ, model không thêm cặp khung chữ chạm nhau nào. Vẫn **để tắt mặc định** vì còn đúng một điều kiện: nguồn "trang truyện thật đã làm sạch" trong dữ liệu học chưa rõ. Khi tác giả xác nhận nguồn sạch thì bật mặc định (`apps/server/src/inpaint.ts`); nếu muốn chắc hơn, đo thêm 25 trang còn lại sau khi có bản dịch lưu.
comic-text-detector (20/10) **không hơn** comic-text-mask. Trên 25 trang nhóm nó ít vẽ lại cả khung nhất (8 so với 10), nhưng vá lộ không giảm (21 so với 15). Nó nặng hơn (95 MB, 1,6 s/trang CPU) và học trên Manga109-s nên không dùng được cho gói trả phí (bảng dưới). Giữ comic-text-mask là ứng viên.

**Dữ liệu học của từng model.** Giới hạn cho gói trả phí nằm ở dữ liệu, không ở giấy phép mã (dự án mã nguồn mở, GPL dùng được):

| Model | Dữ liệu học | Ảnh hưởng tới gói trả phí |
|---|---|---|
| MI-GAN (bản Places2 512) | Places2 | Điều khoản Places: nghiên cứu/giáo dục phi thương mại (theo nguồn thứ cấp, cần đọc văn bản gốc) |
| LaMa (big-lama), LaMa bản OpenCV | Places365-Challenge | Như trên |
| LaMa manga (dreMaz) | big-lama + "300k ảnh manga/anime", không nêu nguồn | Chưa rõ; nền là big-lama nên mang điều khoản Places |
| AOT, LaMa-MPE (manga-image-translator) | Dự án không ghi | Chưa rõ |
| comic-text-detector | Manga109-s + Digital Comic Museum + ảnh tổng hợp | **Manga109-s chỉ cho học thuật** → không dùng cho gói trả phí |
| comic-text-mask | Chữ tổng hợp trên nền tự sinh + "trang truyện thật đã làm sạch" không nêu nguồn | Chưa rõ |

Nghĩa là cả hai engine đang mặc định (MI-GAN, big-lama) cũng học trên Places. Trước khi bán gói cloud cần kiểm tra điều khoản Places gốc, hoặc tìm model vẽ lại học trên dữ liệu cho phép thương mại.

Nguồn ý tưởng: [so sánh với manga-image-translator](reference/compare-manga-image-translator.md).

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
| Extension chạy trên trang web thật | — | — | Sau MVP (nhóm chốt 20/10: MVP không cần extension) |
| Cloud: tài khoản + credit | — | — | Sau MVP (giá đã tính: [COST-PRICING.md](COST-PRICING.md)) |
| Local/offline (Ollama) | — | — | ✅ có hướng dẫn cài |
| Đọc thư mục ảnh/ZIP của mình (thay extension trong MVP) | — | — | ✅ dịch trước trang kế, cache |
| Gán người nói + xưng hô, đo PCA trên nhãn của nhóm | — | — | ✅ ([PROPOSAL-REVIEW.md §7, §9](PROPOSAL-REVIEW.md)) |
| "Tóm tắt đến đây" không spoil | — | — | ✅ |
| Chat hỏi về truyện, mobile, thêm ngôn ngữ | — | — | Sau MVP |

## 6. Mô hình kinh doanh (giả thuyết, chốt sau khi đo chi phí thật)

Số đo 20/10 (~18 đ/trang với DeepSeek; một bộ 200–300 chương ~80–120k tiền model), các cách giảm chi phí và đề xuất gói
39k (1.000 trang) / 99k (8.000 trang) / nạp thêm, chọn bằng mô phỏng thói quen đọc: [COST-PRICING.md](COST-PRICING.md). Đối chiếu với proposal của nhóm và kịch bản thuyết trình 5 phút:
[PROPOSAL-REVIEW.md](PROPOSAL-REVIEW.md).

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
