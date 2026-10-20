# Backend cloud cho desktop và mobile — thiết kế

Cập nhật 19/10/2026. Trạng thái: **thiết kế**; hiện chỉ có server dev chạy trên máy (`apps/server`).
Cloud và từ điển/bộ nhớ truyện dùng chung cho mọi thiết bị; chế độ local (Ollama) chỉ có trên desktop và làm sau.

## 1. Người dùng đến từ đâu

| Thiết bị | Cách đọc | Ghi chú |
|---|---|---|
| Desktop Chrome/Edge | Extension MV3 dịch ngay trên trang web | lấy ảnh bằng quyền của trang (cookie, referer) |
| Android | **Web reader (PWA)**: dán link chương / chia sẻ link vào app / mở ZIP, ảnh của mình | Chrome Android không chạy extension; Edge/Firefox Android có thể chạy bản extension sau |
| iOS | Web reader (PWA) | Safari extension để sau |

Một mã nguồn TypeScript cho cả hai: `packages/core` (logic), `packages/render` (xóa chữ, dàn chữ trên canvas) chạy trong trình duyệt; server dùng lại đúng các gói đó.

## 2. Bước nào chạy ở đâu (chế độ cloud)

| Bước | Desktop (extension) | Mobile (web reader) | Lý do |
|---|---|---|---|
| Lấy ảnh | extension tải ảnh, nén JPEG ~1 280 px (~150–250 KB) rồi gửi | server tải theo link | điện thoại mạng yếu không phải upload; ảnh chỉ ở RAM, không lưu |
| Tìm vùng chữ (detector 11 MB) | server (~0,3 s CPU) | server | đơn giản, như nhau trên mọi máy; sau này có thể chạy WebGPU trên desktop |
| Detector thứ hai cho chữ bị sót (comic-text-detector 95 MB, `apps/server/src/ctd.ts`) | bản miễn phí / chạy trên máy: bật khi có GPU (+0,1 s/trang), tắt trên máy chỉ có CPU (1,6 s/trang) | như desktop | **gói cloud trả phí phải đặt `DETECT_CTD=0`**: model học trên Manga109-s, chỉ được dùng cho học thuật. Trên 60 trang nó tìm lại 17/32 ô chữ detector chính bỏ sót |
| Đọc + dịch (model vision) | server gọi OpenRouter, key nằm ở server, stream từng bóng về | như desktop | không lộ key, tính credit được |
| Vẽ lại nền tranh | trình duyệt (MI-GAN 28 MB, WebGPU ~0,1–0,2 s/vùng) | server (MI-GAN CPU ~0,9 s/vùng, chạy song song lúc dịch) | điện thoại chạy model chậm, tốn pin |
| Dàn chữ, "Xem bản gốc", sửa bóng | trình duyệt | trình duyệt | nhẹ; bản gốc khôi phục đúng từng điểm ảnh |
| Bộ nhớ truyện, từ điển | server (Postgres) + bản sao IndexedDB | như desktop | đồng bộ giữa máy tính và điện thoại |

## 3. Dịch vụ và dữ liệu

- **API**: app Hono hiện có, đóng Docker, chạy Cloud Run / Fly.io (cần `onnxruntime-node` native nên không đặt trên Edge Functions).
- **Supabase**: đăng nhập (email OTP, Google), Postgres với Row Level Security.
- Bảng chính:
  - `profiles`, `credit_ledger` (giữ chỗ → quyết toán → hoàn khi lỗi), `usage_events` (model, token, ms, $ — không lưu ảnh, không lưu thoại);
  - `series`, `memory_entities` (nhân vật, xưng hô A→B, thuật ngữ; trạng thái auto/confirmed/locked; bằng chứng; lịch sử), `memory_records` (thẻ sự kiện, tóm tắt chương);
  - `glossaries` (từ điển của người dùng hoặc của team dịch: nhập/xuất CSV/JSON, chia sẻ công khai nếu muốn), `reading_positions`;
  - `page_results` (bản dịch dạng chữ + toạ độ theo SHA-256 ảnh, **riêng từng người dùng**).
- **Đồng bộ**: mỗi mục có `updated_at` và trạng thái; khi trùng thì khóa của người đọc > đã xác nhận > tự động; lịch sử giữ lại.

## 4. Độ trễ: mục tiêu và cách đạt

Mục tiêu (chưa phải kết quả): bóng đầu < 5 s p95 với trang đang chờ; **0 s** với trang đã dịch trước.

1. Đọc liên tục: dịch trước 1–2 trang kế khi người dùng bật "đọc liên tục" (đã có trong demo, bật thủ công, hiện giá).
2. Trang đang chờ dùng đường nhanh nhất theo số đo (mục 6), trang dịch trước dùng model mặc định.
3. Server tự tải ảnh (mobile), giữ cache prompt nóng, detector warm sẵn.

## 5. Chi phí mỗi trang (đo 19/10, chưa gồm lãi)

| Khoản | Ước tính |
|---|---|
| Đọc + dịch, Claude Haiku 5.5 | $0,00095 (đo, 10 trang) |
| Tóm tắt nền (DeepSeek 1017, ~24 câu/lần) | ~$0,0003 |
| CPU server: tìm vùng + vẽ lại (mobile) | cần đo trên máy chủ thật |
| **Tổng** | **~$0,0013 + CPU** |

## 6. Kết quả đo độ trễ (19/10 tối, `tools/eval/src/latency.ts`)

Cùng 10 trang, cùng yêu cầu (ảnh trang ~470 KB), các cách định tuyến xen kẽ từng trang, mạng nhà: tải lên ~5 Mbps, tải xuống ~9 Mbps.

| Định tuyến | Token đầu p50 | p90 | **Bóng đầu p50** | p90 | Cả trang p50 | $/trang |
|---|---|---|---|---|---|---|
| Haiku 5.5, OpenRouter tự chọn | 7,8 s | 11,5 s | 8,1 s | 11,8 s | 12,3 s | $0,00081 |
| Haiku 5.5, chỉ Anthropic | 7,9 s | 11,3 s | 8,9 s | 11,6 s | 11,4 s | $0,00079 |
| Haiku 5.5, "đua" 2 nhà cung cấp | 7,8 s | 9,9 s | 8,2 s | 10,2 s | 11,7 s | $0,00132 |
| **DeepSeek V4.1 Flash 1017** (InferenceNet) | 2,2 s | 4,2 s | **2,4 s** | **4,3 s** | 4,5 s | $0,00059 |

- Gần như toàn bộ thời gian là **chờ model trả token đầu**; bóng đầu xuất hiện chỉ ~0,3 s sau đó. Trong ngày, Haiku có lúc nhanh hơn (token đầu p50 5,1 s trên 109 lần gọi trước đó) — độ trễ của nó dao động theo tải.
- "Đua" 2 nhà cung cấp tốn thêm 63% mà không nhanh hơn (còn phải upload ảnh hai lần) → bỏ.
- Upload ảnh ~0,75 s ở mạng này: server tự tải ảnh (mobile) bỏ được phần này.

**Đề xuất (chờ kết quả chấm mù của nhóm):** trang người đọc đang chờ mà chưa dịch sẵn → DeepSeek 1017 (bóng đầu ~2,4 s); các trang dịch trước trong lúc đọc → Haiku 5.5. Hai model dùng chung bộ nhớ truyện nên tên và xưng hô vẫn thống nhất. Nếu nhóm chấm DeepSeek kém rõ rệt, giữ Haiku cho mọi trang và dựa vào dịch trước.

## 7. Quyết định nhóm cần chốt

- **Cache dùng chung** giữa người dùng (người sau mở cùng trang là có ngay, không tốn tiền): lợi rất lớn nhưng là phân phối bản dịch của tác phẩm có bản quyền → mặc định **không**, chỉ cache riêng từng người.
- Server tự tải ảnh theo link (mobile) làm server trở thành nơi xử lý ảnh của trang web khác → chỉ giữ trong RAM, có cơ chế gỡ theo yêu cầu, ưu tiên nguồn hợp pháp và file của chính người đọc.
- Giá credit: chỉ chốt sau khi có số chi phí thật trên máy chủ.

## 8. Thứ tự làm

1. **C1**: đóng Docker server, Supabase Auth, bảng credit + mã nạp thử, `/translate` có đăng nhập và giữ/quyết toán credit, API đồng bộ bộ nhớ + từ điển.
2. **C2**: web reader PWA (mở link / ảnh / ZIP), server tự tải ảnh, vẽ lại phía server cho mobile.
3. **C3**: nhập/chia sẻ từ điển team dịch, quyết định cache dùng chung, extension trên Edge/Firefox Android.
