# So sánh với manga-image-translator (zyddnys)

Đọc mã nguồn nhánh `main` ngày 19/10/2026 (các file cấu hình, prompt, ngữ cảnh, mặt nạ, inpainting).
Chỉ học ý tưởng; **không chép mã** — repo dùng GPL-3.0, chép mã sẽ buộc phần được phân phối của mình theo GPL-3.0.

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
