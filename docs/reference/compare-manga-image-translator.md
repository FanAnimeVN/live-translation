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
| Giữ góc nghiêng của từng dòng (detector trả về góc), vẽ chữ dịch rồi nắn phối cảnh vào khung xoay | Detector của mình chỉ cho khung thẳng, nên đo góc từ mực chữ: hình chiếu theo dòng hoặc theo cột sắc nhất ở đúng góc. Dàn chữ trong khung đã xoay | `packages/render/src/slant.ts` |
| Tách và dịch từng dòng riêng, nên giấy tờ giữ nguyên các hàng | Tìm các dòng in của khối chữ ngang căn trái (thẻ, đơn, thư viết ngang). Chia chữ Việt vào từng dòng theo độ dài dòng gốc; mỗi dòng giữ chỗ, mép trái và chiều cao | `lettersOnLines` |
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
