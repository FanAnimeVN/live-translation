# Chi phí đọc một bộ truyện, cách giảm, và các gói cho người Việt

Cập nhật 20/10/2026. Số đo lấy từ sổ chi phí `.private/ledger.jsonl` (giá OpenRouter thật, `usage.cost`).
Tỷ giá dùng để quy đổi: **1 USD ≈ 26.300 đ** (giữa năm 2026). Phần ghi "ước tính" là chưa đo.

## 1. Một trang tốn bao nhiêu (đo thật)

Ảnh Manga109 trong bộ đánh giá là **trang đôi** (hai trang truyện trên một ảnh, 1654×1170). Một trang đơn tốn khoảng 0,6 lần trang đôi:
phần chỉ dẫn cố định của prompt vẫn phải gửi, nhưng ảnh và số bóng thoại chỉ còn một nửa.

| Khoản | DeepSeek V4.1 Flash 1017 (mặc định nhanh) | Claude Haiku 5.5 |
|---|---|---|
| Đọc + dịch, mỗi ảnh trang đôi | **$0,00084** (334 lần gọi; vào 5.826 token, ra 1.121 token) | $0,00129 (475 lần gọi) |
| Đọc + dịch, mỗi trang đơn (×0,6) | ~$0,0005 | ~$0,00077 |
| Cập nhật bộ nhớ truyện (DeepSeek, mỗi ~24 câu thoại ≈ 2–3 trang) | ~$0,0002/trang | ~$0,0002/trang |
| Tóm tắt chương | ~$0,00015/chương, không đáng kể | như trên |
| **Tổng mỗi trang đơn** | **~$0,0007 ≈ 18 đ** (trang nhiều chữ tới ~$0,0015) | **~$0,001 ≈ 26 đ** |

Để tính ngân sách, mình dùng **21 đ/trang** cho DeepSeek và **29 đ/trang** cho Haiku. Hai mức này đã cộng thêm phần dự phòng cho trang nhiều chữ.
Chưa tính CPU máy chủ: tìm vùng ~0,3 s/trang. Phần vẽ lại cho điện thoại thì phải đo trên máy chủ thật.

**Tiền nằm ở đâu (DeepSeek):** giá $0,08/1 triệu token vào và $0,50/1 triệu token ra.
- **Token ra chiếm ~65% chi phí:** 1.121 × $0,5 ≈ $0,00056 trên $0,00084.
- Trong token ra, **khoảng 60% là khung JSON**, phần còn lại mới là nội dung. Mỗi bóng mất ~34 token cho `"id"`, `"role"`, `"speaker":"unknown"`, `"to"`, `"style":[]`. Nội dung thật (chữ Nhật + bản Việt) chỉ ~21 token/bóng. Trung bình có 18,5 bóng mỗi ảnh, và 82% bóng có người nói "unknown".

## 2. Một bộ truyện dài bao nhiêu trang

Chương truyện tuần (Jump) dài khoảng 16–22 trang, truyện tháng 36–50 trang ([ANN](https://www.animenewsnetwork.com/bbs/phpBB2/viewtopic.php?p=773631), [Japan Truly](https://shop.japantruly.com/blogs/anime/what-are-manga-chapters)).
Một tập tankōbon dày ~190 trang. Ước tính "200–300 chương × 100 trang" là **cao gấp ~5 lần** với manga Nhật:
200–300 chương truyện tuần chỉ khoảng **3.800–5.700 trang**. Webtoon dạng cuộn dài mới có chương rất dài, và đó không phải đối tượng hiện tại.

| Bộ | Tập | Chương | Trang ≈ (tập × 190) | DeepSeek hôm nay (21 đ/tr) | Sau tối ưu (12 đ/tr, mục 3) | Haiku (29 đ/tr) |
|---|---|---|---|---|---|---|
| Death Note | 12 | 108 | 2.300 | 48k | 28k | 67k |
| Thanh gươm diệt quỷ | 23 | 205 | 4.400 | 92k | 53k | 128k |
| Chú thuật hồi chiến | 30 | 271 | 5.700 | 120k | 68k | 165k |
| Đại chiến Titan (truyện tháng) | 34 | 139 | 6.500 | 137k | 78k | 189k |
| Naruto | 72 | 700 | 13.700 | 288k | 164k | 397k |
| One Piece (đang ra) | 114 | 1.175+ | 21.700 | 456k | 260k | 629k |

Số tập và số chương của One Piece tính đến 3/2026 ([Wikipedia](https://en.wikipedia.org/wiki/List_of_One_Piece_manga_volumes)).

**Kết luận:**
- Một bộ cỡ trung bình (200–300 chương) tốn **80–120k tiền model** hôm nay, và 46–68k sau tối ưu.
- Mức 500k–1 triệu chỉ xảy ra với bộ siêu dài như One Piece, và đó vẫn là giá vốn chưa có lãi.
- Người đọc không đọc hết một bộ trong một tháng. Chi phí hằng tháng mới là thứ quyết định gói (mục 4).

## 3. Cách giảm chi phí và tăng tốc mà không giảm chất lượng

| # | Cách làm | Tiết kiệm ước tính | Ảnh hưởng chất lượng | Trạng thái |
|---|---|---|---|---|
| 1 | **Định dạng trả về gọn**: một dòng mỗi bóng, ví dụ `r1|d|Hina>Sota|…ja…|…vi…`. Bỏ tên khóa JSON, bỏ `unknown` và `style` rỗng | Token ra −40% → **−25–30% tiền dịch**; cả trang xong nhanh hơn ~30% vì model sinh ít token hơn | Nội dung giữ nguyên. Cần một lượt A/B 60 trang + chấm mù để chắc model không đọc sai | Chưa làm, nên làm trước tiên |
| 2 | **Prefix cố định dài hơn để cache**: chỉ dẫn + bộ nhớ ổn định đặt trước, ảnh đặt sau. DeepSeek đọc lại cache chỉ ~$0,003/1 triệu token ([LLM Reference](https://www.llmreference.com/model/deepseek-v4.1-flash/openrouter)) | −5–10% | Không | Hiện mới cache được ~1,4k/5,8k token |
| 3 | **Ảnh gửi đi nhỏ vừa đủ** (thử cạnh dài 1280 thay vì 1654, giữ crop phóng to cho chữ nhỏ) | −10–20% token vào | Có thể làm đọc kém chữ nhỏ, **phải đo CER trước khi bật** | Chưa làm |
| 4 | Không gọi model cho trang không có chữ (bìa, trang tranh toàn khổ) | −3–5% | Không | Chưa làm |
| 5 | Chỉ trừ lượt khi người đọc mở tới trang. Trang dịch trước mà không đọc thì mình chịu (tối đa ~2 trang mỗi lần đọc) | Không tiết kiệm, nhưng công bằng | Không | Chính sách |
| 6 | **Cache dùng chung giữa người dùng** cho chương phổ biến (người đầu tiên trả, người sau ~0 đ) | −90%+ với bộ hot | Không | **Mặc định tắt**: phân phối bản dịch tác phẩm có bản quyền ([CLOUD.md §7](CLOUD.md)). Chỉ bật với nguồn có phép |
| 7 | Local (Ollama trên GPU người dùng) và BYOK (key Gemini miễn phí của người dùng) | 0 đ phía mình | Local kém hơn cloud (bảng model local ở [DIRECTION.md](DIRECTION.md)) | Đã có lõi; cần trình hướng dẫn |

- **Cộng 1–4: khoảng −40–50%**, tức ~$0,00045 ≈ **12 đ/trang** với DeepSeek. Đây là ước tính, phải đo lại sau khi làm.
- **Model rẻ hơn nữa chưa dùng được.** Qwen3.7-Flash rẻ gấp ~3,6 lần nhưng từ chối 2–3/10 trang truyện bình thường vì bộ lọc nội dung. Nó cũng tóm tắt kém nhất ([DIRECTION.md](DIRECTION.md)).
- **Tốc độ:**
  - Bóng đầu tiên hiện sau ~2,4 s (DeepSeek, p50); phần lớn thời gian này là chờ model trả token đầu.
  - Trang đã dịch trước hiện ngay (0 s).
  - Cách 1 rút ngắn thời gian hoàn tất cả trang chứ không rút ngắn bóng đầu.

## 4. Người đọc tiêu bao nhiêu mỗi tháng

| Kiểu người đọc | Chương/tháng | Trang/tháng | Chi phí hôm nay | Sau tối ưu |
|---|---|---|---|---|
| Theo dõi ~8 bộ đang ra hằng tuần | 40 | ~760 | 16k | 9k |
| Cày đều ~5 chương/ngày | 150 | ~2.850 | 60k | 34k |
| Cày nặng 10+ chương/ngày | 300+ | 5.700+ | 120k+ | 68k+ |

## 5. Các extension khác làm thế nào

| Công cụ | Model | Gói | Cách giữ chi phí |
|---|---|---|---|
| Ichigo Reader | Miễn phí: GPT-4o mini (20 ảnh). $5,99: DeepSeek V3, Gemini Flash. $19,99: GPT-4o, Gemini Pro, Claude, Grok ([UPDF](https://updf.com/chatgpt/japanese-manga-translator/)) | Gói tháng chia theo **chất lượng model** | **Giới hạn theo giờ** (300 ảnh/giờ ở gói rẻ, 150/giờ ở gói cao) thay vì theo tháng: người đọc thật không chạm tới, nên có cảm giác "không giới hạn" |
| Torii | GPT, Gemini, Claude, DeepSeek; người dùng chọn ([moge.ai](https://moge.ai/tw/product/torii-image-translator)) | Gói credit từ $5,99, không hết hạn | **BYOK** (key OpenRouter/Gemini… của người dùng) và **model local** qua LM Studio miễn phí; gửi tóm tắt các trang trước làm ngữ cảnh |
| Sumi | không công bố | $69,99/năm (≈ $5,83/tháng), miễn phí 1 trang ([stork.ai](https://www.stork.ai/en/sumi-ai-manga-translator)) | **Gói năm** |
| "Manga Translator" (60–70k người dùng) | không công bố | miễn phí | Chưa rõ; số người dùng chỉ có từ trang tổng hợp ([chromeboard](https://chromeboard.com/extension/manga-translator-oooikipggipaohjibkmoiacmmlilgokn)) |

Chưa tìm thấy extension nào tên "Manga Scan" có 50k người dùng; có thể bạn đang nghĩ tới một trong các công cụ trên.

**Không ai có giá vốn ~0.** Họ dùng 4 cách:
1. Chia gói theo chất lượng model.
2. Giới hạn "hợp lý" theo giờ để trông như không giới hạn.
3. Đẩy chi phí sang người dùng (BYOK, local).
4. Bán gói năm để có tiền trước.

## 6. Gói đề xuất: giữ model tốt, tìm "điểm ngọt" theo thói quen đọc thật

### 6.1 Người đọc tiêu bao nhiêu (dữ liệu có được)

- **Tốc độ đọc:**
  - Ước tính phổ biến ~20 s/trang manga, tức ~3 trang/phút, ~180 trang/giờ ([MangaDex forum](https://forums.mangadex.org/threads/estimate-the-reading-time-for-each-manga.2326479/)).
  - Thời gian xem tỉ lệ với lượng chữ và khác nhau rất nhiều giữa người đọc ([Scientific Reports 2023](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10661992/)).
- **Tần suất ở Nhật:** người dùng LINE Manga và Piccoma mở app hơn 15 ngày/tháng ([VALUES](https://manamina.valuesccg.com/articles/2083)).
- **Việt Nam:**
  - Gen Z dành 5–7 giờ/ngày cho giải trí số, nhưng thích nội dung miễn phí. Trả tiền chủ yếu theo kiểu freemium ([Appota qua vietnam.vn](https://www.vietnam.vn/en/lua-tuoi-gen-z-dan-dau-tieu-dung-giai-tri-so)).
  - MangaToon bán gói "VIP tháng – VN" **$1,99 (~52k)** ([App Store](https://apps.apple.com/us/app/-/id1385287093)).
- **Hệ quả:**
  - Một người đọc **2 giờ/ngày ≈ 10.000 trang/tháng**.
  - Với Haiku sau tối ưu (~18 đ/trang), riêng tiền model cho người đó là **~150k/tháng**.
  - Mỗi giờ đọc tốn ~3k tiền model. Không gói 50–100k nào "không giới hạn thật" mà vẫn lãi nếu người đó đọc toàn bộ là raw.

### 6.2 Giá vốn mỗi trang khi giữ model tốt (Haiku 5.5 mặc định)

| | Hôm nay | Sau định dạng gọn + cache | + dịch trước theo lô (Batch API, −50% phần dịch) |
|---|---|---|---|
| Haiku 5.5 (mặc định, ít lỗi nặng nhất trong chấm mù) | ~26 đ | **~18 đ** | **~11 đ** |
| DeepSeek V4.1 Flash 1017 (nhanh nhất, chrF ngang Haiku) | ~19 đ | ~14 đ | — (OpenRouter không có batch) |
| Gemini 3.1 Flash-Lite (chrF cao nhất, đắt) | ~100 đ | ~70 đ | — |

- Batch API giảm 50% cho phần dịch không ai đang chờ, phù hợp với **"dịch sẵn các chương kế"** cho người cày.
- Batch cần tài khoản Anthropic trực tiếp; kết quả có thể mất tới 24 giờ, nên chỉ dùng cho chương xếp hàng trước, không dùng cho trang đang mở.

### 6.3 Mô phỏng (`tools/eval/src/pricing.ts`, không gọi API)

**Các giả định, phải thay bằng số đo beta:**
- Bốn kiểu người đọc trong số người có thể trả tiền:

  | Kiểu | Tỉ lệ | Thời gian đọc | Sẵn sàng trả (trung vị) | Phần dịch sẵn theo lô |
  |---|---|---|---|---|
  | Nhẹ | 40% | 15 phút × 12 ngày | 40k | 0% |
  | Đều | 35% | 40 phút × 22 ngày | 70k | 15% |
  | Nặng | 20% | 2 giờ × 28 ngày | 120k | 30% |
  | Cày | 5% | 3 giờ × 30 ngày | 160k | 35% |

- Mức sẵn sàng trả phân bố log-chuẩn quanh trung vị.
- Giá đã gồm VAT 10%; phí cổng ~3%; máy chủ 2k mỗi người; nạp thêm 25k/1.000 trang.
- Mỗi người chọn gói lợi nhất cho mình, hoặc ở lại gói miễn phí (BYOK/Local).
- Biến quan trọng nhất là **tỉ lệ raw**: bao nhiêu phần trang họ đọc thật sự cần dịch. Người đọc nhiều thường đọc bản Việt có sẵn cho truyện cũ, và chỉ cần dịch chương mới hoặc truyện chưa có bản Việt.

| Kịch bản | Bộ gói lãi nhất | Lãi / 1.000 người tiềm năng / tháng | Người đọc nặng + cày được phục vụ |
|---|---|---|---|
| 100% raw | 39k/1.000 trang + 99k/5.000 trang | 9,1 triệu | **5%** |
| 100% raw, buộc phục vụ ≥ 40% người đọc nặng | 39k/1.000 + 129k/20.000 | **lỗ 0,3 triệu** | 48% |
| 50% raw (nhiều khả năng hơn) | 39k/1.000 + 129k/5.000 | 16,4 triệu | 27% |
| **50% raw, phục vụ ≥ 60% người đọc nặng** | **39k/1.000 + 99k/8.000** | **12,7 triệu** | **67%** |
| Giá vốn còn 35% (tự chạy model mở, mục 7), phục vụ ≥ 60% | 39k/2.000 + 99k/20.000 | 18,0 triệu | 71% |

So sánh: bộ 49k/2.000 + 99k/8.000 (nhiều trang hơn cho gói rẻ) chỉ lãi 10,2 triệu ở kịch bản 50% raw. Giá cao hơn làm mất người đọc nhẹ, và thêm trang thì tăng giá vốn của người đọc đều.

**Đọc kết quả:**
- Muốn người đọc nhiều được đọc thoải mái thì phải chấp nhận lãi thấp hơn khoảng 30% so với mức tối đa. Khoản đó là chi phí để giữ đúng nhóm người dùng trung thành nhất.
- Khi giá vốn giảm (tối ưu, gói năm, tự chạy model), chính bộ gói đó quay lại mức lãi cao nhất.

### 6.4 Đề xuất chốt (điểm ngọt)

| Gói | Giá | Bao gồm | Vì sao |
|---|---|---|---|
| **Miễn phí** | 0 đ | BYOK + Local không giới hạn; cloud 100 trang dùng thử + 30 trang/tháng | Giữ người chưa trả tiền mà gần như không tốn |
| **Đọc** | **39k/tháng** (329k/năm) | **1.000 trang** (~50 chương: theo dõi ~10–12 bộ đang ra hằng tuần), **Haiku**, dịch trước, bộ nhớ truyện đồng bộ | Điểm lãi cao nhất ở mọi kịch bản; dưới VIP MangaToon (~52k) và Netflix Mobile (74k) |
| **Cày** | **99k/tháng** (829k/năm) | **8.000 trang** (~420 chương ≈ 1,5 giờ/ngày toàn raw, ~3 giờ/ngày nếu nửa raw), Haiku; **"dịch sẵn 10 chương kế"** qua đêm; quá 8.000 trang vẫn đọc tiếp bằng DeepSeek, không cắt ngang | Người đọc nhiều có một gói dưới 100k; dịch theo lô giữ giá vốn ~11–14 đ/trang. Người cày nặng nhất vẫn lỗ nhẹ, được gói "Đọc" bù |
| Nạp thêm | 25k / 1.000 trang | cho tháng đọc nhiều hơn thường | Không phải nâng gói |
| Chất lượng cao | bật riêng từng bộ | Gemini Flash-Lite cho bộ người đọc chọn, trừ 4 trang mỗi trang | Đắt gấp ~5 lần, chỉ dùng khi người đọc muốn |

- **Chống lạm dụng mà người đọc thật không chạm tới:** ≤ 300 trang/giờ (gấp gần 2 lần tốc độ đọc), giống cách Ichigo giới hạn theo giờ.
- **Gói năm:** giảm ~30%, có tiền trước để chạy máy chủ; chỉ mở sau khi đã tối ưu xong giá vốn.

### 6.5 Đo gì trong bản beta để chốt (20–50 người, 1 tháng)

1. Phân bố trang/ngày và tỉ lệ raw thật, đặc biệt nhóm đọc nhiều như bạn của bạn.
2. Giá thử A/B: 39k/49k/59k cho gói "Đọc", 79k/99k/129k cho gói "Cày"; đo tỉ lệ chuyển đổi và tỉ lệ hủy.
3. Bao nhiêu trang dịch sẵn theo lô được đọc thật (để không trả tiền cho chương người ta bỏ).
4. Chạy lại `tools/eval/src/pricing.ts` với số đo thật, rồi chốt giá.

## 7. Đường tới chi phí "gần như 0 đ" (theo quy mô)

| Giai đoạn | Cách | Giá vốn/trang | Điều kiện |
|---|---|---|---|
| Bây giờ | DeepSeek + cách 1–4 (mục 3) | ~12 đ | Đo lại chất lượng sau khi đổi định dạng |
| Song song | BYOK (key Gemini miễn phí của người dùng) và Local | 0 đ phía mình | Local cần model đọc ảnh đủ tốt (đang đo) |
| Khi có vài nghìn người dùng | **Tự chạy model mở trên GPU thuê** (vLLM, gom nhiều trang một lượt) | ước tính ~3–5 đ nếu một GPU ~$0,5–1/giờ xử lý ~1 trang/giây | **Chưa có model mở nào đạt** chất lượng Nhật–Việt: Gemma 4 E2B bịa chữ; Qwen3-VL 8B chưa đo. Phải chấm mù trước |
| Tùy chính sách | Cache dùng chung cho chương phổ biến | ~0 đ với người đọc sau | Vấn đề phân phối bản dịch tác phẩm có bản quyền; mặc định tắt |

**Không khuyên:** fine-tune hoặc "chưng cất" một model nhỏ từ bản dịch của model thương mại. Ảnh Manga109 chỉ dùng cho học thuật, và điều khoản của nhà cung cấp có thể cấm dùng kết quả để huấn luyện.

**Tốc độ và trải nghiệm:**
- Bóng đầu ~2,4 s, sau đó dịch trước các trang kế để người đọc không phải chờ.
- Hàng đợi tiết kiệm chỉ áp dụng khi vượt ngưỡng, không làm chậm người đọc bình thường.

**Ràng buộc bản quyền model phụ:**
- Detector thứ hai (comic-text-detector) học trên Manga109-s, chỉ dùng cho học thuật, nên **gói trả phí phải tắt nó**.
- Khi tắt, độ phủ chữ của gói trả phí là ~95,2% thay vì 96,4% (60 trang, DeepSeek), cho đến khi có detector học trên dữ liệu được phép dùng thương mại.

**Thanh toán:**
- VietQR / chuyển khoản qua cổng (payOS…), MoMo, ZaloPay.
- Extension và web reader thu tiền qua web, nên không mất 15–30% phí kho ứng dụng.
- Phí cổng cần xác nhận khi ký.
- Không tự gia hạn ngầm; hết lượt thì báo, không tự trừ tiền.

**So sánh giá:**
- Netflix Mobile ~74k, YouTube Premium ~79k/tháng ([Finhay](https://www.finhay.com.vn/cac-goi-netflix), [CafeF](https://cafef.vn/youtube-premium.html)).
- Ichigo $8,99/tháng ≈ 236k ([Gumroad](https://ichigo.gumroad.com/l/ichigo-reader)).
- Torii: credit từ $5,99 ([toolmage](https://www.toolmage.com/en/tool/toriitranslate/)).

## 8. Việc cần làm tiếp (theo thứ tự)

1. Làm cách 1 (định dạng gọn). Đo trên 60 trang: chi phí, thời gian cả trang, độ phủ chữ, rồi chấm mù 50 bóng so với bản hiện tại.
2. Làm cách 2 và 4. Thử cách 3 kèm đo CER.
3. Đo model mở đọc ảnh (Qwen3-VL 8B…) trên GPU: chất lượng (chấm mù) và trang/giây. Đây là điều kiện để tiến tới "gần như 0 đ".
4. Đo CPU/RAM máy chủ thật cho tìm vùng và vẽ lại (mobile), cộng vào giá vốn.
5. Beta 20–30 người đọc để đo phân bố trang/tháng thật, rồi chốt ngưỡng và giá.

## 9. Thử model mới, mức "suy nghĩ" và gói thuê bao (21/10)

### 9.1 Quét mức suy nghĩ (25 trang đôi của nhóm, 419 bóng)

Điều kiện chung: prompt v5, tắt detector thứ hai (giống gói trả phí), mỗi cấu hình chạy 1 lượt, sáng 21/10 (giờ UTC). Giới hạn 6.000 token đầu ra mỗi trang.

| Cấu hình | Lỗi đọc chữ (CER) | chrF so với bản chuẩn | Bóng đầu p50 | Cả trang p50 | $/trang đôi |
|---|---|---|---|---|---|
| Claude Haiku 5.5 (mặc định) | **14,4%** | 38,2 | 8,8 s | 14,0 s | $0,00143 |
| DeepSeek V4.1 Flash 1017, tắt suy nghĩ | 20,5% | **38,5** | **4,2 s** | **9,3 s** | **$0,00109** |
| DeepSeek 1017, suy nghĩ mức thấp | — | — | 18,4 s | 29,4 s | $0,00313 |
| MiniMax M3.1 Flash, mức thấp (OpenRouter, bản free) | 27,1% | 28,9 | 37,9 s | 45,4 s | $0 hôm nay (giá niêm yết ≈ $0,003) |

**DeepSeek bật suy nghĩ:**
- Mức thấp: **18/25 trang không ra bản dịch**, vì phần suy nghĩ dùng hết 6.000 token. Chỉ 92/481 ô được dịch.
- Mức vừa (12 trang thì dừng): tương tự, khoảng $0,003/trang.
- Nới giới hạn token cũng không cứu được. Trang sẽ tốn gấp 3–6 lần và chậm gấp 4 lần, tức thua Haiku cả về giá lẫn tốc độ.
- **Điểm ngọt của DeepSeek vẫn là tắt suy nghĩ.**

**MiniMax M3.1 Flash (ra 19/10):**
- Model này bắt buộc suy nghĩ.
- Qua OpenRouter: đọc và dịch kém hơn rõ rệt (chrF 28,9 so với khoảng 38). Bản free lại chậm (38 s mới có bóng đầu).
- Qua Ollama cloud (máy đã đăng nhập): suy nghĩ hết 6.000 token, rồi hết cả 16.000 token, mà không ra bản dịch nào (70–169 s một trang). Tham số mức suy nghĩ dường như không có tác dụng.
- Với giá niêm yết $0,15/$0,60, mỗi trang khoảng $0,003, đắt gấp đôi Haiku. **Không dùng.**

**Haiku chậm hơn số đo ngày 19/10** (8,8 s so với 5,5 s), dù prompt chỉ dài hơn khoảng 15%. Có thể do nhà cung cấp lúc đo. Chất lượng vẫn ổn định: CER 14,4%, chrF 38,2.

**Hướng tìm điểm ngọt tiếp (chưa đo):** chia việc theo trang.
- DeepSeek tắt suy nghĩ làm mặc định nhanh và rẻ.
- Chỉ những trang khó (nhiều chữ nhỏ, chữ viết tay, nhiều ô bị đọc lỗi) mới chuyển sang Haiku.
- Cách này nhắm lấy độ đọc đúng của Haiku với giá và tốc độ gần DeepSeek.

**Chặn rủi ro:** model Ollama có đuôi `:cloud` gọi qua localhost nhưng thực ra chạy trên máy chủ Ollama, nên giờ bị từ chối trong chế độ offline. Ollama cloud có đường gọi riêng `ollama-cloud/…`, được ghi rõ là dịch vụ cloud.

### 9.2 Gói thuê bao có API key thay vì mua API trực tiếp?

| Nhà cung cấp | Gói | Có gì | Vướng ở đâu |
|---|---|---|---|
| Ollama | Pro $20/tháng → $60 tín dụng; Max $100 → $300; Team $500 → $1.000 | API key, endpoint tương thích chuẩn OpenAI; cam kết không ghi log, không huấn luyện; giá rẻ hơn ngoài giờ cao điểm (12–18 UTC ngày thường) | Chỉ có model mở, không có Haiku. Pro chỉ 3 yêu cầu đồng thời. Khung 12–18 UTC lại đúng 19–01 giờ Việt Nam, giờ người Việt đọc truyện nhiều nhất. Điều khoản không nói rõ chuyện dùng làm nền cho sản phẩm bán cho người khác (cấm "truy cập tự động khi chưa được phép"), cần hỏi hello@ollama.com |
| NanoGPT | $12/tháng, 60 triệu token đầu vào/tuần | Model mở | Không có Claude/Gemini; chưa rõ có model đọc ảnh |
| Synthetic | $20–60/tháng, giới hạn số yêu cầu mỗi 5 giờ | Không huấn luyện, xóa dữ liệu sau 14 ngày | Chủ yếu model chỉ đọc chữ |
| Chutes | $3–20/tháng | Mạng suy luận phi tập trung | Hạn mức không công bố |
| Gói "coding" (GLM, MiniMax, Kimi, Qwen) | $3–168/tháng | Rẻ | Điều khoản chỉ cho dùng trong công cụ lập trình (Z.ai ghi rõ), không dùng làm nền cho app được |

**Kết luận:**
- Gói thuê bao chỉ đáng khi có một model mở trên đó dịch tốt ngang Haiku. Đến nay chưa có model nào như vậy.
- Gói thuê bao được thiết kế cho một người dùng tương tác, nên có giới hạn đồng thời và theo khung giờ, không hợp để phục vụ nhiều người đọc.
- Đường giảm chi phí chắc chắn hơn khi mở rộng:
  - Batch API −50% cho "dịch sẵn chương kế" (§3);
  - cache prompt;
  - tín dụng khởi nghiệp của các hãng;
  - khi đủ lớn thì tự thuê GPU chạy model mở (§7).
- **Ollama Pro $20 vẫn hợp cho giai đoạn beta:** thử nhanh nhiều model mở mà không phải nạp tiền từng nơi.
