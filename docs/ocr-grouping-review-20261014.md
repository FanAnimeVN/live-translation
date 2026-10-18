# Gom vùng OCR và lỗi “Chị nee-chan” — 2026-10-14

## Kết luận thực thi

- Prompt/guard `ja-vi-v22-directed-wait-no-stack`: `nee-chan`, không “chị nee-chan”; `onii-chan`, không “anh trai onii-chan”; bổ sung `姉さん=nee-san`, `兄さん=nii-san` cùng quy tắc và guard hẹp để không đảo vai trong câu `待ってる`. Chặn cả lời gọi đứng riêng khi OCR không có dấu câu. Không xóa đại từ hợp lệ ở mệnh đề sau, không đổi mô tả quan hệ trong lời dẫn, không ghi đè ngoại lệ reader khóa. Số đo cloud/browser v20 bên dưới là lịch sử, chưa thử inference v22 trên Edge cá nhân.
- Layout mặc định `balloon-mask-v16-outer-notch-veto` giữ grouping ổn định và thêm merge veto từ điểm lõm viền ngoài. Cách gom chữ mở v13/v14 từng bị từ chối vẫn chỉ có trong harness opt-in, không bật trong companion; không đổi ảnh/gold để lấy điểm đẹp.
- Chưa promote frozen companion hay registry Edge cá nhân. Build extension thành công không chứng minh native host cũ đã có guard mới.

## Vòng chẩn đoán và kết quả thật

Lỗi lời gọi thiếu dấu câu đã tái hiện bằng `pytest tests/python/test_linguistics.py -q`: ba ca `姉ちゃん`, `お兄ちゃん`, `「姉ちゃん」` không bắt được title dư. Sửa tại `explicit_address`; ca tốt, reader lock và lời dẫn không bị sửa cơ học. Cloud seam chỉ repair ID lỗi tối đa một lần; lỗi vẫn còn thì không đưa ra overlay. Prompt version mới làm mất hiệu lực cache dịch cũ, không cần xóa context reader.

Gom vùng thử nghiệm có unit test xanh nhưng không đủ bằng chứng. Replay polygon thật đi qua chính `group_regions`, không load model và không dùng text/gold để quyết định nhóm. Các regression được tái hiện trước khi sửa: hai khối giới thiệu gộp thành một; caption/logo bị nối qua chú thích nhỏ; nhãn chữ tay nuốt crop bên cạnh; nét trong detector overlap bị coi là viền riêng.

| Cấu hình | Alignment / 78 | CER chẩn đoán | Exact / 78 | Vùng / patch |
|---|---:|---:|---:|---:|
| Baseline v12 | 62 | 29,82% | 33 | 131 / 63 |
| Thử nghiệm v13 | 57 | 32,91% | 31 | 111 / 34 |
| Thu hẹp v14 | 61 | 29,71% | 33 | 115 / 37 |
| Mặc định v15 | 62 | 29,82% | 33 | 131 / 63 |
| Mặc định source v16 | 62 | 29,18% | 34 | 132 / 62 |

v14 sửa chính xác câu hai cột ở MN109-08 b02, nhưng các vùng khác mất/đổi ký tự và alignment giảm. Không chấp nhận làm mặc định. v15 rerun thật có toàn bộ text/bbox vùng giống v12; dataset fingerprint vẫn `445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`. Alignment là containment chẩn đoán, không phải detector recall/precision hoặc điểm dịch. Gold Nhật chưa rà độc lập; không có bản Việt gold hợp lệ hoặc clean-background gold.

### Overmerge viền cong: đã sửa một trường hợp thật, chưa phải segmentation hoàn chỉnh

Lệnh red đã chạy với source v15:

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/probe_grouping_replay.py --folder 'C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001' --page MN109-07 --box 370 700 160 205 --expect-regions 2
```

Trước sửa: 5 cột → 1 crop `[377,709,144,189]`, lệnh thất bại. Sau v16: 2 crop `[422,709,99,189]`, `[377,714,37,117]`, lệnh qua. Numeric probe `scripts/probe_surface_necks.py` kiểm tra đúng component production trong RAM: diện tích 24.544 px, box 166×202; điểm lõm ngoài `[408,829]`, sâu 25,69 px. Không có viền thẳng giữa hai cột; ngưỡng gap đơn thuần không đủ.

`companion/manga_live/layout_geometry.py` chỉ lấy convexity defect ngoài, hướng/cỡ chữ và mốc kết thúc của hai khối. Nền phải có giới hạn, mật độ ≥60%; ≥80% detections cùng hướng; notch sâu ≥max(12 px, 0,75×cỡ chữ). Có gap thật 0,2–1×cỡ chữ, không cắt qua giữa detector crop; khối ngắn kết thúc gần notch và khối dài tiếp ≥1,5×cỡ chữ. Đây là merge veto, không phải suy speaker, segmentation pixels hoặc giấy phép xóa cả component. Split luôn giữ crop, review và không có balloon ownership.

Full-page OCR thật: b04 không còn nuốt câu bên cạnh, 6→0 edit; b05 cũng đọc riêng đúng `難しいかな`. Tuy nhiên bbox gold b05 chỉ 20×97, containment của prediction có padding là 44,8%; gate 50% vẫn không gán nó. Không sửa bbox/nới alignment hoặc cộng điểm b05 để báo cáo đẹp. Bảy trang còn lại có toàn bộ bbox/text/overlay/review giống v15; chỉ b04 thay prediction trong bảng annotation. Tổng CER 29,18%, exact 34/78, perfect vẫn FAIL, nguồn không đổi. Một patch ít hơn vì fragment mới giữ source thay vì cleanup không chắc.

14 test mới bảo vệ nền sáng/tối, chữ dọc/ngang, resize 0,5/1,5/2×, điểm lõm nông, đuôi dưới toàn bộ chữ, thiếu gap và crop vượt biên. Test tắt riêng `paper_notch_cuts` tái hiện lại overmerge; không chữa bằng text/gold. Fixture ban đầu có notch nông/chiếm quá 12% trang không cùng điều kiện với nguồn; đã tách thành negative và đặt canvas đúng nhánh bounded, không nới production threshold để chạy xanh. Toàn Python 508 qua/1 skip, TypeScript 29 qua, typecheck/build qua. Probe chỉ xuất số liệu hình học, không lưu raster hoặc reader context; benchmark OCR giữ báo cáo text riêng trong `artifacts/` như đã công bố.

Lệnh tái hiện candidate:

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/probe_grouping_replay.py --folder 'C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001' --page MN109-08 --box 280 60 70 180 --experimental-open-text --expect-regions 1
.\.venv\Scripts\python.exe -X utf8 -B scripts/benchmark_pages.py --folder 'C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001' --experimental-open-text --output artifacts/private-pages-open-candidate.json
```

Không có cờ thì dùng layout mặc định. Cờ mở hiện chạy trên nền v16 và báo `balloon-mask-v16-open-text-experiment`; các số đo v13/v14 phía trên là kết quả lịch sử, không điểm của cấu hình mới. Candidate không được ghép với resize/đổi detector để tránh trộn biến số. Ảnh/crop/patch chỉ RAM; chi tiết text riêng nằm ở `artifacts/` đã gitignore, không vào bundle.

## Pilot cloud hẹp, không chứng nhận dịch manga

Thoại tự viết: đoạn chị–em ba bóng và hai lời gọi đứng riêng. Hai model cùng prompt v20, thinking tắt, route latency, reservation tổng tối đa USD 0,03; bốn request thực tế, không repair.

| Model | Các guard qua | Hai thời gian request | Reported cost |
|---|---|---|---:|
| DeepSeek V4.1 Flash | 2/2 nhóm | 1,75 s; 0,94 s | USD 0,000808476 |
| Qwen3.8 Flash | 2/2 nhóm | 2,64 s; 2,08 s | USD 0,000452618 |

Lời gọi trả `nee-chan` và `onii-chan` không thêm title. Câu như “Nee-chan, chị chưa về à?” vẫn được phép: “chị” là chủ ngữ ở mệnh đề sau, không phải title ghép trước `nee-chan`. Guard khớp vài lỗi đã biết, không phải chấm toàn nghĩa/ngữ pháp. Chưa có so sánh mù, dataset đại diện, provider-pinned A/B hoặc p95; không đổi model mặc định từ bốn request. Không gửi private text/ảnh.

## QA giao diện

Luồng: localhost reader tự tạo → bật dịch → mở chi tiết OCR → xem ghi chú → cuộn/resize → sửa tên/OCR, xem gốc, retry và chuyển chapter.

- Môi trường: Edge headless riêng, `http://127.0.0.1:58093/chapter/1`; 1280×900, 760×800, 390×844. Browser plugin not available; dùng workflow Playwright có sẵn, không điều khiển Edge cá nhân.
- URL/title, nội dung không trắng, không framework overlay, console không lỗi liên quan: PASS.
- Sai lệch tọa độ sau cuộn/nested scroll/contain/cover <2 CSS px; review note gom/tách vùng hiển thị; sửa tên không chặn đọc; retry không lặp hoặc nhận kết quả stale: PASS.
- Desktop/mobile screenshot đã xem. Note mobile đọc được, control không bị cắt. Fixture transport/OCR/dịch giả lập; các rectangle fallback không chứng minh lettering integrated trên manga thật.
- Bằng chứng ở `C:\Users\Huy\AppData\Local\Temp\mangalive-ui-qa-91ef1587956a42bfb59f7238680369b0` (`desktop-overlay.png`, `ocr-layout-review-mobile.png` và các trạng thái khác). Không có screenshot private.
- Lệnh: `npm run check`, `npm run test:ui`, `python -m pytest tests/python -q`. Các kết quả UI này không thay thử inference browser/native hoặc Windows sạch.

Rerun UI sau v16: `http://127.0.0.1:52664/chapter/1`, cùng ba viewport và các kiểm tra/interaction ở trên đều qua. Đã xem screenshot mobile ghi chú OCR và overflow detail, control đọc được; vẫn là transport/OCR/dịch mock, không bằng chứng segmentation mới trên browser. Bằng chứng mới ở `C:\Users\Huy\AppData\Local\Temp\mangalive-v16-ui-da86efaac5c448af8c0cd802689188b4`. Không portable promotion hoặc screenshot private.

### Kiểm thử luồng inference thật với source mới

`node scripts/browser-pipeline-smoke.mjs --direct-source --cloud-test --cloud-model deepseek/deepseek-v4.1-flash --cloud-budget 0.03 --wait-ms 120000` đã qua. Native handshake xác nhận prompt v20/layout v16, không dùng host cũ. Luồng Edge → PP detector → manga-ocr → DeepSeek → bốn bóng integrated là thật, trên **trang tự tạo**, không gửi private text/ảnh. URL `http://127.0.0.1:64944/chapter/1`, 1280×900 và 390×844; đúng identity, không trắng/framework overlay/console error, scroll lệch <2 px, mobile không tràn, stop/warm/cache qua. Mask lấy màu/glyph geometry của nguồn, khóa reader `Kết Giới Băng Giá` được giữ; screenshot đã xem ở `C:\Users\Huy\AppData\Local\Temp\mangalive-real-browser-j4RiCZ\evidence`.

Cold toàn browser 31,04 s, native 30,36 s; warm page ID mới 5,65 s, native 5,08 s; cache 585 ms, native 4,27 ms, 0 token/request cloud mới. Hai cloud request 1,52 s và 1,23 s, reported cost USD 0,000805416; reservation USD 0,0070884 trong trần USD 0,03. Không percentile hoặc chứng nhận tốc độ manga thật. OCR vẫn tự thêm `「` ở hai câu; không strip để che lỗi. Source permission QA chỉ localhost, không proof UX activeTab thật. Host QA ngẫu nhiên đã gỡ và xác minh không còn registry; host cá nhân giữ nguyên. Frozen companion/Windows sạch vẫn chưa được nghiệm thu, segmentation mới trên manga thật ở browser chưa thử.

## Lỗi còn phải xử lý

Trường hợp MN109-07 đã tách đúng trong OCR thật; chưa giải quyết mọi bóng chồng/nối nhau hoặc cấp lại erasure cho hai phần. Các cột trên nền mở vẫn có thể bị đọc lặp ở mặc định, và detector còn bỏ/chia sai chữ. Cổng perfect vẫn FAIL; không mở rộng dataset hay tuyên bố chất lượng hoàn hảo. Bước tiếp là grouping/layout đáng tin hơn và lettering có bằng chứng, rà annotation độc lập, rồi mới chấm dịch thực và tối ưu latency.

## Đối chứng cột có cùng mốc bắt đầu — chưa promote

Candidate `balloon-mask-v17-aligned-open-text-experiment` thêm mốc đầu cột/dòng cùng một dải nhỏ và kiểm tra mọi thành viên trong cụm, tránh nối bắc cầu qua các khối lệch dòng. Hai regression staggered/transitive và một trường hợp hai hàng xóm thêm cùng lúc đều đã đỏ trước sửa. 60 test grouping/boundary qua; mặc định vẫn `balloon-mask-v16-outer-notch-veto`, không thêm setting hay quyền xóa tranh.

Replay thật MN109-08, vùng `[280,60,70,180]`: default 2 crop (lệnh `--expect-regions 1` đỏ); candidate 1 crop `[283,65,62,170]`, giữ toàn bộ detector columns và `layout_cluster`, không có balloon erasure. Full-page local đủ 8 trang/78 nhãn, cùng fingerprint và weights:

| Chỉ số | Default v16 | Candidate aligned-open |
|---|---:|---:|
| Alignment chẩn đoán | 62/78 | 62/78 |
| Exact theo gold chưa rà | 34/78 | 34/78 |
| Edit / 939 ký tự | 274 | 272 |
| CER chẩn đoán | 29,18% | 28,97% |
| Vùng OCR / bóng phẳng / patch | 132 / 8 / 62 | 118 / 8 / 38 |

MN109-08 b02 giảm 5→0 edit; MN109-02 b12 3→4 (mất một ký tự), MN109-04 b13 6→7 (vẫn sai dấu/thứ tự). MN109-06 b03 0→1 theo gold nhưng đã xem ảnh: khả năng nhãn `手ぶ` ghi nhầm `呼ぶ`. Đề nghị rà riêng được thêm vào `artifacts/private-label-review-proposals-20261014.json`, **pending**, không sửa gold hoặc cộng lại điểm. Số patch giảm vì cluster không được cleanup tự động; CER thấp hơn một ít không chứng minh nghĩa/lettering tốt hơn toàn bộ.

**Không promote**: vẫn còn regression thật và chưa cải thiện exact tổng. Audit `--audit-only --assert-perfect` vẫn FAIL, fingerprint nguồn giữ nguyên; không dùng một câu exact làm chứng nhận. Artifacts riêng: `private-pages-20261014-v17-aligned-candidate.json`, `private-gate-audit-20261014-v17-candidate.json`; không cloud hoặc thay host Edge. Toàn Python sau candidate 635 qua/1 skip; TypeScript 30/typecheck/build qua. Chưa đo percentile hoặc chấm dịch Nhật–Việt từ lần OCR này.

Rerun default đầy đủ sau khi thêm candidate: `artifacts/private-pages-20261014-v16-post-candidate.json`. Đã đối chiếu từng trang: **8/8 trang, toàn bộ 132 region (bbox/text/order/overlay/review/scope), alignment và danh sách patch giống baseline v16**; fingerprint không đổi. Không dựa vào test đơn lẻ để khẳng định default không bị thay. Số thời gian khác do runtime, không phải bằng chứng cải thiện độ trễ.

Tái lập:

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/probe_grouping_replay.py --folder 'C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001' --page MN109-08 --box 280 60 70 180 --experimental-open-text --expect-regions 1
.\.venv\Scripts\python.exe -X utf8 -B scripts/benchmark_pages.py --folder 'C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001' --experimental-open-text --output artifacts/private-pages-20261014-v17-aligned-candidate.json
```

## Guide v2 — OCR union thật sau khi reader cho phép chạy thiếu RAM

Không đưa ZIP của agent khác vào runtime. Candidate riêng `pp-overlapping-crops-comic-block-guide-v2-parallel-band-candidate` thêm ba giới hạn vào guide v1: cùng hướng viết, cỡ ngang tương thích và mốc đầu cột/dòng pairwise. Cụm từ ba thành viên kiểm tra pitch để crop gần trùng không nối vào cột thứ ba. Đã có test đỏ trước sửa cho dòng ngắn nối paragraph, cột lệch mốc đầu và hướng ngang/dọc trộn; thêm regression giữ member, chống drift/bắc cầu và không cấp erasure/memory.

Thực hiện đúng xác nhận reader: CPU 4 threads, model local, **10 crop union OCR fresh**, không crash. Detector dùng hai report ghi nhận thật trước đó, không detector inference mới. Đối chiếu 108 crop không đổi theo ID/bbox/order/ja/overlay/review; giữ nguyên fingerprint, không dùng gold/text để chọn crop, không sửa reader source bindings hoặc promote default.

| Chỉ số | Baseline PP v16 | Guide v1 | Guide v2 |
|---|---:|---:|---:|
| Vùng | 132 | 110 | 118 |
| Alignment / 78 | 62 | 59 | 62 |
| Exact / 78 | 34 | 33 | 34 |
| Edit / 939 ký tự | 274 | 271 | 271 |
| CER chẩn đoán | 29,18% | 28,86% | 28,86% |
| Nhãn giảm/tăng/không đổi edit so baseline | — | 5 / 5 / 68 | 1 / 2 / 75 |

Đối chiếu toàn bộ nhãn, không chỉ trung bình:

- MN109-08 b02: 5→0 edit; không còn lặp phần câu do crop cột chồng nhau.
- MN109-02 b12: 3→4 edit; union làm mất một ký tự thật, thấy rõ trên ảnh. **Regression chưa giải quyết.**
- MN109-06 b03: 0→1 edit theo gold; đã xem ảnh, đề xuất rà nhãn cũ vẫn pending. Không tự thay gold hoặc rescore.
- MN109-04 b13: 6→6 edit nhưng dấu câu/vị trí pause thay đổi. Số edit bằng nhau không chứng minh chất lượng bằng nhau; vẫn có vùng chưa gom chắc.
- Bốn trang không có union giữ mọi crop; title/furigana/art overmerge của guide v1 đã bị veto, nhưng cách ghép còn là giả thuyết review, không balloon/glyph mask hoặc plot evidence.

**Quyết định: chưa promote.** Không hạ cổng perfect, không bỏ nguồn punctuation hoặc thu font để che lỗi. V1 và v2 cùng CER nhưng coverage và loại lỗi khác; chưa có Việt/clean-background gold hợp lệ, role labels hoặc kiểm thử đủ rộng để tuyên bố manga-perfect.

Lượt cold (trang union đầu): 52,81 s gồm import/load, OCR 3 crop và routing; warm union 3 crop/2 crop/2 crop lần lượt 2,30/1,12/1,28 s. Không full-page timing, cloud, browser/native transport hoặc percentile. Không đo peak RAM; không suy rằng cấu hình RAM thấp đã được nghiệm thu chỉ vì một worker không crash.

Harness bổ sung nguyên raw classes/scores/geometry của guide, 136 record, cùng model/revision provenance. `text_free` vẫn là class vị trí, không phải SFX hoặc chữ vô nghĩa. Replay chỉ nhận đúng fingerprint/layout/OCR; kiểm tra 8/8 trang giữ regions/alignment/merges/output như fresh. Không tính replay là một lượt model chạy mới.

Evidence private gitignored: `private-block-guided-v2-fresh-20261014.json`, `private-block-guided-v2-evidence-replay-20261014.json`, `private-gate-audit-20261014-guide-v2.json`. Không ảnh/crop/PNG hoặc key trong output; không ship report/dataset.

Lệnh fresh đã chạy (không chạy lại nếu chỉ muốn đọc kết quả):

```powershell
.\.venv\Scripts\python.exe -B scripts/probe_block_guided_grouping.py --folder 'C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001' --pp-reference 'artifacts/private-pages-default-fresh-20261014-v4-scope.json' --block-reference 'artifacts/private-pages-comic-blocks-20261014.json' --output 'artifacts/private-block-guided-v2-fresh-20261014.json'
```

Toàn Python **866 qua / 1 skip**; TypeScript **41 qua**, typecheck/build qua. Test prompt v21 xử lý cả san-vocative, style natural và ngoại lệ reader. Test boundary dùng ROOT riêng để không phụ thuộc vị trí basetemp; guard production không bị nới. Không cập nhật frozen companion hoặc đăng ký Edge cá nhân trong lượt này.
