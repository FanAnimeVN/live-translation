# Định hướng đồ án và sản phẩm — 22/10/2026

Tài liệu này gom các quyết định rút ra từ số đo ngày 21–22/10. Chi tiết số liệu nằm ở [LOCAL-MODELS.md](LOCAL-MODELS.md), kế hoạch beta ở [BETA-PLAN.md](BETA-PLAN.md), nghiên cứu nền ở [báo cáo](../reports/Model%20local%20v%C3%A0%20g%C3%B3i%20beta%20VN.md).

## 1. Một pipeline cho mọi nơi chạy

```
ảnh trang → detector (vùng chữ) → OCR từng ô (Baberu) → model ngôn ngữ dịch theo ngữ cảnh → dàn chữ lên tranh
                                                        ↑ bộ nhớ truyện, thẻ "Ai là ai?", ảnh mặt nhân vật (~2% token)
```

**Vì sao "OCR trước" (đo 22/10, Haiku 5.5, 25 trang, mỗi cách 1 lượt):**
- So với gửi ảnh: rẻ hơn 25%, token đầu nhanh hơn ~4 lần, đọc sai chữ Nhật ít hơn, chrF không kém.
- Model OCR nhỏ (54–200M tham số) đọc chữ manga ngang hoặc tốt hơn LLM lớn. Model ngôn ngữ chỉ còn việc của nó: dịch, chọn xưng hô, giữ danh xưng.
- Cùng một pipeline chạy được ở bốn nơi, chỉ khác chỗ chạy từng bước:

| Nơi chạy | Detector + OCR | Model ngôn ngữ | Ghi chú |
|---|---|---|---|
| **Cloud (gói trả phí)** | server (OCR: GPU encoder + CPU decoder) | Haiku 5.5; DeepSeek cho chế độ nhanh | ~$0,001/trang đôi |
| **BYOK (extension)** | ngay trong trình duyệt (ONNX Runtime Web, Baberu int4 122 MB) | nhà cung cấp người dùng chọn | chỉ gửi chữ (và ảnh mặt), ảnh trang không rời máy |
| **Local máy tính** | như BYOK | Ollama: Gemma 4 12B (12–16 GB) / Hy-MT2-7B Q6 (8 GB) | offline hoàn toàn |
| **Điện thoại** | trên máy (Baberu int4 / manga-ocr bản mobile) | cloud/BYOK chỉ nhận chữ; offline chỉ cho máy mạnh (Gemma 4 E2B/E4B) | cảnh báo rõ chất lượng và pin |

## 2. Đồ án: đóng góp và thí nghiệm

1. **"OCR trước" so với "VLM đọc ảnh":** bảng chi phí, độ trễ, CER, chrF, độ đúng xưng hô cho ba cách gửi. Đã có số chi phí, độ trễ, CER, chrF; độ đúng xưng hô đang đo.
2. **Bộ nhớ xưng hô có hướng và thẻ "Ai là ai?":** người đọc khóa thông tin, model chỉ được đề xuất. Đo độ đúng cặp xưng hô (PCA) trên nhãn của nhóm.
3. **OCR fine-tune có SFX:**
   - model gốc sai 70–78% ở SFX, nên đây là chỗ train thêm có lợi nhất;
   - đánh giá **không rò rỉ** trên 22 bộ chỉ có trong Manga109 bản học thuật, vì mọi model train trên Manga109-s đều chưa thấy chúng;
   - 5 bộ test của nhóm đều thuộc Manga109-s, nên điểm của các model train trên Manga109-s đo trên 5 bộ này có thể bị thổi cao.
4. **Chế độ local trên GPU phổ thông:** bảng so sánh model (Kaggle T4, gần với RTX 4050/4060).
5. **Phương pháp đánh giá:**
   - chia dữ liệu theo bộ truyện (`tools/kaggle/manga109-split-v2.json`);
   - kiểm tra rò rỉ dữ liệu;
   - mỗi số đo ghi rõ điều kiện chạy (model, số lượt, cold/warm).

## 3. Giấy phép: hai nhánh không trộn lẫn

- **Manga109-s đã được duyệt (22/10):** 87 bộ, được dùng thương mại kết quả train (kể cả model) nếu ghi rõ đã dùng Manga109-s. Danh sách bộ: `tools/kaggle/manga109s-titles.json`.
- **Bảng giấy phép cho từng model** ([apps/server/src/licenses.ts](../apps/server/src/licenses.ts)): gói trả phí (`PAID_TIER=1`) từ chối model "no"/"review". Model "credit" phải hiện dòng ghi công trong app.
- **Bản học thuật Manga109 đầy đủ:** chỉ dùng cho số liệu đồ án. Không model nào train trên 22 bộ học thuật được vào sản phẩm.
- **Còn phải rà soát trước khi bán:**
  - detector chính (dữ liệu train chưa công bố);
  - ảnh cắt cho nhánh thương mại phải cắt lại từ chính bản Manga109-s;
  - bốn câu hỏi pháp lý trong BETA-PLAN §2.4.

## 4. Lộ trình

| Tuần | Sản phẩm | Đồ án / dữ liệu |
|---|---|---|
| 1 | "OCR trước" thành mặc định nếu độ đúng xưng hô không tụt; OCR chạy trên worker thread (mục tiêu ≤ 1 s/trang); commit Reader + chế độ chia sẻ, mở tunnel cho bạn bè | Kaggle: bảng xếp hạng OCR không rò rỉ + fine-tune trên Manga109-s (2 GPU song song) |
| 2 | Extension MV3: detector + OCR trong trình duyệt (WebGPU/WASM), BYOK chỉ gửi chữ, kết nối model local | Thêm 20–30 trang raw ngoài Manga109 có nhãn để đo thực tế |
| 3 | Web reader cho điện thoại (PWA); tài khoản + credit + VietQR; chế độ SFX (chú thích gỡ được) | Train OCR SFX; cắt lại dữ liệu từ bản Manga109-s cho nhánh thương mại |
| 4 | Hoàn thiện UI/UX, phát hành beta (Unlisted) | Báo cáo đồ án: bảng số cuối, demo, video |

## 5. Quyết định đã tự chốt trong đêm 21–22/10 (nhóm có thể đổi)

- Nộp đơn Manga109-s bằng thông tin bạn cung cấp; đơn được duyệt ngay.
- Chọn **Baberu v1.2** (Apache-2.0, train trên Manga109-s) làm OCR của sản phẩm.
  - Bản TypeScript trong server đạt CER 6,2% trên hộp nhãn và 12,9% trên vùng detector, khớp bản PyTorch (6,3% / 12,9%).
  - Tốc độ 145 ms/ô khi encoder chạy trên GPU qua DirectML.
- Thêm ba chế độ đọc trang (`READING_MODE` = `image` | `ocr+image` | `ocr`). Mặc định vẫn là `image` cho tới khi có số đo độ đúng xưng hô.
- Chia dữ liệu lại thành v2 để đo không rò rỉ.
