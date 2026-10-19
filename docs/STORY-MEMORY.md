# Bộ nhớ truyện toàn cục và "P/S nhắc tình tiết" — thiết kế

Cập nhật 19/10/2026. Trạng thái: **đã cài (context v4, prompt `vlm-ja-vi-v4`)**, xem mục 8 (cách cài) và mục 9 (số đo). Mục 2 mô tả context v3 trước đó.

## 1. Mục tiêu

- Tên, xưng hô, thuật ngữ nhất quán suốt bộ truyện; cảnh hồi tưởng vẫn biết chuyện cũ.
- Chi phí và độ trễ mỗi trang **không tăng theo độ dài truyện**: prompt có trần token cố định.
- Không spoil (chỉ dùng điều đã biết trước vị trí đang đọc), mọi dữ kiện có bằng chứng trang/vùng, khóa của người đọc luôn thắng.
- "Tinh tế" như team dịch: khi nhân vật nhắc lại chuyện cũ, có dòng P/S chỉ chương/trang để đọc lại.

## 2. Đã có trong code (context v3)

| Thành phần | Nội dung | Vào prompt |
|---|---|---|
| Thực thể | nhân vật, xưng hô có hướng A→B, thuật ngữ; trạng thái auto/confirmed/locked, bằng chứng, mốc hiệu lực | luôn, chọn theo người đang xuất hiện, trần 1 200 token |
| Thoại gần | các câu vừa đọc (ja, vi, người nói→người nghe) | luôn, trong trần 900 token |
| Kho lưu trữ | mỗi lần cập nhật nền (~24 câu) thêm một bản ghi: đoạn tóm tắt ≤ 60 từ, ≤ 4 sự kiện có bằng chứng; **chỉ ghi thêm, không sửa** | đoạn gần nhất |
| "Truyện tới giờ" | ≤ 120 từ, model nền gộp bản cũ với đoạn mới | luôn |

Điểm yếu: "Truyện tới giờ" là **tóm tắt của tóm tắt** (mỗi lần gộp lại mất chi tiết); sự kiện cũ không bao giờ được lôi ra lại; không có tóm tắt theo chương.

## 3. Thiết kế: bốn tầng, không tóm tắt chồng tóm tắt

| Tầng | Nội dung | Ai viết, khi nào | Vào prompt | Trần |
|---|---|---|---|---|
| L0 Gần đây | K câu thoại gần nhất, nguyên văn | tự động | luôn | ~600 token |
| L1 Thẻ sự kiện | sự kiện, ai tham gia, mức quan trọng 1–3, loại (sự kiện / tiết lộ / đổi quan hệ / lời hứa / hồi tưởng), từ khóa ja+vi, bằng chứng trang/vùng | model rẻ chạy nền, mỗi ~24 câu | **chỉ khi được gọi lại** (mục 4) | ≤ 400 token |
| L2 Tóm tắt chương | dựng từ thẻ L1 của chính chương đó | khi hết chương | chương liền trước | ≤ 150 token |
| L3 Toàn truyện | dựng lại từ các L2, **không** từ L3 cũ | khi có chương mới | luôn | ≤ 200 token |
| Thực thể | như hiện có | | luôn | ≤ 1 200 token |

Ba nguyên tắc chống mất dữ kiện:

1. Dữ kiện quan trọng nhất (tên, xưng hô, quan hệ, thuật ngữ) nằm trong **bảng có cấu trúc**, không bao giờ bị tóm tắt; chỉ được chọn lọc theo nhân vật đang xuất hiện.
2. Thẻ L1 là bản gốc chỉ-ghi-thêm, giữ vĩnh viễn và có bằng chứng. Mỗi tầng trên chỉ tóm tắt **một cấp** từ tầng ngay dưới và luôn dựng lại từ nguồn — lỗi không cộng dồn qua nhiều vòng.
3. Trần cố định ≈ 2 500 token context mỗi trang dù truyện 10 hay 500 chương: chi phí và độ trễ phẳng. Phần lớn lịch sử nằm ngoài prompt, chỉ được gọi khi cần.

## 4. Model tự quyết khi nào cần nhớ lại

- Thoại thường ngày: chỉ L0 + thực thể + L3 (rẻ, nhanh).
- Khi một câu nhắc chuyện cũ (あの時, 約束, 前に, "còn nhớ không…", khung hồi tưởng viền đen/mờ), model đọc trang trả thêm một dòng, ví dụ
  `{"recall":{"regions":["r7"],"who":["Nana"],"keys":["約束","lễ hội"]}}`.
- Server truy hồi thẻ L1 **trước vị trí đang đọc** theo nhân vật + từ khóa + mức quan trọng. Có thẻ khớp thì chạy **một lượt sửa nhỏ chỉ cho các vùng đó** (giống lượt sửa ID hiện có) kèm thẻ, cập nhật bản dịch và tạo P/S. Chỉ tốn thêm ở trang cần (ước tính 5–10% số trang; phải đo).
- Hỏi đáp trong khung chat ("chuyện X là gì?", "Tóm tắt đến đây"): cùng bộ truy hồi, trả lời có trích chương/trang, không vượt vị trí đang đọc.
- Sau này: truy hồi theo nghĩa bằng một model embedding nhỏ chạy trên máy khi từ khóa không đủ.

## 5. P/S nhắc tình tiết

- Nguồn: chỉ thẻ L1 có bằng chứng ở chương/trang **trước** vị trí đang đọc. Ví dụ: "P/S: lời hứa ở lễ hội — chương 3, trang 12."
- Vị trí: tìm dải trống giữa các khung tranh (gutter, trắng hoặc đen) bằng hồ sơ chiếu theo hàng/cột, chọn dải gần bóng thoại nhắc chuyện cũ và đủ chỗ. Không có chỗ thì hiện một chấm nhỏ bấm để xem — không bao giờ đè lên tranh.
- Cài đặt: Tắt / Kín đáo (chấm bấm xem, mặc định) / Hiện. "Xem bản gốc" ẩn toàn bộ P/S.

## 6. Điểm ngọt (sweet spot): đo, không đoán

- Biến số: K câu ở L0 ∈ {0, 10, 20, 40, 80}; số câu mỗi thẻ L1 (hiện 24); độ dài L3.
- Dữ liệu: các truyện có trang liên tiếp trong bộ của nhóm (set1) và 10 trang GT, đọc tuần tự.
- Số đo: chrF với bản dịch chuẩn của nhóm, lỗi xưng hô/người nói (tự chấm), token vào, thời gian tới bóng đầu, $/trang.
- Chọn K **nhỏ nhất** đạt ≥ 98% chất lượng của K lớn nhất. Chi phí thử ước tính ~$0,2 (Haiku, 5 cấu hình × ~40 trang).

## 7. Thứ tự cài đặt

1. Mở rộng sự kiện L1: `who`, `importance`, `kind`, `keys`; prompt cập nhật nền trả các trường này (tương thích dữ liệu cũ).
2. Tóm tắt chương L2, dựng L3 từ L2; bỏ việc gộp "truyện tới giờ" nối tiếp.
3. `recallEvents(memory, vị trí, truy vấn)` trong `packages/core` (thuần, có test chống spoil).
4. Trường `recall` trong prompt đọc trang (v4) + lượt sửa có thẻ; đo tỉ lệ kích hoạt và chi phí.
5. `findGutters(ảnh)` + vẽ P/S trong renderer + cài đặt.
6. Thí nghiệm điểm ngọt, chốt K.

Cả 6 bước đã cài ngày 19/10/2026 (mục 8, 9).

## 8. Đã cài (context v4)

| Phần | Ở đâu | Ghi chú |
|---|---|---|
| Thẻ L1 | `StoryEvent` trong `packages/core/src/memory.ts` | thêm `who[]`, `importance` 1–3, `kind` (event/reveal/relationship/promise/flashback), `keys[]` ja+vi; trường sai kiểu bị bỏ; thẻ v3 (chỉ có text/pos/evidence) vẫn đọc được và vẫn được gọi lại theo chữ |
| Cập nhật nền | `UPDATE_SYSTEM` trong `apps/server/src/context.ts` | không còn `story_so_far`: model nền chỉ viết đoạn mới + thẻ; "truyện tới giờ" cũ của bộ nhớ v3 vẫn hiện (không gộp tiếp) cho tới khi có L3 |
| L2 tóm tắt chương | `chapterDigestsDue`, `digestInput`, `makeDigest` | chỉ từ thẻ của chính chương đó; chương đã qua (người đọc sang chương sau) được tóm lại khi thiếu thẻ; chương đang đọc được tóm sau > 3 đoạn và mỗi ≥ 6 thẻ mới (để đầu chương không mất khi "diễn biến mới nhất" chỉ giữ 3 đoạn); tối đa 3 lần gọi mỗi lần cập nhật |
| Cung (arc) | `arcDigestsDue` | truyện dài: mỗi 10 chương đã qua thành một bản tóm từ 10 L2, để đầu vào L3 tăng chậm (500 chương ≈ 50 cung + ≤ 10 chương) |
| L3 toàn truyện | `overviewSources`, `makeOverview`, `mem.overviews` | dựng lại từ các L2/cung của chương đã qua, **không bao giờ** từ L3 cũ; giữ một bản mỗi chương, nên đọc lại chương 5 thấy L3 như lúc hết chương 4 |
| Prompt mỗi trang | `volatileContext` | trần cố định `MEMORY_BUDGET` = 1 200 (bền) + 900 (động) token, tính cả tiêu đề mục: L3 ≤ 200, L2 ≤ 150 (chương đang đọc, nếu chưa có thì chương trước), L0 = K câu gần nhất (mặc định K=10, mục 9) ≤ 600, phần còn lại cho các đoạn mới chưa tóm; bộ nhớ chỉ lưu tối đa 80 câu L0 |
| Gọi lại L1 | `recallEvents(mem, vị trí, {who, keys, text}, max)`, `recallContext` | thuần; loại mọi thẻ có vị trí hoặc **bất kỳ** bằng chứng nào sau vị trí đọc, và thẻ bắt đầu ở chính trang đang đọc; máy chủ chỉ gọi lại sự kiện cách ≥ `RECALL_MIN_PAGES` (5) trang trong cùng chương (chương trước luôn được, xem mục 9); có từ khóa thì bắt buộc khớp ít nhất một (từ khóa của thẻ nằm trong câu thoại cũng tính); xếp theo người + từ khóa, rồi mức quan trọng, rồi độ mới; trần 400 token |
| Prompt v4 | `SYSTEM_PROMPT`, `parseNotesObject` | dòng notes có thể thêm `"recall":{"regions":[…],"who":[…],"keys":[…]}`; recall/ps sai dạng bị bỏ mà không mất names/address |
| Lượt sửa có thẻ | `recallPass` trong `apps/server/src/pipeline.ts`, `RECALL_SYSTEM` | chỉ chạy khi có thẻ khớp; chỉ gửi chữ (không ảnh): các câu của trang, id cần sửa, thẻ c1…; chỉ thay bản dịch tiếng Việt (giữ ja, vai trò); P/S chỉ từ thẻ model **trích** (`ps`), chỉ chương/trang nơi sự kiện bắt đầu |
| Khe tranh | `findGutters` trong `packages/core/src/gutters.ts` | cắt XY đệ quy 3 tầng theo hồ sơ chiếu hàng/cột; dải trắng hoặc đen; chấm lẻ được bỏ qua, nét ≥ 2 px (viền khung) cắt dải; dải dày > 8% trang mà không chạm mép trang bị loại (khung trống, bầu trời) |
| Vẽ P/S | `placeNotes`, `drawNotes` trong `packages/render/src/notes.ts` | đặt trong khe gần bóng thoại nhất (≤ 25% chiều cao trang), không đè vùng chữ nào; không có chỗ thì thành chấm bấm xem |
| Cài đặt demo | `apps/demo/src/App.tsx` | "P/S nhắc chuyện cũ": Tắt / Kín đáo (chấm, mặc định) / Hiện trong khe tranh; "Xem bản gốc" ẩn hết; tab Số đo ghi vùng recall, số thẻ, câu được sửa, chi phí |

Chưa làm: tự cập nhật nền ngay khi sang chương mới (hiện L2 của chương vừa xong có sau khi đủ 24 câu ở chương mới, vì nút gọi nằm trong `apps/server/src/app.ts`); hỏi đáp trong khung chat; truy hồi theo nghĩa bằng embedding.

## 9. Số đo: điểm ngọt K (19/10/2026)

Điều kiện: đọc tuần tự 60 trang (10 trang GT local + 50 trang set1; 7 truyện, tất cả ở chương 1), mỗi K một bộ nhớ riêng, cập nhật nền như máy chủ (mỗi 24 câu). Dịch trang: `anthropic/claude-haiku-5.5`; cập nhật nền và giám khảo: `deepseek/deepseek-v4.1-flash-1017`. **Một lượt** mỗi K, không cache kết quả, detector đã nóng. 6 truyện chạy song song, các K xen kẽ từng trang (đổi thứ tự mỗi trang), nên độ trễ chỉ để so giữa các K, không phải độ trễ một người đọc. Lượt chạy này dùng prompt v4 với recall **chưa có** ngưỡng khoảng cách (xem dưới). Chi phí: $0,50 theo sổ chi phí (dịch $0,371, lượt recall $0,029, cập nhật nền + tóm tắt chương $0,093, sửa ID $0,002, giám khảo $0,008); ước tính ban đầu $0,2 vì đếm 40 trang và chưa tính recall/cập nhật nền.

| K | Trang | chrF so với bản dịch nhóm | Δ chrF so với K=80 [KTC 95%, bootstrap theo trang] | Lỗi xưng hô / người nói (giám khảo, 51 trang) | Lệch đại từ so với bản nhóm (tự động) | Token vào/trang | Token thoại gần (L0+) | Bóng đầu p50 | $/trang (dịch + recall) | $/trang nền |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 60 | 37,27 | −0,71 [−1,78; 0,29] | 16 / 9 | 55,1% | 7 485 | 155 | 11,5 s | $0,00145 | $0,00031 |
| 10 | 60 | 37,34 | −0,64 [−1,62; 0,33] | 13 / 7 | 57,3% | 7 781 | 396 | 11,3 s | $0,00143 | $0,00032 |
| 20 | 60 | **38,15** | +0,16 [−0,73; 1,15] | 15 / 9 | 52,4% | 8 007 | 606 | 10,1 s | $0,00149 | $0,00028 |
| 40 | 59* | 37,88 | −0,10 [−1,40; 0,95] | **12 / 7** | 48,3% | 8 341 | 973 | 10,0 s | $0,00150 | $0,00031 |
| 80 | 60 | 37,98 | — | 14 / 7 | 58,4% | 9 456 | 1 557 | 11,1 s | $0,00161 | $0,00030 |

\* một trang lỗi mạng ở K=40. "Lệch đại từ (tự động)": tỉ lệ dòng mà bản nhóm có đại từ nhân xưng nhưng bản máy không dùng chung đại từ nào (≈ 267 dòng); thô, chỉ để so giữa các K. Giám khảo thấy 5 bản cạnh nhau, nhãn chữ cái xáo trộn, không biết K; chỉ chấm trang có đủ 5 bản.

Kết luận:

- **Không K nào tách được khỏi K=80**: mọi khoảng tin cậy chứa 0, số lỗi giám khảo chênh 3–4 trên 51 trang, độ trễ không theo xu hướng. Truyện trong bộ thử chỉ dài 10 trang, nên K lớn gần như chứa hết những gì đã đọc.
- Quy tắc "K nhỏ nhất đạt ≥ 98% chất lượng của K lớn nhất" theo chrF cho phép cả K=0 (98,1%), nhưng K=0 có nhiều lỗi xưng hô nhất (16). **Chọn K=10** (`RECENT_LINES`): 98,3% chrF của K=80, lỗi gần mức tốt nhất (13/7), ~400 token, vừa trần L0 600. Mỗi 10 câu thêm tốn ~+$0,00003/trang. Cần thêm trang/lượt (hoặc truyện nhiều chương) mới phân biệt được K=0 với K≥10.
- **Recall**: model hỏi lại ở 34–39/60 trang; có thẻ khớp ở 12–18 trang; lượt sửa chữ tốn ~$0,0001/trang trung bình (7–9% giá trang), p50 ~2 s. P/S đúng chủ đề (trỏ vào sự kiện thật đã đọc) nhưng **82% chỉ cách 1–3 trang** — vô ích với người đọc. Vì vậy thêm `RECALL_MIN_PAGES = 5`: cùng chương phải cách ≥ 5 trang (chương trước luôn được). Chạy lại các yêu cầu đã lưu (không gọi API): lượt recall chỉ còn 0–5/60 trang mỗi K (≤ 8%), khớp mức 5–10% dự kiến, ví dụ trang 8–9 của Uchi no Nyan's Diary nhắc lời Norabosu tuyên bố ở trang 3.
- **Vị trí P/S** (chạy lại offline trên 98 P/S của lượt thử): 35 chữ được đặt trong khe tranh (cỡ 10–16 px trên trang đôi 1654×1170), 63 thành chấm vì khe gần nhất quá mỏng (thường 12–16 px) hoặc xa hơn 25% chiều cao trang. `findGutters` ~100 ms mỗi trang đôi (Node, CPU).
- **Kiểm tra trên trình duyệt** (demo, dịch tuần tự 10 trang set1 Uchi no Nyan's Diary với K=10 và ngưỡng 5 trang, ~$0,02): model hỏi lại ở 7 trang nhưng **không P/S nào hiện**, đúng luật: trang 3–6 chưa có thẻ cách ≥ 5 trang khớp; trang 7–9 tra "ノラトラ / Nora-tora / 注射 / Tora" trong khi thẻ trang 2–3 ghi "ノラボス / Nora-boss", không trùng từ khóa nào. Đây là một lần bỏ sót thật (cùng một con mèo hay không thì cần người đọc xác nhận); truy hồi theo nghĩa hoặc bí danh trong bảng thực thể sẽ bắt được. Phần vẽ được kiểm bằng kết quả K=20 của chính các trang đó (P/S trang 8 và 9 trỏ về trang 3, cách 5–6 trang): chế độ Kín đáo hiện chấm "P/S" ở góc bóng thoại, bấm mở ghi chú, khung soi bóng thoại cũng hiện; chế độ Hiện đặt chữ vào khe trắng (vùng đặt chữ trên ảnh gốc có 0 điểm ảnh tối, tức không đè tranh), trang 9 không có khe đủ dày nên vẫn là chấm; "Xem bản gốc" xóa cả chữ lẫn chấm.
- Chưa đo trên truyện nhiều chương: L2 chương đã qua, cung và L3 chỉ được kiểm bằng unit test; dữ liệu có hết ở chương 1.

Tái lập: `npx tsx tools/eval/src/recall-k.ts --run recall-k --k 0,10,20,40,80 --sets local,set1 --cap 0.6 --judge deepseek/deepseek-v4.1-flash-1017` (chấm lại không tốn tiền: thêm `--score-only`). Kết quả riêng tư trong `.private/eval/recall-k*/`.

## 10. Chỉnh sau khi rà soát (19/10/2026, khuya)

- **P/S rất hiếm**, đúng như các nhóm dịch làm: chỉ hiện khi sự kiện **cách ≥ 20 chương** (`PS_MIN_CHAPTERS`) và quan trọng (importance ≥ 2), **tối đa 1 P/S mỗi trang**. Người đọc không quên chuyện vài trang trước. Bộ thử hiện có toàn chương 1 nên sẽ không thấy P/S nào; cần truyện nhiều chương để kiểm.
- **Lượt nhớ lại** chỉ dùng thẻ của **chương trước** (`RECALL_MIN_CHAPTERS = 1`): chương đang đọc đã có sẵn trong prompt (tóm tắt chương + thoại gần). Lượt này **chỉ được đổi phần tiếng Việt**; người nói/người nghe giữ nguyên như đọc từ ảnh.
- **So khớp tên qua bảng nhân vật** (`nameForms`): tên Nhật, tên Việt, tên chính thức và các cách dịch cũ của cùng một mục được coi là một; hai mục khác nhau không bao giờ bị gộp.
- **Câu hướng dẫn `recall`** viết lại theo hướng "hiếm". Trên ca thật Uchi no Nyan's Diary (10 trang, một lượt mỗi bản): bản thắt chặt 1/10 trang hỏi; bản gốc 5/10 trang hỏi, 1 trang tìm được thẻ. Cả hai không ra P/S (đúng luật mới). Chi phí mỗi lượt ~$0,02.
- **Prompt v3 với v4** trên 10 trang GT (Haiku, 2 lượt mỗi bản, chạy song song): v4 chrF 23,3 so với 21,5, CER 26,0% so với 28,9%, bóng đầu p50 8,0 so với 7,8 s, token ra +1%, cùng $0,00094/trang. Không thấy v4 kém đi; khác biệt nằm trong độ dao động của 20 lượt trang.
