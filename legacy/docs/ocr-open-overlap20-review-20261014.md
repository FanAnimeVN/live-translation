# Đối chứng gom cột mở `.2` — 2026-10-14

Lượt này chạy fresh inference local trên bộ riêng `drive-download-20261012T095418Z-1-001`. Ảnh chỉ ở RAM; không gọi cloud, không ghi ảnh/crop/patch và không thay cấu hình companion. Artifact chi tiết nằm trong thư mục gitignored `artifacts/private-pages-open-overlap20-fresh-20261014.json`.

## Kết quả

| Tuyến | Vùng | Có prediction gán nhãn | Exact chẩn đoán | CER chẩn đoán |
|---|---:|---:|---:|---:|
| baseline hiện tại | 132 | 62/78 | 34/78 | 29,18% |
| open-overlap `.2` | 125 | 62/78 | 35/78 | 28,75% |

Đây chỉ là alignment/CER trên nhãn OCR chưa được rà độc lập, không phải precision/recall detector và không phải điểm dịch Việt. Tập vẫn chưa có Việt gold hợp lệ hoặc clean-background gold.

## Ca cải thiện và regression

- `MN109-08:b02`: hai cột được gom thành một crop; lỗi giảm từ 5 xuống 0. Đây là bằng chứng rằng grouping có thể giúp OCR khi cột thuộc cùng một câu.
- `MN109-04:b13`: grouping làm số vùng giảm nhưng OCR union đổi dấu/ngắt nhịp và tăng lỗi từ 6 lên 7. Không được đánh đổi biểu đạt nguyên bản chỉ để có ít vùng hơn.
- `MN109-08` vẫn có các vùng phủ định/ellipsis tách riêng trong chuỗi đọc. Một union đúng hình học chưa đủ chứng minh thứ tự chữ, glyph hay ownership.

## Quyết định

Không promote `.2` vào runtime. Candidate giữ `sourceMembers`, điểm detector và cờ review; không cấp quyền xóa nền hoặc ghi memory. Hướng thử tiếp theo là **OCR từng source member rồi gom cho dịch/dàn chữ**, chỉ dùng union OCR như đối chứng khi có kiểm tra toàn vẹn ký tự và dấu câu. Mục tiêu là tránh lỗi aspect-ratio của crop union, không làm mất chữ để giảm số vùng.

Lượt này không thay `LAYOUT_VERSION`, prompt, cache key hoặc reader bindings.

## Thử OCR theo source member

Lượt đầu của comparator `scripts/probe_member_preserving_grouping.py` chạy năm cụm (một ở MN109-02, hai ở MN109-04 và hai ở MN109-08); aggregate ghi được **35/78 exact, CER 28,75%**. Tuy nhiên harness đã ghi đè `ja` union trước khi ghi mục so sánh và bỏ các prediction từng member. **Rút lại kết luận rằng text từng member trùng với union**: aggregate bằng nhau không chứng minh từng chuỗi bằng nhau. Artifact v1 không đủ provenance cho kết luận đó.

Comparator `member-preserving-v2` giữ riêng `unionJa`, `memberJa`, prediction/polygon/score và chỉ số member/raw detector. Có test tái hiện lỗi ghi đè trước bản sửa. Đối chứng mới chỉ chấp nhận report local fresh đúng phiên bản/fingerprint, đủ mọi trang hợp lệ, member khớp chính xác raw detector và cờ distrust còn nguyên; hạn chế 1–4 CPU threads, batch 1–2 và không ghi đè artifact cũ. Crop member làm tròn ra ngoài để không cắt mất pixel ở biên phân số. Vẫn không sửa runtime, cache, memory, reader bindings hay cấp quyền xóa tranh.

Lượt v2 đã hoàn tất trên đủ tám trang hợp lệ; bằng chứng riêng nằm ở `artifacts/private-member-preserving-v2-20261014.json`. **Bốn cụm trùng, một cụm khác** (`MN109-04:r016`). Cụm khác vẫn có khoảng cách 7 edit với nhãn `b13`; aggregate member và union đều 35/78 exact, CER 28,75%. Đây là ví dụ cụ thể tại sao aggregate bằng nhau không có nghĩa text bằng nhau. Có 51 test mới cho comparator; toàn bộ suite Python đạt **930 pass, 1 skip**. Không promote candidate: các regression biểu đạt của `.2`, thiếu nhãn Việt/background gold và lỗi baseline vẫn chưa được giải quyết.
