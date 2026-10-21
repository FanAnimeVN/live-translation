# Kế hoạch: từ MVP tới bản beta công khai (extension + web reader)

Trạng thái: **chờ duyệt** (21/10/2026). Không có bước nào dưới đây được làm trước khi nhóm đồng ý, trừ đợt đo model local trên Kaggle mà nhóm đã yêu cầu.
Bằng chứng cho các quyết định: [báo cáo nghiên cứu](../reports/Model%20local%20v%C3%A0%20g%C3%B3i%20beta%20VN.md) (ghi chú gốc ở `research_notes/Model local và gói beta VN/`), [COST-PRICING.md](COST-PRICING.md), [CLOUD.md](CLOUD.md), [PROPOSAL-REVIEW.md](PROPOSAL-REVIEW.md).

## 1. Bản beta công khai cần gì (yêu cầu)

Beta công khai = **vài trăm người đọc lạ** cài được trong 2 phút, đọc trọn một chương raw mà không cần người trong nhóm hỗ trợ, và nhóm đo được họ đọc bao nhiêu và có trả tiền không.

| # | Yêu cầu | Hiện có | Còn thiếu |
|---|---|---|---|
| R1 | Extension Chrome/Edge dịch ngay trên trang đang đọc | chưa có (MVP đã bỏ, [PROPOSAL-REVIEW.md:19](PROPOSAL-REVIEW.md)) | toàn bộ |
| R2 | Web reader mở thư mục/ZIP, chạy cả trên điện thoại | demo chỉ mở 60 trang của bộ dữ liệu ([PROPOSAL-REVIEW.md:20](PROPOSAL-REVIEW.md)) | toàn bộ phần mở file, PWA |
| R3 | Ba chế độ: Cloud (credit), BYOK, Local | Cloud gọi OpenRouter bằng key của server; Local gọi Ollama `/v1` ([apps/server/src/openrouter.ts:59-73](../apps/server/src/openrouter.ts)) | tài khoản/credit; BYOK; local đúng cấu hình |
| R4 | Model đã chốt cho từng chế độ, có số đo | cloud đã đo (Haiku mặc định, DeepSeek nhanh, [COST-PRICING.md §9.1](COST-PRICING.md)) | local chưa có model đạt; định tuyến lai chưa đo |
| R5 | Gói giá VND + thu tiền trong nước | đề xuất 39k/99k dựa trên giả định ([COST-PRICING.md §6.4](COST-PRICING.md)) | kiểm chứng, cổng thanh toán, điều khoản |
| R6 | UI/UX đẹp, tiếng Việt, dễ hiểu | demo React một trang ([apps/demo/src/App.tsx](../apps/demo/src/App.tsx)) | design system, onboarding, popup, side panel, trang giá |
| R7 | Ổn định | chưa có SLO, chưa có kiểm thử hồi quy tự động trên trang thật | cổng chất lượng trước mỗi bản phát hành |
| R8 | Hiệu ứng âm thanh (SFX), danh xưng, xưng hô | prompt v5 + thẻ "Ai là ai?" | chế độ SFX, từ điển SFX Nhật→Việt |
| R9 | Pháp lý tối thiểu để thu tiền | chưa có | đăng ký hộ kinh doanh, điều khoản, chính sách riêng tư/hoàn tiền |

## 2. Quyết định đề xuất (cần nhóm chốt)

### 2.1 Chế độ Local: đổi kiến trúc, không dùng "một model đọc ảnh làm hết"

Bằng chứng (báo cáo §1):
- Trên benchmark MangaOCR, mọi model đọc ảnh ≤ 14B đều gần 0 điểm. Thử thực tế với qwen3-vl và gemma4 trên Ollama: hoặc ra trống, hoặc bịa thoại.
- Model OCR cắt từng bóng nhỏ (54M–1B) đạt CER 1,5–5% trên 7.789 bóng (JMangaBench, tác giả tự công bố).
- Model dịch chữ Hy-MT2-7B đã đạt chrF 33,8 trên máy nhóm (Haiku 38,7).

**Lỗi cấu hình đã tìm ra và sửa hôm nay (đo trên máy nhóm: Ollama 0.40.6, RTX 4060 Laptop, 3 trang của bộ 25 trang):**
- **Nguyên nhân:**
  - Chế độ local gửi đúng prompt v5 của cloud: system prompt ~2.400 token, thêm ảnh trang và tới 19 ảnh cắt.
  - Prompt đi qua endpoint `/v1` của Ollama. Endpoint này không đặt được `num_ctx`, và ngữ cảnh mặc định chỉ có 4.096 token.
- **Hệ quả:** Ollama **từ chối hẳn** yêu cầu: "request (5383 tokens) exceeds the available context size (4096 tokens)". Chế độ đọc ảnh local đã hỏng vì cấu hình, không phải vì model.
- **Đã sửa:**
  - Khi server local là Ollama, sản phẩm gọi API gốc `/api/chat` với `num_ctx` = `LOCAL_NUM_CTX` (mặc định 16.384) ([apps/server/src/openrouter.ts](../apps/server/src/openrouter.ts), [apps/server/src/env.ts](../apps/server/src/env.ts)).
  - LM Studio và các server tương thích OpenAI khác vẫn dùng `/v1`.
- **Sau khi sửa,** `gemma4:e2b` chạy đủ 3 trang, 58/58 vùng đúng khuôn, 17 s/trang. Nhưng **mọi ô chữ Nhật và chữ Việt đều rỗng** (CER 100%): nó không bịa, nó không đọc được.
- **Kết luận:** model đọc ảnh nhỏ không thay được OCR. Chế độ local phải tách thành hai bước, như bảng dưới đây.

Pipeline local mới:

| Bậc máy | Đọc chữ | Dịch | Người nói / xưng hô |
|---|---|---|---|
| Không cài gì (Chrome desktop) | detector + OCR cắt bóng chạy trong trình duyệt (ONNX Runtime Web, WebGPU/WASM) | Chrome Translator API `ja→vi` (có sẵn từ Chrome 138, chất lượng **chưa đo**) | không có (ghi rõ) |
| GPU 6–8 GB (RTX 3050/4050/4060) | như trên, hoặc chạy trong server local | Hy-MT2-7B Q6_K (6,2 GB) qua Ollama/llama-server, theo template chính thức | model đọc ảnh 4B chỉ *đề xuất* người nói (tùy chọn, chạy sau) |
| GPU 12–16 GB / Mac 16 GB | như trên | model thắng trong đợt đo Kaggle (Hy-MT2 Q8, TranslateGemma 12B, Gemma 4 12B hoặc Qwen3.5-9B theo trang) | Qwen3.5-9B / Gemma 4 12B đọc trang |
| Chỉ CPU | NAR/Baberu ONNX (~60 ms/bóng) | Hy-MT2-1.8B (1,5 GB) | không |

Giấy phép:
- **CPT-flex và NAR-small** là CC BY-NC-SA (không thương mại). Chỉ dùng được ở chế độ local miễn phí, người dùng tự tải về. Muốn dùng ở gói trả phí phải xin phép tác giả.
- **Manga109-s** cho phép dùng model đã huấn luyện vào mục đích thương mại nếu ghi nguồn. Ghi chú nghiên cứu viết vậy, nhưng chưa đọc được bản thỏa thuận đầy đủ nên **cần người hiểu luật xác nhận**. Nếu đúng, `comic-text-detector`, manga-ocr và PaddleOCR-VL-For-Manga có thể dùng lại ở gói trả phí. Điều này thay đổi kết luận ở [COST-PRICING.md §7](COST-PRICING.md).

### 2.2 Model cho từng chế độ

| Chế độ | Mặc định | Tùy chọn | Ghi chú |
|---|---|---|---|
| Cloud "Chuẩn" | Claude Haiku 5.5 | — | CER 14,4%, chrF 38,2, $0,0014/trang đôi ([COST-PRICING.md §9.1](COST-PRICING.md)) |
| Cloud "Nhanh" | DeepSeek V4.1 Flash 1017, tắt suy nghĩ | — | bóng đầu 4,2 s, đọc sai nhiều hơn (CER 20,5%) |
| Cloud "Cao cấp" | Gemini 3.1 Flash-Lite | bật riêng từng bộ | chrF 43,4, đắt ~7 lần |
| Thử nghiệm | **định tuyến lai**: DeepSeek cho trang dễ, Haiku cho trang nhiều chữ nhỏ | — | đo trước khi bật (~$0,05) |
| BYOK | key OpenRouter (mọi model trong danh sách), key Gemini, key Anthropic | key DeepSeek trực tiếp | key nằm ở `chrome.storage.local`, gọi thẳng nhà cung cấp, server không thấy key |
| Local | theo bảng §2.1 | mọi server tương thích OpenAI (LM Studio :1234, KoboldCpp :5001, llama-server) | không bao giờ tự chuyển sang cloud |

Vì sao không bán "10 engine" như Immersive Translate:
- DeepL, Google, Microsoft dịch chữ thuần nên không nhìn thấy tranh. Không biết ai nói với ai thì đoán sai xưng hô.
- Tính theo trang, chúng còn **đắt hơn** model nhỏ: ~$0,004–0,014 so với ~$0,0004–0,002 (báo cáo §3).
- Người khác dùng chúng vì tên quen, vì người dùng sẵn có key, và vì "đổi engine" bán được như gói nâng cấp. Ta chỉ cần để BYOK mở cho người thích tự chọn.

### 2.3 Gói giá (bản đề xuất, đo lại trong beta)

Bằng chứng mới (báo cáo §2):
- **Mức vào dưới 50k là hợp lý:** MangaToon VIP ở Việt Nam là 47k, MANGA Plus 29k/99k, Spotify Student 33k.
- **Mức sẵn sàng trả 120k–160k của người đọc nặng chưa có căn cứ:** các gói AI cũng chỉ ở mức ~132k. 99k nên là **trần**.
- **Người Việt quen trả trước, không tự gia hạn.** Ví dụ: gói 3/6/12 tháng trả trước của Spotify, thẻ game mệnh giá 20k/50k/100k.
- **Luật bảo vệ người tiêu dùng** buộc nhắc trước khi hết hạn và cho hủy bất cứ lúc nào.

| Gói | Giá | Bao gồm | Thay đổi so với §6.4 |
|---|---|---|---|
| Miễn phí | 0 đ | Local + BYOK không giới hạn; thử 1 trang không cần tài khoản; **5 trang cloud/ngày, công bố rõ** (~150/tháng, giá vốn ~3.900 đ/người hoạt động) | 30 trang/tháng quá ít so với đối thủ (Sumi 5/ngày, Kites 100/ngày, IsManga 40/tuần) |
| Đọc | 39k/tháng (trả trước) | 1.000 trang | giữ; thêm nhánh thử 29k; tránh 49k (trùng YouTube Lite web) |
| Cày | **79k/4.000 hoặc 99k/5.000 trang** (~20 đ/trang) | vượt quota thì đọc tiếp bằng DeepSeek tới 300 trang/giờ | 99k/8.000 chỉ thu 12,4 đ/trang, giá vốn đo được 18–26 đ: lỗ 45–109k mỗi người dùng hết |
| Vé 7 ngày | 15–20k | ~300 trang | **mới**: người Việt quen gói data 7 ngày |
| Nạp thêm (chỉ cho người đã có gói) | 20k / 50k / 100k | 500 / 1.280 / 2.560 trang (~39–40 đ/trang, không rẻ hơn Đọc) | mệnh giá thẻ game; không bán rẻ hơn Đọc để khỏi ăn mòn gói |
| Năm | ~−30% | như gói tháng | giữ; vẫn nhắc trước khi hết hạn |
| Nhóm (thử) | — | nhiều hồ sơ, bộ nhớ truyện riêng từng người | chia sẻ tài khoản là chuyện chắc chắn xảy ra; gói nhóm dễ chuyển đổi hơn đi bắt đăng nhập chung |

Thuế 2026 có lợi cho nhóm:
- Hộ kinh doanh dưới 1 tỷ đ/năm không chịu VAT.
- VietQR gần như miễn phí.
- Hai điều này trả lại ~13% doanh thu mà mô hình cũ đã trừ, đủ để giữ Đọc ở 39k.

**Quy tắc chốt sau beta:**
- Chạy lại `tools/eval/src/pricing.ts` với phân bố trang/tháng thật.
- Giữ bộ giá nào thì phải có biên lãi dương ở trung vị người dùng trả tiền.
- Bộ đó phải phục vụ được ít nhất 60% người đọc nặng.

### 2.4 Thu tiền và pháp lý (tóm tắt; cần người có chuyên môn xác nhận)

**Thu tiền:**
- **Beta:** VietQR chuyển khoản qua **payOS** hoặc **SePay**, webhook tự cộng credit. Cả hai miễn phí, đăng ký bằng CCCD.
- **Không dùng Stripe hay ExtensionPay:** Stripe không nhận pháp nhân Việt Nam.
- **Ra mắt:** thêm MoMo, cần tài khoản doanh nghiệp. Polar, Lemon Squeezy hoặc Paddle chỉ dành cho gói năm tính bằng USD; phí ~5% + $0,50.

**Pháp lý:**
- Đăng ký hộ kinh doanh trước khi thu tiền. Doanh thu dưới 1 tỷ đ/năm được miễn VAT và thuế TNCN (Nghị định 141/2026). Tài khoản ngân hàng dùng để thu tiền phải khai với cơ quan thuế.
- Trang web phải công bố giá, cách thanh toán, chính sách hủy/hoàn tiền và chính sách riêng tư, và có bước "Tôi đồng ý" khi tạo tài khoản (Luật Thương mại điện tử 122/2025).
- **Lịch sử đọc có thể bị coi là dữ liệu nhạy cảm** theo Nghị định 356/2025. Vì vậy bộ nhớ truyện và lịch sử đọc **mặc định chỉ lưu trên máy**; đồng bộ lên server phải do người dùng bật.
- **Rủi ro bản quyền** của một dịch vụ thu phí dịch raw: chưa nghiên cứu. Cần hỏi luật sư trước khi thu tiền. Giữ các nguyên tắc: không cache dùng chung, không lưu ảnh, không quảng bá trang lậu.

### 2.5 UI/UX: học từ đối thủ lớn, cộng điểm khác biệt Nhật–Việt

**Nên học từ đối thủ:**
- Thử ngay một trang.
- Danh sách trang web đã kiểm tra, kèm form "đề xuất trang".
- Giá ghi bằng chương và VND.
- Bảng "chi tiết" cho mỗi trang: model, chi phí, trang đã có sẵn trong cache.
- Từ điển thuật ngữ ở mọi gói.
- Giữ một phím để xem bản gốc.
- Một tài khoản dùng chung cho extension, web và điện thoại.

**Điểm riêng của ta (chưa đối thủ nào ghi trong tài liệu):**
- Cài đặt riêng cho từng bộ truyện: mức giữ danh xưng, kiểu xưng hô, chế độ SFX.
- Thẻ "Ai là ai?".
- Tóm tắt không spoil.
- Chế độ local riêng tư thật.

**SFX:**
- Mặc định **chú thích nhỏ, xóa được** cạnh chữ gốc; không xóa nét vẽ.
- Mỗi bộ chọn được: tắt / chú thích / thay hẳn.
- Thêm từ điển ~200 từ tượng thanh Nhật → Việt do nhóm soạn. Không tìm thấy quy ước Việt nào có sẵn.
- Không chắc nghĩa thì đánh dấu, không bịa.

## 3. Các bước thực hiện

Ước lượng theo nhịp hiện tại (Claude làm lõi, nhóm review và kiểm thử). Mỗi giai đoạn có tiêu chí "xong khi" đo được.

### Giai đoạn 0 — Ổn định và đo (tuần 1)
1. **Sửa chế độ local:**
   - ✅ Đã làm 21/10: gọi Ollama bằng `/api/chat` với `num_ctx` 16.384.
   - Còn lại:
     - pipeline hai bước "detector → OCR cắt bóng → model dịch" chạy trong server local;
     - báo lỗi rõ khi prompt dài hơn ngữ cảnh;
     - prompt local gọn hơn cho model đọc ảnh (ít ảnh cắt, system prompt ngắn).
   - File: [apps/server/src/pipeline.ts](../apps/server/src/pipeline.ts), [packages/core/src/prompt.ts](../packages/core/src/prompt.ts).
2. **Đo model local trên Kaggle:**
   - Gói 25 trang ([tools/eval/src/kaggle-pack.ts](../tools/eval/src/kaggle-pack.ts)) và script 2×T4 ([tools/kaggle/local-models.py](../tools/kaggle/local-models.py)).
   - Ba nhóm phép đo: 5 model OCR cắt bóng; 10+ cấu hình dịch; 5 model đọc trang.
   - Chấm trên máy nhóm bằng `tools/eval/src/kaggle-score.ts`, cần mở rộng cho OCR/MT/MT2.
3. **Đo định tuyến lai DeepSeek → Haiku** trên 25 trang (~$0,05).
4. **Cổng chất lượng tự động** `npm run gate`: chạy lại 25 trang của nhóm, báo coverage, CER, chrF, p50/p95 độ trễ, lỗi JSON. Phát hành bị chặn nếu tụt quá ngưỡng ở §4.
5. **Độ ổn định cloud:**
   - Timeout và tự chuyển nhà cung cấp khi token đầu > 12 s.
   - Thống kê lỗi theo nhà cung cấp trong `ledger.jsonl`.
   - Giới hạn ngân sách theo người dùng.

### Giai đoạn 1 — Web reader + chia sẻ cho bạn bè (tuần 2)
6. **Reader:**
   - Mở thư mục/ZIP; đọc cuộn dọc hoặc từng trang; dịch trước 2–3 trang; cache chữ và tọa độ (không lưu ảnh); giữ Space xem bản gốc.
   - Đây là khoảng trống lớn nhất của MVP ([PROPOSAL-REVIEW.md §7](PROPOSAL-REVIEW.md)).
7. **Chế độ chia sẻ:**
   - Mã mời; hạn mức trang/ngày cho mỗi người; trần ngân sách chung.
   - Tắt các route dataset/judge/reset.
   - Cloudflare Tunnel cho 10–20 bạn bè thử trên cả điện thoại.

### Giai đoạn 2 — Extension MV3 (tuần 3–4)
8. **Phần đọc trên trang:**
   - Content script tìm ảnh truyện (`<img>`, canvas; nếu ảnh bị xáo thì chụp vùng đang xem).
   - Dịch ảnh đang thấy và dịch trước ảnh kế.
   - Lớp phủ dùng chung `packages/render`.
9. **Chạy trong trình duyệt:**
   - Detector và OCR cắt bóng chạy bằng ONNX Runtime Web trong offscreen document.
   - Đây là điều kiện để BYOK và local chạy **không cần server của nhóm**.
10. **Giao diện extension:**
    - Popup: bật/tắt theo trang, chọn chế độ, xem credit.
    - Side Panel: bộ nhớ truyện, "Ai là ai?", từ điển, cài đặt từng bộ.
    - Trang cài đặt: BYOK, local.
11. **Kết nối local:**
    - Dò các cổng 11434/1234/5001/8080 trên 127.0.0.1.
    - Ollama trả 403 cho origin `chrome-extension://`, nên cần ghi đè Origin bằng `declarativeNetRequest` (nếu không được thì hướng dẫn đặt `OLLAMA_ORIGINS`).
    - Khi thiếu server hoặc model quá lớn, báo rõ cho người dùng.

### Giai đoạn 3 — Tài khoản, credit, thu tiền (tuần 4–5, song song được)
12. **Tài khoản:** Supabase Auth (email OTP, Google); sổ credit theo kiểu giữ chỗ → quyết toán → hoàn khi lỗi ([CLOUD.md §3](CLOUD.md)); mã mời.
13. **Thu tiền:**
    - Webhook payOS/SePay cho gói nạp.
    - Trang giá bằng VND.
    - Nhắc trước 7 ngày khi gói tháng sắp hết hạn; không tự gia hạn.
    - Đăng ký hộ kinh doanh và soạn điều khoản trước khi bật thu tiền.

### Giai đoạn 4 — Hoàn thiện và phát hành beta (tuần 5–6)
14. **Thiết kế và nội dung:**
    - Design system tiếng Việt: màu, chữ, trạng thái lỗi, chế độ tối.
    - Onboarding chọn chế độ theo phần cứng máy.
    - Chế độ SFX và từ điển SFX.
    - Bảng "chi tiết" cho mỗi trang.
    - Hướng dẫn cài local, chính sách riêng tư, điều khoản.
15. **Phát hành:**
    - Chrome Web Store dạng Unlisted ($5 một lần) và Edge Add-ons (miễn phí).
    - Danh sách trang đã kiểm tra.
    - Form báo lỗi dịch cho từng bóng; người dùng đồng ý thì mới gửi chữ.

## 4. Tiêu chí nghiệm thu (đo được)

| # | Tiêu chí | Ngưỡng | Cách đo |
|---|---|---|---|
| A1 | Chất lượng cloud không tụt | coverage ≥ 95% ô chữ GT; CER ≤ 15%; chrF ≥ 38 (Haiku, 25 trang) | `npm run gate` |
| A2 | Tốc độ cloud | bóng đầu p95 ≤ 6 s (Nhanh) / ≤ 12 s (Chuẩn); trang đã dịch trước hiện ≤ 0,3 s | `tools/eval/src/latency.ts` + log beta |
| A3 | Ổn định | ≤ 1% trang lỗi không tự phục hồi; 0 lần tính tiền khi lỗi | `ledger.jsonl`, sổ credit |
| A4 | Local (GPU 8 GB) | chrF ≥ 34 (≥ 88% của Haiku) trên 419 bóng; CER OCR ≤ 8%; ≤ 10 s/trang trên RTX 4060 Laptop | Kaggle + đo lại trên máy nhóm |
| A5 | Local không cài gì | chạy được trên Chrome desktop không cài gì; điểm chrF ghi rõ (chưa đặt ngưỡng) | đo sau khi làm |
| A6 | Offline đúng luật | chế độ local: 0 request ra host khác localhost (trừ lần tải model, có xin phép) | test mạng trong `npm run check` + kiểm tay bằng DevTools |
| A7 | Cài đặt | người lạ cài và dịch xong trang đầu trong ≤ 2 phút (cloud) / ≤ 15 phút (local, chưa tính tải model) | 5 người thử, bấm giờ |
| A8 | Đo thị trường | ≥ 30 người dùng beta 4 tuần; có phân bố trang/tháng, tỉ lệ raw, tỉ lệ chuyển đổi gói nạp | dashboard beta |

## 5. Rủi ro và cách giảm

| Rủi ro | Cách giảm |
|---|---|
| Model local vẫn không đạt A4 sau khi sửa ngữ cảnh | Local ghi rõ là "chất lượng thấp hơn cloud"; giữ BYOK Gemini làm đường miễn phí; cân nhắc fine-tune OCR/MT sau beta (Kaggle) |
| Trang truyện chặn extension hoặc xáo ảnh | Chụp vùng đang xem; danh sách trang đã kiểm tra; web reader làm đường dự phòng |
| Chi phí cloud vượt doanh thu ở người đọc nặng | Gói Cày 5.000 trang; giới hạn 300 trang/giờ; Batch API cho trang dịch trước |
| Rủi ro pháp lý khi thu tiền | Beta miễn phí trước; hỏi luật sư về bản quyền và dữ liệu; hộ kinh doanh trước khi thu tiền |
| Giấy phép model (NC, Manga109-s) | Bảng giấy phép theo từng chế độ trong `docs/`; gói trả phí chỉ dùng model cho phép thương mại |
| Ổ C còn 3,7 GB | Model và cache đặt ở D:; dọn ổ C trước khi cài thêm công cụ |

## 6. Kiểm chứng sau mỗi giai đoạn
- `npm run check` (tsc + vitest) xanh; `npm run gate` không tụt ngưỡng A1.
- Thử thật trong trình duyệt: Reader (giai đoạn 1), extension trên 3 trang web thật (giai đoạn 2), thanh toán ở chế độ thử (giai đoạn 3).
- Mỗi số đo ghi model, số lượt chạy, cold/warm, ngày, như quy tắc trong `AGENTS.md`.
