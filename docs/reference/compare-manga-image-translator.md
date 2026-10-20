# So sánh với manga-image-translator (zyddnys)

Đọc mã nguồn nhánh `main` ngày 19/10/2026 (các file cấu hình, prompt, ngữ cảnh, mặt nạ, inpainting); ngày 20/10 đọc thêm phần dàn chữ (`rendering/`), lọc mặt nạ (`mask_refinement/`), gộp dòng (`textline_merge/`) và luồng chính (`manga_translator.py`) ở commit `d6de6ab6`.
Dự án sẽ mở mã nên GPL-3.0 dùng được (nhóm đã chốt). Dù vậy, các bước học được ở mục 6 đều do mình tự viết lại bằng TypeScript cho hợp kiến trúc, không chép nguyên văn.

## 1. Họ đã làm tới đâu

- 10,5k sao, 1,08k fork, cập nhật 11/10/2026. Python, chạy dạng CLI / web / API / Docker (~15 GB). Dịch theo lô file ảnh.
- Mặc định: phát hiện chữ bằng model DBNet tự huấn luyện (ảnh 2 048 px) → OCR 48 px tự huấn luyện (tùy chọn manga-ocr)
  → dịch (mặc định Sugoi offline Nhật→Anh; có GPT, DeepSeek, Gemini, Ollama/OpenAI-compatible…)
  → mặt nạ chữ từ **lớp phân đoạn chữ của detector** + thành phần liên thông + giãn nở
  → vẽ lại bằng **LaMa được huấn luyện thêm trên anime/manga** (`dreMaz/AnimeMangaInpainting`, MIT, 204 MB), có AOT, LaMa-MPE, Stable Diffusion
  → dàn chữ (README tự nhận "vừa đủ dùng").
- Prompt LLM: "dịch 3 bước" (sát nghĩa → phân tích → trau chuốt), đánh số từng dòng, ví dụ mẫu (Trung/Anh/Hàn, không có tiếng Việt),
  từ điển thuật ngữ tự chọn mục liên quan, từ điển thay thế trước/sau dịch (regex).
- Ngữ cảnh: chèn nguyên văn N trang trước (`context_size`), chỉ với bộ dịch OpenAI.
- Dùng ảnh: chế độ 2 giai đoạn — model vision sửa lỗi OCR và thứ tự đọc từ ảnh, rồi mới dịch (có thể kèm ảnh).
- **Không có**: theo dõi ai nói với ai, bộ nhớ nhân vật, hệ xưng hô tiếng Việt, tóm tắt mạch truyện, chống spoil.

## 2. Mình có phải bản sao không

Không. Cùng bài toán "dịch ảnh manga" nhưng khác người dùng và khác lõi:

| | manga-image-translator | Live translation |
|---|---|---|
| Người dùng | người biết cài Python/Docker, dịch lô file | người đọc trên web, bấm là đọc |
| Ngôn ngữ đích | chủ yếu Anh/Trung | **tiếng Việt trước tiên** |
| Đọc chữ | OCR riêng → dịch văn bản (ảnh chỉ để sửa OCR) | model vision đọc **cả trang + tranh**, đoán người nói/người nghe từ hình |
| Xưng hô | không có | xưng hô có hướng A→B (anh/em/cậu/tớ…), giữ kính ngữ Nhật đúng luật |
| Ngữ cảnh dài | dán N trang trước | bộ nhớ truyện có bằng chứng, không spoil, khóa của người đọc; thiết kế global context ([STORY-MEMORY.md](../STORY-MEMORY.md)) |
| Vẽ lại | xóa theo mặt nạ rồi LaMa toàn bộ | chỉ xóa khi tách chữ an toàn; giữ chữ trang trí, giữ hatching; "Xem bản gốc" khôi phục đúng từng điểm ảnh |
| Đo lường | không có bộ đo công khai | đo trên trang thật: tìm vùng, CER, chrF, độ trễ, $/trang |

Người dùng đã chỉ đúng điểm mấu chốt: tách OCR ra văn bản thì mất thông tin ai đang nói. Tiếng Việt cần biết quan hệ
để chọn đại từ — tiếng Anh/Trung không cần — nên với tiếng Việt, đọc cả trang kèm tranh là lợi thế thật, không chỉ khác biệt kỹ thuật.

## 3. Nên học gì (theo thứ tự đáng làm)

1. **LaMa huấn luyện trên manga** (MIT): thử thay LaMa thường trong chế độ vẽ lại chất lượng cao. File là pickle PyTorch → nạp an toàn (`weights_only`), xuất ONNX, ghim SHA-256, đo bằng `inpaint-bench`.
2. **Mặt nạ học máy**: lớp phân đoạn chữ của detector (họ) cho mặt nạ sát nét chữ; dùng làm tín hiệu thứ hai bên cạnh luật của mình (luật giữ mắt, hatching, chữ trang trí).
3. **OCR truyền thống + ảnh**: cho chế độ offline/rẻ — OCR nhẹ + model dịch nhỏ (Hy-MT2), model vision chỉ kiểm tra lại khi có.
4. **Từ điển nhóm dịch**: nhập glossary, từ điển thay thế trước/sau dịch — hợp với cộng đồng scanlation Việt.
5. Phóng to ảnh trước khi phát hiện chữ nhỏ (mình đã có crop phóng to), xuất file nhiều lớp (PSD) cho team dịch.
6. Prompt "dịch 3 bước": chỉ thử khi đo được lợi, vì tăng token ra và độ trễ.

## 4. Giấy phép (khi phát hành mã nguồn mở và bán gói tiện ích)

- Mã của mình hiện chỉ dùng thư viện/model MIT hoặc Apache-2.0 (detector RT-DETR-v2, MI-GAN, LaMa, Gemma 4, Qwen3, Hy-MT2 theo khóa model) → phát hành MIT/Apache/GPL đều được.
- Nếu sau này lấy mã từ manga-image-translator: toàn bộ phần phân phối kèm phải theo GPL-3.0 (vẫn hợp với hướng mở mã, nhưng phải chọn từ đầu).
- **Dữ liệu là điểm cần cẩn thận nhất**: Manga109 chỉ cho nghiên cứu học thuật; model huấn luyện trên dữ liệu đó không nên dùng trong gói trả phí. Bộ dữ liệu nhóm đã xin phép tác giả cần ghi rõ phạm vi cho phép.

## 5. Câu trả lời cho buổi proposal

**Giá trị cho cộng đồng**: người đọc Việt chờ bản dịch nhiều tuần hoặc đọc bản máy dịch sai xưng hô; công cụ hiện có dịch sang Anh/Trung
và cần cài đặt kỹ thuật. Nhóm làm bộ công cụ **mã nguồn mở** dịch manga Nhật → Việt ngay trên trang web, hiểu ai đang nói với ai,
nhớ mạch truyện mà không spoil, giữ nguyên nét vẽ — và công bố **bộ đo Nhật→Việt cho manga** (chưa có bộ công khai nào), để cộng đồng
kiểm chứng và đóng góp. Gói trả phí chỉ bán sự tiện lợi (không cần key, không cần máy mạnh), không khóa thuật toán.

## 6. Đã học và áp dụng (20/10)

Phần vẽ lại bằng model của họ (AOT, LaMa-MPE, LaMa manga), cách nới mặt nạ và mặt nạ học máy đã được đo riêng ở [DIRECTION.md](../DIRECTION.md) (mục "Vẽ lại").
Mục này là phần còn lại: cách họ **ghép các bước** quanh model và cách họ **dàn chữ**.

| Họ làm gì | Mình áp dụng thế nào | Ở đâu |
|---|---|---|
| Che toàn bộ chữ trên trang rồi vẽ lại một lượt, nên model không còn chữ nào để chép | Vẫn vẽ lại từng vùng, nhưng mỗi lần vẽ đều che luôn lỗ của mọi vùng khác đang chờ vẽ lại | `apps/server/src/redraw.ts` (`withNeighbours`) |
| Mặt nạ học máy nhận cả chữ nét đậm là chữ, nên vẽ lại được hết | Lượt cuối, chỉ chạy khi đã vẽ lại cả khung mà vẫn đo được nét chữ. Gỡ bảo vệ cho mảng cỡ một chữ, hoặc tới 2 lần cỡ chữ nếu nằm trọn trong khung. Ảnh, mặt, nét tranh dài vẫn giữ | `wholeBoxes` |
| Màu chữ và màu viền lấy từ chữ gốc; viền chữ dịch bằng màu nền; khi hai màu quá gần thì viền đổi sang trắng/đen | Server đọc màu nét gốc (nửa đậm nhất của nét) và tông sạch quanh nét. Renderer viền bằng tông đó nếu đủ tương phản, không thì trắng/đen như họ. Trước đây chữ trên tranh luôn là đen viền trắng | `textColours`, `haloColour` |
| Giữ góc nghiêng của từng dòng (detector trả về góc), vẽ chữ dịch rồi nắn phối cảnh vào khung xoay | Detector của mình chỉ cho khung thẳng, nên đo góc từ mực chữ: hình chiếu theo dòng hoặc theo cột sắc nhất ở đúng góc. Chỉ tính các mảng mực cỡ một chữ (≤ 1,6 chữ), để bàn tay vắt qua tấm áp phích hay nét tốc độ không làm nghiêng chữ. Dàn chữ trong khung đã xoay | `packages/render/src/slant.ts` |
| Tách và dịch từng dòng riêng, nên giấy tờ giữ nguyên các hàng | Tìm các dòng in của khối chữ ngang căn trái (thẻ, đơn, thư viết ngang). Chia chữ Việt vào từng dòng theo độ dài dòng gốc; mỗi dòng giữ chỗ, mép trái và chiều cao. Chữ thẳng chỉ dàn theo dòng khi không nhỏ hơn 90% cách dàn khối thường | `lettersOnLines` |
| (Họ không có) | Một dòng hoặc cột gốc uốn cong: chữ Việt đặt từng ký tự trên cùng cung | `arcBow`, `placeOnArc` |
| (Mình giữ cách riêng) | Lỗ nằm giữa giấy trắng: điểm sáng model vẽ ra được đưa về đúng màu giấy, nét tối model nối tiếp được giữ | `snapToPaper` |
| Họ chỉ che điểm ảnh chữ, nên ảnh trong khung chữ không bị đụng | Khi phải vẽ lại cả khung, vùng ảnh nằm trong khung chữ (ảnh trên thẻ, chân dung trong khung) được giữ: vùng phần lớn là tông xám trung gian, rộng hơn 1,5 chữ, ít nét chữ. Chữ Việt cũng tránh vùng đó | `keepPictures`, `avoidPictures` |
| Mỗi dòng là một vùng riêng nên không giành chỗ | Khung nghiêng lớn chứa tâm của một khung nghiêng nhỏ hơn thì nhường phần đó (cắt theo chiều giữ được nhiều chỗ hơn). Chống chồng chữ so hình xoay thật, không so khung thẳng bao ngoài | `avoidAreas`, `quadsTouch` |

Không làm theo họ: nới mặt nạ theo cỡ chữ và vẽ cả trang một lần (đã đo, không sạch hơn), dense CRF (nặng, mặt nạ của mình đã bám mép).

Đo trên 60 trang (10 trang GT + 50 trang bộ của nhóm), bản dịch Haiku có sẵn (`recall-k-k10`), vẽ lại auto + big-lama, `INPAINT_DEVICE=dml`, một lượt mỗi cột, ngày 20/10 (`tools/eval/src/render.ts`):

| 60 trang, 935 vùng có chữ Việt | Trước | Sau |
|---|---|---|
| Còn sót nét chữ Nhật dưới chữ Việt | 10 | **1** (MN109-ARMS-008 r7) |
| Chữ tràn / chữ chạm nhau / chữ đè chữ chưa xóa | 0 / 0 / 0 | 0 / 0 / 0 |
| Chữ ra ngoài bóng | 4 | 4 |
| Vùng chưa vẽ lại được | 1 | 1 |
| Tổng thời gian vẽ lại | 111,8 s | 108,3 s |

Nhìn bằng mắt các vùng từng sót chữ: chữ đậm (唯一, chữ đậm trong bóng, chữ trên lông thú) đã sạch. Tấm thẻ trên trang MN109-Akuhamu-004 giờ được dàn nghiêng đúng góc thẻ (−18,8°), ảnh trên thẻ được giữ, hai khối chữ trên thẻ không giành chỗ nhau.
Chưa đạt: thẻ này kẻ bảng giữa các dòng nên chưa tách được từng dòng in (chữ Việt dàn thành một khối nghiêng nhỏ); dàn từng dòng mới chạy được khi giữa các dòng có khe trắng (đã có test). Bước tiếp: bỏ các đường kẻ thẳng dài trước khi tìm dòng, và nhờ model trả ngắt dòng cho thẻ, đơn, thư viết ngang.

Audit sau đó (20/10, cùng 60 trang): xem tận mắt mọi vùng được dàn kiểu mới. Bắt được 2 lỗi và đã sửa: một tấm áp phích bị coi là nghiêng 31° vì ngón tay vắt qua chữ (UchiNoNyan'sDiary-005 r2), và 3 chú thích thẳng hai, ba dòng bị dàn theo dòng nhỏ hơn bản cũ (MN109-07 r10, ARMS-008 r14, UchiNoNyan'sDiary-005 r30). Sau khi sửa: số liệu QA giữ nguyên (sót 1, tràn 0, chạm 0); vùng dàn kiểu mới còn 3: hai khối trên tấm thẻ (−19°) và một dòng chữ viết tay xiên (Akuhamu-010 r27, −9°). Thời gian dàn chữ (không tính vẽ lại) trung vị 547 ms/trang, p90 1,30 s, bằng bản trước khi thêm phần này (547 ms, 1,22 s).

### Vòng 3 (20/10): đo phần QA không thấy, test bằng bản dịch mới

**Chữ Nhật bị bỏ sót hẳn.** QA dàn chữ (`render.ts`) chỉ chấm các vùng đã có, nên không thấy chữ mà detector không tìm ra. Công cụ mới `tools/eval/src/gt-coverage.ts` so từng ô chữ GT (946 ô trên 60 trang) với kết quả của trang:

| 946 ô chữ GT | Haiku (bản dịch có sẵn) | DeepSeek (dịch mới 20/10) |
|---|---|---|
| Đã dịch | 869 (91,9%) | 901 (95,2%) |
| Model để lại làm tranh (SFX, chữ trang trí, tiêu đề) | 43 | 12 |
| Bỏ sót hẳn (không vùng nào phủ) | 34 | 33 |

Phần bỏ sót là giới hạn của detector, không phụ thuộc model dịch. Phần lớn rơi vào bóng thoại nhỏ trên nền tối hoặc nền tone, nhãn tên nhỏ, và chữ viết tay. manga-image-translator dò chữ bằng model phân đoạn ở ảnh 2048 px.
Đã thử cách gần nhất mà không đổi model: chạy thêm detector trên 6 ô cắt mỗi trang (phóng to khoảng 2,7 lần). Kết quả: tìm lại 10/32 ô sót, sinh thêm 34 ô không phải chữ, chậm thêm 3,1 s/trang trước lúc gọi model, nên **không bật**.
Bước tiếp: thử comic-text-detector (lớp mặt nạ họ dùng, đã có ONNX ở máy) làm detector thứ hai. Model này học trên Manga109-s, nên chỉ dùng cho bản miễn phí và mã nguồn mở.

**Sửa trong vòng này** (mỗi lỗi đều xem tận mắt trước khi sửa):
- **Dải chú thích giữa hai ô tranh (ARMS-008 r7, chỗ sót cuối cùng).** Các nét chữ chạy cạnh đường viền dải bị luật "trường gạch" giữ lại, còn model vẽ đè tranh lên cả dải. Giờ, nếu còn sót mà nền sau chữ là giấy trắng đồng đều, khung được dựng lại từ ảnh gốc: giữ mảng mực chạm mép và dài hơn 1,6 chữ (đường viền, nét tranh) cùng mảng đặc (mắt nhân vật), tô giấy phần còn lại (`snapBoxesToPaper`).
- **Hai bóng chồng nhau (ARMS-004 r6 còn lòi chữ).** Bản vá của bóng bên cạnh làm bóng này bị đánh giá lại là "chưa xóa được". Giờ trình dàn chữ xóa các vùng không vá trên ảnh gốc trước, rồi mới đặt bản vá. Lỗ vẽ lại cũng không ăn vào khung chữ và bóng của vùng khác (`clearOthers`).
- **Bóng hét có gai bị sơn thành khối trắng (Uchi-002 r3).** Khi bóng không có lòng khép kín, chỉ xóa nét quanh khung chữ thật. Viền bóng cong nằm trọn trong khung giờ được giữ như nét dài. Chữ Việt dàn theo lòng bóng quét từng hàng từ giữa ra, dừng ở viền và gai (`scanBalloon`).
- **Tên dài một từ ("Moriguo-kuuun!") bị co nhỏ nhất.** Cho ngắt dòng sau dấu gạch nối khi cả từ không vừa một dòng.
- **Chữ in ngang trong khung cao hẹp bị xoay dọc.** Chỉ xoay dọc theo cột khi phép đo góc cho thấy chữ gốc viết theo cột.

**Bản dịch mới bằng DeepSeek** (deepseek-v4.1-flash-1017, 60 trang, một lượt): 0,057 USD, bóng đầu trung vị 2,9 s (p90 3,6 s), cả trang trung vị 8,8 s. Lỗi của model: chép câu trên tấm áp phích vào cả một dải hẹp không có chữ (UchiNoNyan'sDiary-005 r28). Chưa chặn tự động, vì chặn câu lặp dễ chặn nhầm thoại lặp thật.

QA dàn chữ sau vòng này (60 trang, auto + big-lama, `INPAINT_DEVICE=dml`, một lượt mỗi cột):

| 60 trang | Haiku | DeepSeek |
|---|---|---|
| Vùng có chữ Việt | 936 | 951 |
| Sót nét / chưa vẽ lại / tràn / chạm nhau | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| Chữ đè lên chữ giữ làm tranh | 0 | 3 (dòng phụ đề dưới logo: khung logo trùm cả dòng phụ đề) |
| Chữ ra ngoài bóng | 0 (trước vòng này 4) | 1 (trước 6) |

### Vòng 4 (20/10 tối): detector thứ hai, bóng nhỏ bị bỏ sót, tiếng hét

- **comic-text-detector làm detector thứ hai** (ONNX bản manga-image-translator phát hành, GPL-3.0, học trên Manga109-s), chạy song song với detector chính:
  - Khối chữ (độ tin ≥ 0,4) mà detector chính không phủ thì thêm vào. Khối nằm trên một ô chữ yếu của detector chính thì xác nhận ô đó.
  - 60 trang: tìm lại 17/32 ô chữ bị sót. Dịch lại bằng DeepSeek: **đã dịch 95,2% → 96,4%, bỏ sót 33 → 20 ô**.
  - Có GPU thì thêm ~0,1 s/trang; chỉ có CPU thì thêm 1,6 s/trang nên mặc định tắt. Bóng đầu không chậm hơn (trung vị 3,47 s so với 3,39 s).
  - Gói cloud trả phí phải đặt `DETECT_CTD=0` vì giấy phép dữ liệu học.
- **Bóng nhỏ trên nền tram/gạch bị vẽ lại thành vệt.**
  - Detector chính chỉ cho các bóng này điểm 0,04–0,15 (dưới ngưỡng 0,2), nên chúng thành "chữ tự do" và bị model vẽ lại, kéo tram vào lòng bóng trắng.
  - Giờ ảnh tự quyết (`findBalloon`): chữ nằm trong một vùng giấy sáng khép kín, viền trơn, ôm sát chữ, bên trong không có gì ngoài chữ. Phải có thêm một trong hai: detector chính "hơi thấy" bóng ở đó (≥ 0,035, IoU ≥ 0,6), hoặc viền rất tròn.
  - Không áp dụng cho: khung chữ do model báo bỏ sót (khung lỏng), vùng có đường kẻ chạy ngang chữ (bảng, biểu mẫu), vùng lớn hơn 10% trang mà detector không chắc, dải hẹp (cột chú thích).
  - Bản đầu nhận nhầm cả ô tranh làm bóng, nhóm phát hiện khi xem tận mắt và đã loại. Bản cuối nhận 20/320 vùng chữ tự do; xem từng vùng, tất cả là bóng thoại, khung chú thích hoặc tờ giấy.
- **Nét chữ chạm viền bóng** (bóng nhỏ đầy chữ đậm, tiếng hét trong bóng gai): loang không tới được các nét này. `paintBalloon` tô lại cả hình lòng bóng và giữ viền:
  - bóng nhỏ: lấy bao lồi của phần giấy giữa các chữ;
  - bóng lớn: bắn tia từ giữa chữ ra viền.
  - Từ chối khi bóng hở hoặc bên trong có tranh.
- **Tiếng hét chữ to** (như raw vẽ): viết hoa, đậm, cỡ theo chữ gốc.
  - Một từ ngắn trong cột cao thì xếp dọc từng chữ cái, mỗi chữ đứng thẳng. **Không xoay 90°**: nhóm đánh giá chữ xoay ngang trong bóng là lỗi.
  - Chỉ áp dụng khi model đánh dấu "shout" và chữ gốc to hơn chữ thường của trang ≥ 1,3 lần, hoặc chữ to gấp đôi và từ dài ≤ 8 chữ cái. Câu thường ("May quá!") giữ nguyên.
- **Chặn chữ Việt đè lên chữ Nhật chưa xóa.** Chữ rỗng có viền vắt qua mép bóng gai làm phép đo sót nét bị lừa (ARMS-006 r6).
  - Giờ trong bóng: nếu xóa xong mà phần lõi khung chữ còn hơn nửa lượng mực ban đầu thì vùng đó chờ vẽ lại, không dàn chữ.

QA dàn chữ 60 trang (DeepSeek ds-ctd2, chỉ MI-GAN vì máy thiếu RAM, chạy 6 đợt):

| | Trước vòng này | Sau |
|---|---|---|
| Vùng có chữ Việt | 991 | 992 |
| Sót nét / tràn / chạm nhau | 3 / 0 / 0 | 4 / 0 / 0 |
| Chữ đè lên chữ giữ làm tranh / chữ ra ngoài bóng | 2 / 1 | 2 / 1 |

- Vùng sót nét thêm (AisazuNihaIrarenai-009 r27, chấm furigana) giống hệt ảnh trước vòng này; trang đó lần trước chạy lỗi RAM nên chưa được đếm.
- **Phần khung chữ thò ra ngoài bóng** (tiếng hét chạy qua mép bóng gai): xóa nét chữ ở đó như chữ tự do, giữ nét tốc độ và mép gai.
  - Chỉ giữ kết quả khi phần đó sạch hẳn. Nếu gửi cả bóng cho model vẽ lại chỉ vì một dải nhỏ, các nét chữ cũ hiện lại như bóng ma (đã thử và loại).
  - Chữ hét viết hoa chỉ đặt vào phần cột sạch; cột không sạch thì dàn chữ bình thường.
  - QA 60 trang sau thay đổi: các số trong bảng trên giữ nguyên.
- **Còn lại:**
  - Tiếng hét ARMS-005 r1: chữ あ rỗng có viền dính vào mép bóng gai, phía dưới mở ra giấy trắng có nét tốc độ. Luật hiện tại không tách được chữ khỏi mép gai.
    - Cách đúng là mặt nạ chữ học máy, như manga-image-translator: mặt nạ đánh dấu điểm ảnh chữ, rồi tô lại.
    - comic-text-detector không dùng được cho gói trả phí. comic-text-mask cần kiểm giấy phép trước.
  - Vài vùng nhỏ trên nền tối còn vệt xám (MI-GAN).
  - 77% câu thoại chưa rõ người nói.
