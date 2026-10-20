# Rà soát proposal và chuẩn bị thuyết trình 5 phút

Cập nhật 20/10/2026. Đối chiếu đề cương *"Two-Tier Context Engine cho LLM trong dịch manga Nhật–Việt"* của nhóm với những gì
repo này đã làm và đo được. Mục đích: biết MVP đang ở đâu, proposal lệch chỗ nào, tuần sau trình bày gì.

## 1. MVP đã xong chưa?

**Chưa.**
- **Đã đủ cho bài nói tuần sau:** phần lõi dịch, xóa chữ, dàn chữ và bộ nhớ truyện.
  Tuần sau chỉ trình bày ý tưởng 5 phút kèm demo nhẹ.
- **Còn thiếu so với MVP đã định** ([DIRECTION.md §5](DIRECTION.md)): phần vỏ sản phẩm. Extension chưa có, tài khoản/credit chưa có.

| Hạng mục MVP | Trạng thái | Số đo / ghi chú |
|---|---|---|
| Tìm vùng chữ + đọc + dịch cả trang có ngữ cảnh | ✅ mạnh | 60 trang, 946 ô chữ GT: **96,4% được dịch**, 1,5% giữ làm tranh, 2,1% bỏ sót (DeepSeek + detector thứ hai) |
| Bóng hiện dần, xem bản gốc, bấm bóng xem JP/VI | ✅ trong demo | Bóng đầu p50 **2,4 s** (DeepSeek, 10 trang) |
| Xóa chữ + dàn chữ Việt trong bóng và trên tranh | ✅ | Ngày 20/10, 60 trang: 993 vùng được dàn chữ; chữ đè lên chữ 0, tràn bóng 0. 4 vùng còn sót nét (ca khó, ghi ở mục 5) |
| Bộ nhớ truyện: xưng hô A→B có bằng chứng, mốc đọc, tóm tắt chương, nhắc tình tiết cũ không spoil, Đúng/Đổi/Bỏ | ✅ lõi + demo cơ bản | Chưa có Side Panel, lịch sử sửa, xuất/nhập |
| Extension chạy trên trang web thật | ⏸ để sau MVP | Nhóm chốt 20/10: MVP không cần extension. Thay bằng Reader mở chương của người đọc (mục 7) |
| **Reader mở chương của người đọc** (thư mục/ZIP) | ❌ chưa làm | **Khoảng trống lớn nhất của MVP**: demo hiện chỉ mở 60 trang của bộ dữ liệu |
| Cloud: tài khoản, credit, thanh toán thử | ❌ mới có thiết kế | [CLOUD.md](CLOUD.md), giá: [COST-PRICING.md](COST-PRICING.md) |
| Local (Ollama) | ⚠️ một phần | Đã đo model dịch chữ; model đọc ảnh chạy local chưa đạt |
| Đo **độ đúng đại từ** (chỉ số chính của proposal) | ⚠️ mới có số gần đúng | So với bản dịch chuẩn của nhóm: chỉ ~26–28% bóng dùng đúng bộ đại từ (mục 9). Cần nhãn đại từ chuẩn để đo PCA thật |

## 2. Proposal có lệch hướng không?

**Về vấn đề thì không lệch.** Proposal và sản phẩm cùng nhắm một lỗ hổng:
- tiếng Nhật lược chủ ngữ;
- xưng hô tiếng Việt là quan hệ có hướng và đổi theo cảm xúc;
- chữ dịch phải vừa bóng.

**Lệch về phạm vi và cách làm:**
- **Proposal:** chỉ làm "engine ngữ cảnh". Đầu vào là tọa độ + chữ Nhật có sẵn của Manga109. Viết bằng Python, model mặc định là Qwen2.5-3B chạy local.
- **Repo:** làm trọn đường đi, từ ảnh raw → tìm chữ → đọc + dịch có bộ nhớ → xóa chữ, vẽ lại nền → dàn chữ. Viết bằng TypeScript, dùng model đọc ảnh trên cloud.
- **Hai hướng ghép được.** Engine ngữ cảnh của proposal chính là phần "bộ nhớ truyện" của sản phẩm, và nên là **đóng góp nghiên cứu** của đồ án.

| Thành phần trong proposal | Trong repo hiện tại | Khuyến nghị |
|---|---|---|
| Thứ tự đọc Panel-First DAG (RTL ≥ 95%) | Thứ tự phải→trái theo hình học (`core/order.ts`); model sửa thứ tự khi đọc cả trang; tìm rãnh giữa khung bằng XY-cut (`core/gutters.ts`) | Giữ. Đo độ đúng thứ tự trên GT (rẻ, không tốn API) |
| Gán người nói lai ghép (vector đuôi bóng + yakuwarigo) | Model nhìn cả trang và tự ghi người nói/người nghe. Prompt v4: **58–77% câu thoại không rõ người nói, 80% không rõ người nghe** (Haiku/DeepSeek, 60 trang). Prompt v5 (20/10): còn 6–11% và 63–66%, nhưng đại từ mới nhích nhẹ (mục 9) | **Đây là chỗ proposal đóng góp thật.** Nên làm thành module chính và đo trước/sau |
| DRPG: đồ thị xưng hô có hướng | Đã có: luật A→B kèm bằng chứng (trang + vùng), mốc đọc; người đọc khóa thì luôn thắng (`core/memory.ts`) | Giữ, trình bày như đã có. **Sửa bài toán #9 (mục 3)** |
| Micro FIFO 15–25 câu + sub-graph + macro register | Đã có: thoại gần nhất + bộ nhớ ổn định (nhân vật, xưng hô, thuật ngữ) + tóm tắt chương + tìm lại sự kiện cũ; trần ~2.100 token | Giữ. Đo được ngay **CR** (token gửi đi so với toàn bộ lịch sử) |
| Flashback gating bằng OpenCV (F1 ≥ 92%) | Có một phần: phát hiện rãnh đen (`gutters.ts`); prompt nhắc khung tối/mờ; chưa có ngăn xếp trạng thái | Làm nếu còn thời gian. 50 trang có rất ít cảnh hồi tưởng nên F1 sẽ dao động mạnh. Hạ thành chỉ số phụ |
| Ngân sách âm tiết L_max | Hiện co chữ / ngắt dòng / tách từ **sau** khi dịch; chưa báo trước cho model | Rẻ, đáng làm: gửi trần ký tự mỗi vùng trong danh sách vùng, đo tỉ lệ phải co chữ trước/sau |
| Cache băm SHA-256 | Đã có: cache kết quả theo SHA-256 ảnh + phiên bản prompt/model | Giữ |
| Qwen2.5-3B local mặc định, Gemini 1.5 Flash | Đo 19/10: model chữ local đạt chrF 24–34 so với Haiku 38,7. Model chỉ đọc chữ không biết **ai nói với ai**. Cloud đọc ảnh hiện ~18 đ/trang, bóng đầu 2,4 s | Mặc định cloud rẻ, local là tùy chọn. Bỏ "Gemini 1.5 Flash" (đã cũ) |

## 3. Những câu trong proposal nên sửa trước khi nộp hoặc trình bày

1. **Bài toán #9 ("A gọi B là anh thì bắt buộc B gọi A là anh và xưng em").**
   - Câu này đang viết nhầm.
   - Quan trọng hơn, nó **mâu thuẫn quy tắc sản phẩm**: xưng hô có hướng, không tự suy ra B→A.
   - Ngoài đời có nhiều cặp lệch: thầy–trò, mày–tao một chiều, đang cãi nhau.
   - Đề xuất: biến thành **kiểm tra mềm**. Phát hiện cặp mâu thuẫn và hỏi người đọc, không ép model.
2. **"zyddnys / BallonsTranslator dùng GPT-4o Vision, đắt, trễ 3–8 s" — không đúng.**
   - manga-image-translator dùng OCR + dịch chữ, có tùy chọn gửi kèm chữ của vài trang trước (`context_size`).
   - Hướng "model đọc ảnh" giờ rẻ và nhanh: ~$0,0005 mỗi lần gọi cho một trang đơn, bóng đầu 2,4 s.
3. **"Hơn 70% câu lược chủ ngữ"**: cần nguồn trích dẫn, không thì viết mềm lại.
4. **Chỉ số:**
   - **ΔBLEU ≥ +3,5** với một bản dịch tham chiếu rất không ổn định cho thoại manga. Thay bằng **chấm mù A/B có/không bộ nhớ** (đã có công cụ `/judge`), giữ chrF làm chỉ số phụ.
   - **t_LLM ≤ 1,2 s** không thực tế với dịch cả trang. Dùng "bóng đầu ≤ 3 s p50" (đã đo 2,4 s).
   - **PCA ≥ 85%** nên giữ, nhưng cần làm nhãn: ~200 câu có cặp xưng hô chuẩn.
5. **Kho mã nguồn:** proposal ghi `oocsng/realtime-manga-translator` (Python), còn code đang chạy là `FanAnimeVN/live-translation` (TypeScript). Nhóm chọn một repo chính và cập nhật mục 7 của proposal.

## 4. Tại sao vẫn đáng làm khi đã có manga-image-translator (10,5k sao)?

| | manga-image-translator | Live translation |
|---|---|---|
| Người dùng | Người làm bản dịch: tải ảnh lên, chạy Python/GPU/Docker, nhận ảnh kết quả | **Người đọc**: dịch ngay trên trang đang đọc, không cài nặng; điện thoại dùng web reader |
| Ngữ cảnh | Từng trang; tùy chọn kèm chữ vài trang trước | **Bộ nhớ riêng cho từng bộ**: ai gọi ai thế nào (A→B) kèm bằng chứng, tóm tắt chương, nhắc tình tiết cũ **không spoil**, người đọc sửa và khóa |
| Tiếng Việt | Một ngôn ngữ đích trong nhiều ngôn ngữ, không có luật xưng hô | Thiết kế cho Nhật→Việt: danh xưng (-san, senpai…), không chồng "chị nee-chan", xưng hô có hướng |
| Đọc liên tục | Xử lý theo lô | Bóng hiện dần, dịch trước trang kế, cache, mở lại tức thì |

**Cách nói:**
- "Chúng em học từ họ." Kỹ thuật vẽ lại và mask đã ghi nguồn trong [compare-manga-image-translator.md](reference/compare-manga-image-translator.md).
- "Chúng em giải phần họ không giải: **xưng hô tiếng Việt xuyên suốt cả bộ truyện** và **trải nghiệm đọc tại chỗ**."
- Số đo để chứng minh: 96,4% chữ được dịch, 0 chữ đè lên chữ, ~18 đ/trang, bóng đầu 2,4 s.

## 5. Demo "nhẹ" tuần sau: chọn cái làm tốt nhất

**Nên chiếu** (`apps/demo` chạy trên máy, ảnh chỉ ở máy, slide ghi "courtesy of [tác giả]" theo điều khoản Manga109):
1. Mở 2–3 trang đã dịch sẵn (mở lại từ cache, tức thì), rồi **dịch trực tiếp 1 trang** để thấy bóng hiện dần sau ~2–3 s.
2. Giữ phím Space để xem bản gốc, thả ra để xem bản dịch. Nên chọn trang có:
   - bóng nhỏ trên nền tram (đã sửa hôm nay);
   - tiếng hét viết hoa xếp dọc;
   - chữ trên tranh được vẽ lại nền.
3. Mở bảng bộ nhớ: một cặp xưng hô A→B có bằng chứng (trang/vùng), bấm **Đúng/Đổi**.
4. Một con số chi phí: ~18 đ/trang (Haiku, sau tối ưu), gói 39k/tháng ≈ 50 chương, gói 99k cho người đọc nhiều.

**Không nên chiếu:** extension (chưa có), trang có thẻ/biểu mẫu nghiêng, các trang trong danh sách lỗi còn lại. Lỗi còn lại:
- tiếng hét ARMS-005: phần cuối của chữ mở ra vùng nét tốc độ nên còn sót chữ;
- vài ô vẽ lại còn vệt xám;
- người nói "unknown" nhiều.

**Dự phòng:** quay sẵn video 60 s phòng khi mạng lỗi.

## 6. Kịch bản 5 phút

| Thời gian | Nội dung | Ý chính |
|---|---|---|
| 0:00–0:40 | Vấn đề | Người Việt đọc raw: chờ bản dịch lậu lâu; Google Lens phá bố cục và xưng "tôi–bạn" máy móc; mất ngữ cảnh ai nói với ai |
| 0:40–1:20 | Vì sao khó | Ví dụ tự soạn (không lấy thoại trong truyện): cùng một câu tiếng Nhật không có chủ ngữ, ba bản dịch xưng hô khác nhau tùy quan hệ. Chữ Việt dài gấp 2–3 lần và phải vừa bóng. Không được spoil |
| 1:20–2:30 | Demo | Mục 5 |
| 2:30–3:20 | Giải pháp theo 4 trụ cột tư duy tính toán | **Phân rã:** tìm chữ → đọc + dịch có bộ nhớ → xóa/vẽ lại → dàn chữ. **Trừu tượng:** đồ thị xưng hô có hướng + mốc đọc. **Nhận dạng mẫu:** yakuwarigo, danh xưng, khung hồi tưởng, bóng thoại nhỏ. **Thuật toán:** thứ tự đọc, loang tô lòng bóng, dàn chữ quy hoạch động |
| 3:20–4:10 | Khác manga-image-translator | Bảng ở mục 4 rút còn 3 dòng |
| 4:10–5:00 | Đo đạc + kế hoạch | Số đo hiện có; sẽ đo PCA và A/B có/không bộ nhớ; mốc 2–3 tuần; phân công |

**Câu hỏi nên chuẩn bị trả lời:**
- Bản quyền: chỉ dịch thứ người đọc đã mở được; không lưu ảnh; không chia sẻ bản dịch giữa người dùng.
- Chi phí: [COST-PRICING.md](COST-PRICING.md).
- Đo đại từ thế nào?
- Sao không fine-tune? Dữ liệu song ngữ Nhật–Việt có nhãn xưng hô gần như không có; bộ nhớ + prompt rẻ và sửa được ngay.
- Khác Google Lens chỗ nào?

## 7. Nên làm tới đâu trong 2–3 tuần tới (MVP trước giảng viên)

**MVP không cần extension** (nhóm chốt 20/10). Extension để sau MVP. Thay vào đó, MVP là **trang đọc truyện chạy trên máy** (`apps/demo`): người đọc mở chương của chính mình và đọc liền mạch.

**Phải có**
1. **Reader mở chương của người đọc.**
   - Kéo thả thư mục ảnh hoặc file ZIP; đọc cuộn dọc hoặc từng trang.
   - Dịch trước 2–3 trang kế; mở lại từ cache; giữ Space để xem bản gốc.
   - Ảnh chỉ nằm trong RAM. Bộ nhớ truyện lưu theo từng bộ.
   - Hiện demo chỉ mở được 60 trang của bộ dữ liệu, nên đây là khoảng trống lớn nhất khi bỏ extension.
2. **Gán người nói và xưng hô** — phần nghiên cứu của đồ án (mục 9), theo bậc:
   - prompt v5 (đã đo);
   - ngoại hình nhân vật trong bộ nhớ, để nối nhãn "(cô gái tóc ngắn)" với tên ở các trang sau;
   - hướng đuôi bóng tính từ hình học, gửi kèm danh sách vùng;
   - kiểm tra nhất quán cặp xưng hô trong trang, chỉ hỏi lại các bóng mâu thuẫn.
3. **Đo theo proposal**, mỗi số ghi rõ điều kiện:
   - **PCA** trên ~200 câu nhóm gán nhãn: người nói → người nghe, các cặp xưng hô chấp nhận được (một câu có thể đúng với nhiều cặp);
   - A/B có/không bộ nhớ (chấm mù);
   - độ đúng thứ tự đọc từ `reading_order`;
   - CR (token gửi đi so với toàn bộ lịch sử);
   - độ trễ p50/p95.
4. **Bảng bộ nhớ đầy đủ:** sửa và khóa, lịch sử sửa, xuất/nhập JSON.
5. **Định dạng trả về gọn** (−25–30% chi phí, [COST-PRICING.md §3](COST-PRICING.md)).

**Nên có:**
- trần ký tự L_max gửi cho model;
- mask chữ học máy cho chữ rỗng (ARMS-005), nếu giấy phép cho phép;
- giảm vệt xám của MI-GAN.

**Để sau MVP:** extension, tài khoản + thanh toán thật, web reader cho điện thoại, cache dùng chung, LaMa trên GPU cloud.

| Tuần | Việc | Xong khi |
|---|---|---|
| 1 | Người nói bậc 2–3; đo thứ tự đọc; công cụ gán nhãn người nói/xưng hô cho nhóm; định dạng trả về gọn | Có số trước/sau cho tỉ lệ "unknown" và đại từ; nhóm bắt đầu gán nhãn |
| 2 | Reader mở thư mục/ZIP + dịch trước + cache; bảng bộ nhớ đầy đủ | Đọc trọn một chương raw ngoài bộ dữ liệu, không lỗi, mở lại tức thì |
| 3 | PCA thật trên nhãn của nhóm; A/B có/không bộ nhớ; CR; độ trễ; sửa ca khó nếu còn thời gian; video + slide | Bảng số cuối cùng cho báo cáo, video 60 s dự phòng |

## 8. Dữ liệu của nhóm (`realtime-manga-translator-main/dataset`) đã dùng tới đâu

**Không có gì được "huấn luyện".**
- Pipeline dùng model có sẵn và chỉ chỉnh prompt cùng luật xử lý ảnh.
- Dữ liệu chỉ dùng để **đánh giá** và **chỉnh ngưỡng**.
- Không nên huấn luyện trên bộ này: 50 trang là quá ít, ảnh Manga109 chỉ được dùng cho học thuật, và các ngưỡng đã chỉnh trên chính 50 trang này cũng cần một bộ giữ riêng để kiểm tra lại.

| Phần dữ liệu | Đã dùng? | Dùng vào đâu / nên dùng thế nào |
|---|---|---|
| 50 ảnh (5 bộ × 10 trang đôi) | ✅ toàn bộ | Mọi lượt dịch, QA dàn chữ, đo độ trễ |
| `bbox` + `ja_ocr_truth` (865 bóng) | ✅ toàn bộ | Độ phủ chữ (96,4%), CER đọc chữ, chỉnh ngưỡng detector |
| `vi_gold_trans` (865 bản dịch chuẩn) | ⚠️ một phần | Đối chứng ẩn khi chấm mù (25 trang, 419 bóng), chrF. **Hôm nay** thêm đo đại từ trên cả 865 bóng (mục 9) |
| `reading_order` | ⚠️ chỉ để sắp xếp khi chấm | **Chưa đo độ đúng thứ tự đọc** (chỉ số RTL của proposal). Đo được ngay, không tốn API |
| XML Manga109: 575 khung tranh, 327 mặt + 439 thân nhân vật kèm mã nhân vật, chữ của **cả cuốn** | ❌ chưa dùng | (1) Khung tranh để đo thứ tự đọc theo khung. (2) Mặt/thân kèm mã nhân vật làm nền cho bài toán **gán người nói**. Cần thêm nhãn "câu nào của ai", ví dụ bộ Manga109Dialog, chỉ dùng cho học thuật. (3) Chữ của các trang trước đó làm "phần đã đọc" để thử bộ nhớ trên mạch truyện dài hơn |
| 6 file PDF (persona, đặc tả đầu vào, benchmark & UX, tài liệu tham khảo) | ❌ chưa đọc kỹ | Nên đối chiếu với các chỉ số của proposal |

## 9. Prompt nhận diện người nói: so với manga-image-translator

**manga-image-translator không có bước nhận diện người nói.**
- Prompt dịch mặc định chỉ yêu cầu chọn đại từ theo ngữ cảnh, không thêm đại từ không có trong câu gốc, và giữ giọng nhân vật nhất quán ([config_gpt.py](https://github.com/zyddnys/manga-image-translator/blob/main/manga_translator/translators/config_gpt.py)).
- Bản "2 bước" gửi ảnh trang chỉ để sửa OCR và thứ tự đọc ([chatgpt_2stage.py](https://github.com/zyddnys/manga-image-translator/blob/main/manga_translator/translators/chatgpt_2stage.py)).

**Prompt của mình đã chặt hơn ở điểm này:**
- Model phải ghi người nói → người nghe cho mọi bóng, chọn xưng hô theo cặp A→B trong bộ nhớ.
- Model trả về các cặp xưng hô kèm bằng chứng.
- Model bị cấm đoán bừa giới tính và quan hệ. Từ v5, những gì tranh vẽ rõ (tuổi, giới tính, cách gọi nhau) được tính là bằng chứng.

**Nhưng kết quả còn yếu (prompt v4):**
- 58% (Haiku) đến 77% (DeepSeek) câu thoại không rõ người nói.
- So với bản dịch chuẩn của nhóm (`tools/eval/src/pronouns.ts`, 267 bóng mà bản chuẩn có đại từ):

| Lượt dịch (60 trang) | Cùng bộ đại từ | Bỏ đại từ mà bản chuẩn có | Khác bộ | Dùng "bạn" khi bản chuẩn không dùng |
|---|---|---|---|---|
| DeepSeek (ds-ctd2) | 25,8% | 25,8% | 46,8% | 0% |
| Haiku, bộ nhớ K=0 | 28,1% | 27,7% | 42,3% | 0% |
| Haiku, K=20 | 28,5% | 28,1% | 41,6% | 0% |
| Haiku, K=80 | 23,6% | 28,5% | 46,1% | 0% |

**Đọc số này thế nào:**
- Đây là số gần đúng. "ta", "mình", "con" cũng là từ thường, và bản chuẩn chỉ là lựa chọn của một nhóm.
- Lỗi thật lớn nhất là chọn cặp ngang hàng hoặc trung tính ("tớ–cậu", "tôi") thay vì cặp theo tuổi ("anh–em"), hoặc bỏ hẳn đại từ. Chi tiết ở mục 9.1.
- **Thêm ngữ cảnh (K=80) không làm tốt hơn.** Điều này củng cố luận điểm của proposal: nhồi thêm câu cũ không giải được xưng hô, cần **đồ thị quan hệ + gán người nói**.
- Không có lỗi "tôi–bạn" máy móc.

### 9.1 Lệch do đâu (soi tay các bóng lệch của lượt Haiku K=20, không tốn API)

- **Khoảng 1/3 số bóng lệch không phải lỗi thật.** Có ba loại:
  - bản chuẩn lệch dòng với câu tiếng Nhật;
  - sản phẩm cố ý giữ "-san" trong khi bản chuẩn dịch thành "chị/anh";
  - hai lựa chọn đều ổn, ví dụ "ta" và "tao" khi quát kẻ thù.
- **Lỗi thật lớn nhất: chọn cặp ngang hàng hoặc trung tính thay vì cặp theo tuổi.**
  - Giữa một nam lớn hơn và một nữ nhỏ hơn, bản chuẩn dùng "anh–em", còn model dùng "tôi–cậu", "tớ–cậu" hoặc bỏ hẳn đại từ.
  - Độc thoại nội tâm: model dùng "tôi" thay vì "mình".
- **Nguyên nhân.** Prompt v4 dặn "chưa rõ quan hệ thì dùng dạng trung tính hoặc lược", mà 58% câu không rõ người nói, nên model né.
  - Khi biết người nói, tỉ lệ khớp cao hơn: Haiku 33,9% so với 25,2%; DeepSeek 46,2% so với 19,7%.

### 9.2 Đã thử ngày 20/10 (Haiku 5.5, bộ nhớ K=20, 60 trang, mỗi cấu hình chạy 1 lượt, ~$0,11 mỗi lượt)

- **v5:**
  - Dạy dấu hiệu hình ảnh: đuôi bóng; bóng suy nghĩ; tên gọi trong câu là người nghe; yakuwarigo.
  - Thêm bảng cặp xưng hô thường dùng: lớn–nhỏ → anh/chị–em; bạn bè → tớ–cậu; độc thoại → "mình".
  - Thêm **nhãn mô tả** cho người chưa có tên, ví dụ "(girl, short hair)". Bộ nhớ không bao giờ lưu nhãn thành nhân vật hay luật xưng hô.
- **v5b:** v5, cộng thêm hai thứ:
  - Model ghi **ngoại hình** của nhân vật có tên vào thẻ nhân vật, để nhận ra họ ở trang sau.
  - Gợi ý quan hệ tuổi từ cách gọi lệch nhau, ví dụ một người gọi 〜さん, người kia gọi 〜ちゃん.

| Lượt | Người nói không rõ | Người nghe không rõ | Cùng bộ đại từ (267 bóng) | Bỏ đại từ | Bóng "anh/chị/em" dùng đúng từ (67 bóng) | chrF | $/60 trang |
|---|---|---|---|---|---|---|---|
| v4 (trước) | 58% | 80% | 28,5% | 28,1% | 9% | 38,15 | $0,106 |
| v5 | **6%** | 63% | 28,1% | 21,7% | 10% | 37,67 | $0,106 |
| v5b | **11%** | 66% | **30,0%** | 20,6% | **15%** | **39,20** | $0,107 |

**Đọc kết quả:**
- **Giải được "không rõ người nói":** 58% xuống còn 6–11%, chi phí không đổi.
- **Đại từ chỉ nhích nhẹ**, nằm trong mức dao động giữa các lượt chạy. Các lượt K=0…80 trước đây dao động 23,6–28,5% và chrF dao động khoảng ±1.
- Model vẫn thích "tớ–cậu" trong 46% số bóng mà bản chuẩn dùng anh/chị–em.
- **Phát hiện quan trọng — bộ nhớ tự động có thể khóa nhầm.**
  - Ở một bộ, model đoán sai giới tính một nhân vật ngay từ trang đầu. Từ đó bộ nhớ có luật "gọi là chị…", và các trang sau đều theo luật sai này.
  - Đã sửa: giới tính đoán từ tranh chỉ được ghi khi **hai trang khác nhau** cùng kết luận. Đã có test, chưa đo lại bằng API.
  - Ngoại hình chứa nhãn bị loại.
- **Bóng đầu chậm hơn trong lượt đo** (p50 16–18 s so với 10 s). Đây là điều kiện khác chứ không phải do prompt: token ra chỉ +4%. Hai nguyên nhân:
  - bộ tìm chữ thứ hai đang bật khi máy dev có GPU (+1,5 s);
  - mạng hoặc nhà cung cấp lúc đo.
  - Cần đo A/B cùng lúc trước khi kết luận về tốc độ.

### 9.3 Tối ưu tiếp phần người nói và xưng hô (theo thứ tự đáng làm)

1. **Thẻ xác nhận nhân vật một chạm** (rẻ nhất, chắc nhất).
   - Sau vài trang đầu của một bộ, hiện thẻ (ví dụ tự đặt): "Kenta: nam/nữ? Lớn hơn hay nhỏ hơn Yui? Cặp xưng hô: anh–em / tớ–cậu / …".
   - Người đọc chạm một lần là khóa cho cả bộ (khóa của người đọc luôn thắng).
   - Lỗi lớn nhất hiện nay là đoán sai quan hệ và tuổi; vài chạm sửa được cả trăm trang. Luồng Đúng/Đổi/Để sau đã có sẵn.
2. **Luật xưng hô tự động cần ≥ 2 trang đồng ý** mới được ép lên các trang sau, giống cách vừa làm với giới tính. Luật mới thấy một lần thì chỉ là gợi ý.
3. **Hướng đuôi bóng tính từ hình học** (miễn phí): gửi kèm danh sách vùng câu "đuôi bóng r5 chỉ về (x,y)". Model đọc ảnh vốn kém ở các chi tiết không gian nhỏ.
4. **Thí nghiệm "trần" bằng XML Manga109** (mặt và thân nhân vật có mã):
   - Đưa người nói đúng vào prompt, đo xem đại từ tăng bao nhiêu.
   - Nếu tăng nhiều → đáng đầu tư bộ nhận mặt và gán người nói.
   - Nếu không → nút thắt là quan hệ và tuổi, nên đi theo hướng 1.
5. **Đo đúng thay vì đo gần đúng:** nhóm gán nhãn ~200 câu (người nói → người nghe, *các* cặp xưng hô chấp nhận được). Chỉ số hiện tại chỉ so với một lựa chọn của một nhóm nên nhiễu.

### 9.4 Ý tưởng "nhớ mặt nhân vật" và thẻ xác nhận của người đọc (21/10)

**Ý tưởng của nhóm:** vì đã gửi ảnh trang cho model, cho model "nhớ" mặt từng nhân vật rồi gán tên, giới tính, vai trò, quan hệ; tích lũy độ tin cậy qua nhiều trang và chốt khi đủ chắc.

**Chi phí không đáng sợ nếu làm gọn** (giá Claude: ảnh tốn khoảng ⌈rộng/28⌉ × ⌈cao/28⌉ token):

| Cách làm | Token thêm mỗi trang | Ghi chú |
|---|---|---|
| Ngây thơ: gửi lại cả trang cũ, hoặc ảnh mặt 512 px cho 10 nhân vật | ~3.600 (+45%) | Đắt, chậm |
| **Gọn (đã cài):** tối đa 6 mặt ~128 px (đo được 91×128 px ≈ 20 token/mặt), chỉ cho nhân vật đang xuất hiện | ~150 (+2%) | Đo được: 8.265 → 8.410 token/trang, $0,107/60 trang như cũ |
| Gemini (mỗi ảnh tối thiểu ~258 token) | ~1.500 (+19%) | Nên ghép mọi mặt vào **một ảnh danh bạ** |

**Quy tắc riêng tư vẫn giữ.**
- Bộ nhớ chỉ lưu **tọa độ khung mặt** (trang + hộp), không lưu ảnh.
- Lúc cần mới cắt lại từ trang mà người đọc vẫn đang có.

**Đo được (Haiku, K=20, 60 trang, mỗi cấu hình chạy 1 lượt):**

| Lượt | Thêm gì | Câu gắn được tên | Câu chỉ có nhãn | Cùng bộ đại từ | Bóng anh/chị/em đúng từ | chrF |
|---|---|---|---|---|---|---|
| v5b | ngoại hình (chữ) | 26% | 63% | 30,0% | 15% | 39,20 |
| v5c | + ảnh mặt tham chiếu, giới tính cần 2 trang, nhãn độ tin cậy | 26% | 67% | 28,5% | **27%** | 37,94 |
| v5d | + model tự nối nhãn → tên (áp dụng ngay) | **41%** | 53% | 29,2% | **3%** | 37,72 |

**Đọc kết quả:**
- **Ảnh mặt không giúp gắn tên** (26% → 26%). Có lần model khoanh nhầm mặt: thẻ của một nhân vật nam ghi ngoại hình "cô gái tóc ngắn". Nhận diện mặt manga bằng model đọc ảnh chưa đáng tin; để model tự chốt "100%" sẽ khóa nhầm.
- **Model đã tự giữ danh tính khá tốt bằng nhãn chữ:** cùng một người là "(boy, curly hair)" suốt 10 trang. Thứ thiếu là **nối nhãn đó với tên** và với quan hệ. Cách này miễn phí, không cần ảnh.
- Nhãn đôi khi gộp hai người làm một. Vì vậy câu trả lời chắc chắn vẫn phải đến từ người đọc.
- Bóng anh/chị/em đúng từ tăng 15% → 27% (67 bóng, chênh 8 bóng). Có thể nhờ giới tính cần 2 trang và nhãn độ tin cậy, chưa tách riêng được từng thay đổi.
- **Để model tự nối nhãn với tên (v5d):**
  - Câu gắn được tên tăng 26% → 41%.
  - Nhưng model nối sai vài chỗ, ví dụ gắn nhãn "cô gái tóc ngắn" cho một con chuột hamster. Bóng anh/chị/em đúng từ rơi từ 27% xuống 3%.
  - **Đã đổi:** liên kết do model đặt chỉ là *gợi ý*, hiện thành "AI đoán" trên thẻ "là ai?". Chỉ khi người đọc chạm thì các câu cũ mới được đổi sang tên.
  - Bản hiện tại giống v5c về những gì gửi cho model.
- Mỗi cấu hình chỉ chạy 1 lượt trên 60 trang. Chênh lệch vài điểm phần trăm là trong mức dao động. Riêng mức rơi 27% → 3% ở v5d (18 → 2 bóng) đủ lớn để không bật tính năng đó.

**Cách làm tốt hơn (đã cài, chi phí API = 0):**
1. **Độ tin cậy cho từng dữ kiện** (luật xưng hô, giới tính):
   - mới thấy 1 trang = "AI đoán" (chỉ là gợi ý);
   - ≥ 2 trang đồng ý, không mâu thuẫn = "khá chắc", dùng mà không hỏi;
   - có trang mâu thuẫn = "mơ hồ";
   - người đọc chốt = khóa.
   - **Model không bao giờ tự lên mức khóa.** Model có thể sai một cách nhất quán, như vụ đoán sai giới tính.
2. **Thẻ một chạm** (`core/cast.ts`, tab Bộ nhớ của demo), tối đa 2 thẻ mỗi lần, chỉ hỏi những gì đáng hỏi:
   - "Nhân vật AI đang gọi là '(cậu bé đeo kính)' là ai?" → chọn tên đã có hoặc nhập tên. Một chạm đổi toàn bộ câu cũ dưới nhãn đó sang tên.
   - "A là nam hay nữ?"
   - "A và B xưng hô thế nào?" → các cặp anh–em, chị–em, tớ–cậu, tao–mày, con–bố/mẹ. Mỗi cặp ghi rõ cả hai chiều, nên đây là người đọc chọn, không phải tự suy chiều ngược.
   - Thẻ hỏi được cả cho hai nhãn chưa có tên.
   - Mỗi thẻ có nút "Không rõ" (không hỏi lại) và "Để sau" (hỏi lại sau 10 trang).
3. **Model gợi ý nối nhãn khi tên xuất hiện:** ghi `was: "(boy, curly hair)"` trong ghi chú tên. Gợi ý này chỉ hiện làm "AI đoán" trên thẻ (nút tên được đoán đứng đầu); người đọc chạm thì mới áp dụng. Lý do xem v5d ở trên.
4. **Ảnh mặt tham chiếu** giữ làm tùy chọn thử nghiệm (`--refs`), mặc định tắt ở server vì chưa thấy lợi.

**Học từ câu trả lời của người đọc:**
- **Ghi nhận:** mỗi câu trả lời được ghi vào `.private/labels/cast-answers.jsonl`. Nội dung chỉ là chữ: câu hỏi, AI đã đoán gì, người đọc chọn gì, và vài câu thoại giữa hai người.
- **Bốn cách dùng:**
  - Khóa ngay cho bộ truyện đó.
  - Đo AI đoán đúng bao nhiêu với từng loại dữ kiện, để chỉnh lúc nào nên hỏi.
  - Làm nhãn chuẩn cho chỉ số PCA của proposal.
  - Khi người dùng đồng ý chia sẻ (ẩn danh, chỉ chữ): gộp thành bảng mặc định. Ví dụ tự đặt: "một người gọi 〜さん, người kia gọi tên trống → đa số chọn anh–em". Bảng này đưa vào prompt; về sau có thể huấn luyện một bộ phân loại nhỏ chạy trên máy, không tốn API.
- **Ảnh không bao giờ rời máy.** Bộ nhận diện nhân vật học sâu kiểu Magi v2 (Oxford) chỉ cấp phép cho nghiên cứu, nên chỉ dùng để đo, không dùng cho gói trả phí.

**Bước tiếp để đo đúng giá trị của thẻ:**
- Nhóm mở demo và trả lời thẻ cho 5 bộ trong bộ dữ liệu. Mất khoảng 30 phút, và câu trả lời tự thành nhãn.
- Sau đó chạy A/B: dựng lại bộ nhớ đến trang N từ kết quả đã có (không tốn API), áp câu trả lời, rồi dịch các trang sau N. Khoảng $0,06.
- Không nên để AI tự "đóng vai người đọc": thử ở trên cho thấy nhãn của model đôi khi gộp hai người, nên đáp án phải do người nhìn tranh đưa ra.
