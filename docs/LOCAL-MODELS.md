# Model local và "OCR trước" — số đo 21–22/10/2026

**Điều kiện chung:**
- 25 trang đôi của nhóm (Manga109, 5 bộ), 419 dòng có nhãn, 481 vùng do detector tìm (tắt CTD).
- Prompt v5, mỗi cấu hình **chạy 1 lượt**.
- Model local chạy trên Kaggle 2×T4 bằng Ollama 0.40.7 (`tools/kaggle/local-models.py`). Model cloud gọi qua OpenRouter (`tools/eval/src/hint-cloud.ts`).
- Chấm trên máy nhóm bằng `tools/eval/src/kaggle-score.ts`; bản dịch chuẩn không rời máy.

**Cách đọc các chỉ số:**
- CER: tỉ lệ ký tự Nhật đọc sai. chrF: độ gần với bản dịch chuẩn của nhóm.
- Bảng 2 chấm theo từng dòng nhãn. Các bảng còn lại chấm theo vùng detector khớp với nhãn. Vì vậy chỉ so các số trong **cùng một bảng**.

## 1a. Pipeline thật của sản phẩm (22/10, `tools/eval/src/bakeoff.ts --reading …`)

**Điều kiện:**
- Haiku 5.5, 25 trang của nhóm, mỗi chế độ chạy 1 lượt.
- Có bộ nhớ truyện; các trang trong một bộ chạy lần lượt, trang sau dùng bộ nhớ của trang trước.
- OCR Baberu chạy trên server: encoder trên GPU qua DirectML, decoder trên CPU.
- Xưng hô đo bằng `tools/eval/src/pronouns.ts` so với bản dịch chuẩn của nhóm, trên 106 bóng có đại từ.
- Chế độ `image` là lượt quét ngày 21/10 (`sweep-haiku`).

| Chế độ đọc | Dòng nhãn đúng hết | Đọc sai | chrF | Bóng đầu p50 | Cả trang p50 | $/trang đôi | Xưng hô khớp | Mâu thuẫn xưng hô | Người nói "không rõ" |
|---|---|---|---|---|---|---|---|---|---|
| `image` (cũ) | 280/419 | 14,4% | 38,2 | 8,8 s | 14,0 s | 0,00143 | 28,3% | 49,1% | 7% |
| `ocr` | 293/419 | 12,9% | 40,2 | **5,3 s** | **10,6 s** | **0,00107** | **33,0%** | 45,3% | 35% |
| `ocr+image` | **303/419** | **12,4%** | 39,7 | 12,6 s | 17,5 s | 0,00141 | 33,0% | **40,6%** | 28% |
| **`ocr+thumb` (mặc định mới)** | 293/419 | 13,3% | **40,3** | 7,9 s | 13,1 s | 0,00110 | 30,2% | 48,1% | **5%** |
| `ocr+thumb`, OCR chạy song song trên worker thread (đo lại) | 294/419 | 13,4% | 40,6 | 7,1 s | 12,5 s | 0,00114 | 34,0% | 39,6% | 7% |
| **DeepSeek V4.1 Flash 1017, `ocr+thumb`** | 293/419 | **12,9%** | **41,0** | **3,2 s** | **7,6 s** | **0,00077** | **39,6%** | **38,7%** | 11% |
| (đối chiếu) DeepSeek 1017 đọc ảnh, 21/10 | — | 20,5% | 38,5 | 4,2 s | 9,3 s | 0,00109 | — | — | — |

**DeepSeek + OCR:**
- Nhờ đã có chữ đọc sẵn, DeepSeek đọc đúng ngang Haiku. Nó còn nhanh gấp đôi, rẻ hơn 32% so với Haiku `ocr+thumb` (46% so với Haiku đọc ảnh), và cho chrF cùng độ khớp xưng hô cao nhất.
- **Chưa đủ để đổi mặc định:** chrF và độ khớp xưng hô không bắt được lỗi sai nghĩa nặng. Ở lần chấm mù trước (30 câu khác nhau nhiều nhất), DeepSeek có 8 lỗi nặng, Haiku có 3.
- **Đề xuất:**
  - dùng ngay DeepSeek + OCR cho gói "Nhanh" và cho trang người đọc đang chờ;
  - đổi mặc định sau khi nhóm chấm mù lại với `ocr+thumb` (`/judge`).

**Đọc kết quả:**
- **Chỉ gửi chữ OCR** là nhanh và rẻ nhất, xưng hô cũng khớp nhất. Nhưng không thấy tranh thì 35% người nói thành "không rõ", và bộ nhớ truyện mất thông tin để nối nhân vật qua các trang.
- **Gửi kèm ảnh thu nhỏ 640 px** chỉ tốn thêm ~3% mà người nói trở lại như chế độ ảnh (5% "không rõ"). Chế độ này rẻ hơn chế độ ảnh 23%, đọc chữ đúng hơn, chrF cao hơn.
- **Vì vậy mặc định là `ocr+thumb`:**
  - `ocr` dành cho chế độ "nhanh/rẻ";
  - `image` dành cho máy chưa có model OCR (sản phẩm tự quay về chế độ này).
- **Mỗi chế độ chỉ chạy một lượt,** nên chênh lệch xưng hô 2–5 điểm có thể là nhiễu. Cần chạy lại 2–3 lượt trước khi đưa vào báo cáo đồ án.
- **OCR chạy nối tiếp mất 2,7 s/trang trên máy nhóm.** Đưa OCR sang worker thread sẽ rút ngắn thời gian tới bóng đầu.

## 1. Cloud: gửi chữ OCR đọc sẵn cho Claude Haiku 5.5 (gói trang dựng sẵn, không bộ nhớ)

| Cách gửi | CER | chrF | Token đầu p50 | Cả trang p50 | Token vào/ra mỗi trang | $/trang đôi |
|---|---|---|---|---|---|---|
| Ảnh (như sản phẩm hiện nay) | 16,2% | 38,6 | 7,3 s | 13,8 s | 7.353 / 1.749 | 0,00135 |
| Ảnh + chữ OCR (Baberu) | **12,7%** | 40,0 | 6,1 s | 11,7 s | 7.703 / 1.737 | 0,00136 |
| **Chỉ chữ OCR, không ảnh** | 12,9% | **40,3** | **1,6 s** | **7,4 s** | 4.187 / 1.708 | **0,00101** |

**Đọc kết quả:**
- **Chỉ gửi chữ OCR:** rẻ hơn 25%, token đầu nhanh hơn 4,5 lần, mà không kém về chữ Nhật lẫn chrF.
- **Chưa đo:** chrF không đo được ai nói với ai. Bỏ ảnh có thể làm sai người nói và xưng hô. Phải đo bằng nhãn người nói trước khi bỏ ảnh.
- **Đầu ra vẫn đắt:** ~1.700 token mỗi trang, phần lớn vì model chép lại chữ Nhật. Khi đã có OCR, bỏ phần chép này sẽ giảm thêm chi phí.
- **Dao động giữa các lượt:** lượt "ảnh" hôm nay đạt CER 16,2% và chrF 38,6, còn lượt quét ngày 21/10 là 14,4% và 38,2. Chênh lệch chừng 1–2 điểm có thể chỉ là nhiễu.

## 2. Dịch chữ Nhật đã có sẵn (OCR hoàn hảo, 419 dòng)

| Cấu hình | chrF | Thời gian/dòng (T4) |
|---|---|---|
| Hy-MT2-7B Q6_K, cả trang một lần, các đoạn ngăn bằng dấu phân cách (1/25 trang phải gọi lại từng dòng) | **37,9** | 0,73 s |
| Gemma 4 12B, cả trang một lần, danh sách đánh số | 37,1 | 0,56 s |
| Hy-MT2-7B Q6_K, từng dòng, template ngữ cảnh chính thức | 37,1 | 0,75 s |
| Hy-MT2-7B Q4_K_M, template ngữ cảnh | 36,5 | 0,59 s |
| MiLMMT-46-12B Q4_K_M, từng dòng | 36,1 | 0,77 s |
| Hy-MT2-7B Q4_K_M, từng dòng | 36,0 | 0,51 s |
| Hy-MT2-7B Q8_0, từng dòng | 35,7 | 0,76 s |
| Hy-MT2-7B Q6_K, từng dòng | 35,3 | 0,86 s |
| Gemma 4 E4B, cả trang | 34,4 | 0,24 s |
| TranslateGemma 12B, từng dòng | 30,7 | 0,92 s |
| Qwen3.5 9B, cả trang | 28,9 | 0,45 s |
| Qwen3.5 4B, cả trang | 26,7 | 2,65 s |
| TranslateGemma 4B, từng dòng | 26,3 | 0,26 s |

**Lỗi khi chạy:**
- Hy-MT2-1.8B bị lặp chữ đến mức Ollama phải dừng.
- Seed-X-PPO-7B báo lỗi server 500.

**Đối chiếu với lần đo 19/10 (120 dòng, máy nhóm):** khi kèm ngữ cảnh, Hy-MT2-7B chỉ đạt 26,3 vì prompt tự viết. Dùng đúng template chính thức thì lên **37,1**. Haiku khi ấy dịch chữ thuần đạt 38,7.

## 3. OCR cắt từng ô

| Model | CER, cắt theo hộp nhãn | Đúng cả dòng | CER, cắt theo vùng detector | ms/ô (T4) | Giấy phép |
|---|---|---|---|---|---|
| **Baberu** | **6,3%** | **80%** | **12,9%** | 151 | Apache-2.0, train trên Manga109-s |
| CPT-flex | 8,7% | 74% | 13,5% | 8,4 | CC BY-NC-SA (không thương mại) |
| NAR-small | 8,8% | 75% | 13,5% | 6,8 | CC BY-NC-SA |
| manga-ocr | 9,2% | 71% | 14,1% | 83 | Apache-2.0, train trên Manga109-s |
| PaddleOCR-VL-For-Manga | không nạp được (code của repo lỗi `'default'`) | | | | Apache-2.0 |

**Phần chênh nằm ở đâu** (`tools/eval/src/det-gap.ts`, Baberu, 60 trang, 946 nhãn, tắt CTD):

| Cách detector bao một nhãn | Số nhãn | CER |
|---|---|---|
| Một vùng, không dính bóng khác | 863 (91%) | **7,9%** |
| Bị tách thành nhiều vùng | 13 | 9,6% |
| Bị gộp với bóng khác | 36 (3,8%) | 134% (phần lớn do cách chấm: chữ bóng kia bị tính vào) |
| Bị bỏ sót | 34 (3,6%) | 100% |

**Nhận xét:**
- **Detector là khâu yếu hơn OCR, nhưng chỉ ở 3,6% số bóng bị bỏ sót.** Khi detector bao đúng thì OCR gần bằng lúc cắt theo hộp nhãn.
- **Bật detector thứ hai (CTD) giảm một nửa số bóng bị sót** (`tools/eval/src/det-coverage.ts`, 60 trang, 946 nhãn):

  | | Bị sót | Bị gộp | Thời gian dò/trang |
  |---|---|---|---|
  | Chỉ detector chính | 34 (3,6%) | 36 (3,8%) | 1,10 s |
  | Detector chính + CTD | **18 (1,9%)** | 40 (4,2%) | 1,21 s |

- **CTD được dùng ở gói trả phí:** điều khoản Manga109-s cho dùng thương mại kèm ghi nguồn, nên bảng giấy phép để CTD ở mức "credit". Server vẫn bật CTD khi máy có GPU.
- **Các số đo trong tài liệu này chạy với CTD tắt,** nên sản phẩm thật (CTD bật) sót ít chữ hơn.
- **Số tự công bố cao hơn thực tế:** benchmark của tác giả các model này ghi CER 1,5–5%, nhưng trên nhãn của nhóm là 6–9%. Một phần là vì nhãn của nhóm cũng có lỗi đã biết ([private-ground-truth-audit.md](reference/private-ground-truth-audit.md)).

## 4. Model đọc ảnh chạy local (nguyên trang)

| Model | Vùng dịch được | CER | chrF | Cả trang p50 (T4) |
|---|---|---|---|---|
| Gemma 4 E4B + chữ OCR | 445/481 | 22,8% | **33,6** | **14,2 s** |
| Gemma 4 12B + chữ OCR | 388/481 | 31,1% | 32,1 | 41,1 s |
| Qwen3.5 4B + chữ OCR | 454/481 | **18,4%** | 27,8 | 285 s (4 token/s, quá chậm) |
| Qwen3.5 9B + chữ OCR | 396/481 | 32,3% | 25,6 | 31,7 s |
| Qwen3.5 9B, chỉ ảnh | 393/481 | 45,6% | 23,8 | 32,8 s |
| Gemma 4 12B, chỉ ảnh | 312/481 | 59,7% | 20,2 | 44,3 s |
| Gemma 4 E4B, chỉ ảnh | 388/481 | 63,0% | 16,8 | 16,0 s |
| Qwen3-VL 8B (± chữ OCR) | 88–91/481 | ~80% | ~6 | lỗi ở 15–18/25 trang |

**Nhận xét:**
- **Gửi kèm chữ OCR luôn tốt hơn:** model local nhìn ảnh vẫn chọn được ai nói, nhưng không tự đọc chữ được.

## 5. Chuỗi hai bước: OCR từng vùng detector, rồi model dịch

| OCR → model dịch | chrF | Thời gian dịch/trang (T4) |
|---|---|---|
| CPT-flex → **Gemma 4 12B** (cả trang) | **41,2** | 10,2 s |
| CPT-flex → Hy-MT2-7B Q6 (từng dòng) | 33,3 | 12,2 s |
| CPT-flex → Qwen3.5 9B (cả trang) | 31,6 | 8,0 s |
| CPT-flex → TranslateGemma 12B (từng dòng) | 29,4 | 17,5 s |

## 5b. Fine-tune OCR lần đầu: thất bại, đã tìm ra triệu chứng (22/10)

**Thiết lập:**
- Model gốc `kha-white/manga-ocr-base`, train 2 vòng (5.884 bước, batch 48, lr 5e-5, fp16).
- Dữ liệu: 141 nghìn ô từ Manga109 bản học thuật, gồm cả ô chữ thoại và ô SFX.
- Chạy trên Kaggle T4 (`tools/kaggle/train-ocr.py`).

**Kết quả: loss giảm đều nhưng model đọc kém đi nhiều:**

| Tập chấm | CER trước → sau | Đúng cả dòng trước → sau |
|---|---|---|
| val, chữ thoại | 7,6% → 49,8% | 69% → 2,7% |
| val, SFX | 78,3% → 56,0% | 23% → 17% |
| 25 trang của nhóm | 9,9% → 51,1% | 69% → 4,1% |

**Chẩn đoán** (`tools/kaggle/diag-ocr.py`): model sau train vẫn nhận ra đúng các ký tự nhưng sinh ra sai thứ tự hoặc bỏ sót. Model gốc luôn mở đầu bằng `[CLS]`, còn model sau train thì bỏ token này. Nghi vấn chính có hai:
1. Ô SFX (29% dữ liệu) thường xoay hoặc uốn cong nhưng chỉ được cắt theo hộp bao thẳng, nên thứ tự ký tự trong ảnh không nhất quán.
2. Learning rate quá cao làm hỏng decoder.

**Thí nghiệm tách nghi vấn** (`tools/kaggle/ocr-ablate.py`, 2 GPU, lr 2e-5): cả bản chỉ chữ thoại lẫn bản thêm SFX đều hỏng ngay sau 500 bước (CER chữ thoại từ 8,8% lên khoảng 47%). Vậy nguyên nhân không phải SFX, cũng không phải learning rate.

**Nguyên nhân thật** (`tools/kaggle/debug-train.py`): trong `transformers` 4.57, loss có sẵn của `VisionEncoderDecoderModel` dịch nhãn thêm một vị trí, như loss của mô hình ngôn ngữ thông thường. Model vì thế học đoán token *sau token kế tiếp*.
- **Bằng chứng:** model gốc đoán đúng 95% token khi được mớm đáp án mà loss lại là 14,7.
- **Học thuộc một batch, loss có sẵn:** độ chính xác khi mớm đáp án rơi về 16%, sinh lại đúng 0/16 dòng.
- **Học thuộc một batch, loss tự tính** (logit ở vị trí t so với nhãn ở vị trí t): độ chính xác 100%, sinh lại đúng 11/16 dòng; 5 dòng còn lại dài hơn giới hạn 40 token khi thử.

**Đã sửa ở cả ba script train.** Lượt v2 đang chạy: fine-tune trên 72 bộ Manga109-s, kèm bảng xếp hạng OCR không rò rỉ.

**Bài học cho báo cáo:** loss khi train không đủ để đánh giá OCR. Phải cho model tự sinh chữ trong lúc train, và phải thử học thuộc một batch trước khi chạy dài. Sản phẩm vẫn dùng Baberu chưa fine-tune.

## 5c. Bảng xếp hạng OCR không rò rỉ (22/10, `tools/kaggle/ocr-v2.py`)

**Cách chấm:**
- **"clean":** 22 bộ chỉ có trong Manga109 bản học thuật. Không model nào train trên Manga109-s từng thấy chúng (danh sách: `tools/kaggle/manga109s-titles.json`). Lấy mẫu 3.000 ô chữ thoại và 2.000 ô SFX.
- **"val":** 10 bộ thuộc Manga109-s; các model khác có thể đã train trên đây.
- **"team25":** 25 trang của nhóm, cũng thuộc Manga109-s.
- Mỗi ô ghi CER / tỉ lệ đúng cả dòng. Thời gian đo bằng PyTorch trên T4.

| Model | clean, chữ thoại | clean, SFX | val, chữ thoại | val, SFX | team25 | ms/ô |
|---|---|---|---|---|---|---|
| **Baberu v1.2** (Apache-2.0) | **4,4% / 80%** | 31,4% / 61% | **2,6% / 87%** | 39,1% / 56% | 6,3% / 80% | 167 |
| Hayai v2.5 Nova (Apache-2.0) | 4,6% / 80% | 32,9% / 58% | 2,9% / 87% | 41,1% / 52% | 8,3% / 82% | 13 |
| Hayai v2 (Apache-2.0) | 4,7% / 78% | 32,9% / 60% | 3,1% / 86% | **35,8% / 58%** | 6,4% / 80% | 32 |
| CPT-flex (không thương mại) | 5,3% / 78% | 45,4% / 56% | 5,8% / 76% | 48,7% / 50% | 9,8% / 73% | 9 |
| manga-ocr (Apache-2.0) | 6,2% / 73% | 70,8% / 28% | 6,2% / 71% | 81,7% / 24% | 10,0% / 68% | 120 |
| **Nhóm tự fine-tune:** manga-ocr-base trên 61 bộ Manga109-s, chữ thoại + SFX, 2 vòng (4.938 bước) | 6,5% / 74% | **31,2% / 60%** | 7,5% / 71% | 36,8% / 54% | 10,1% / 70% | 15 |

Trên 25 trang của nhóm, cắt theo hộp nhãn (`eval-ocr.py`):
- **PaddleOCR-VL-For-Manga** đúng cả dòng nhiều nhất (84%, CER 5,1%), và đọc vùng detector tốt nhất (10,6%). Nhưng nó mất **4,4 s mỗi ô**, và SFX sai tới 62%.
- **Hayai v2.5 ở 512 patch:** CER 5,6%.

**Đọc kết quả:**
- **Baberu đọc chữ thoại đúng nhất trên bộ không rò rỉ,** nên giữ làm OCR của sản phẩm. Nó còn có bản ONNX chạy trong server, trình duyệt và điện thoại.
- **Hayai nhanh hơn 5–13 lần** với chất lượng gần bằng, nhưng chỉ có code PyTorch (`trust_remote_code`), chưa có ONNX.
- **Fine-tune của nhóm chạy đúng sau khi sửa loss:**
  - SFX giảm từ 69,7% xuống **31,2%**, ngang Baberu;
  - chữ thoại gần như giữ nguyên;
  - muốn vượt Baberu ở chữ thoại thì nên fine-tune chính Baberu (repo có sẵn `train_ocr.py`), không phải manga-ocr-base.
- **Giấy phép:**
  - model nhóm train trên các bộ Manga109-s được ghi "review" trong bảng giấy phép, vì ảnh cắt lấy từ bản Manga109 học thuật (ảnh giống hệt);
  - cắt lại từ chính bản Manga109-s thì đổi được sang "credit".

## 6. Hướng đề xuất (chờ nhóm chốt)

1. **Cloud chuyển sang "OCR trước":**
   - Server chạy detector và một OCR có giấy phép thương mại (Baberu hoặc manga-ocr: Apache-2.0, train trên Manga109-s, cần ghi nguồn; nên nhờ người hiểu luật xác nhận), rồi gửi chữ cho Haiku.
   - **Còn phải đo trước khi chốt:**
     - độ đúng người nói và xưng hô giữa ba cách gửi;
     - cách "chữ OCR + ảnh trang thu nhỏ 768 px": vẫn nhìn được nhân vật mà rẻ gần bằng chỉ gửi chữ;
     - bỏ phần chép lại chữ Nhật ở đầu ra.
2. **Local:**
   - **Máy 12–16 GB:** detector → OCR → Gemma 4 12B dịch cả trang (chrF 41,2, ~10 s/trang trên T4).
   - **Máy 8 GB:** detector → OCR → Hy-MT2-7B Q6_K dịch cả trang có dấu phân cách, hoặc Gemma 4 E4B kèm ảnh và chữ OCR (14 s/trang) nếu cần biết ai nói.
   - Model đọc ảnh không bao giờ phải tự đọc chữ.
3. **Train OCR riêng:** đang chạy trên Kaggle (`tools/kaggle/train-ocr.py`).
   - Đánh giá trên val, OOS và 25 trang của nhóm.
   - Nhánh học thuật dùng Manga109 đầy đủ, chỉ cho đồ án. Nhánh thương mại chạy lại cùng công thức trên Manga109-s và dữ liệu tổng hợp.
