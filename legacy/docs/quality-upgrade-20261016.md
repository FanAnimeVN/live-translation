# Nâng cấp chất lượng manga thật — 2026-10-16

## Kết quả và phạm vi

Source layout hiện là `balloon-mask-v20-source-footprint-corners`. Đã sửa một
lỗi có bằng chứng ảnh thật: các cột chữ dài/ngắn khác nhau tạo góc trống ngoài
bóng ở hộp union, khiến bóng kín bị chuyển thành nhãn/bảng đọc. Trên bộ riêng,
hai bóng ở MN109-06 và MN109-08 nay đủ điều kiện dàn chữ nền trong suốt.
**Chưa đạt chất lượng manga tổng thể; không phải bản phát hành đã nghiệm thu.**

Không đổi engine OCR, prompt, model dịch, grouping, thứ tự hay bbox nguồn.
Không gọi cloud hoặc dùng credit. Không cập nhật frozen companion/registry
Edge cá nhân trong lượt này. Build extension vẫn `0.1.0-dev.ae423bfce5e4`
vì bundle TypeScript không đổi; thay đổi Python có runtime package hash riêng.

## Tái hiện → nguyên nhân → sửa

MN109-08 có hộp nguồn `[140,767,91,107]`. Chạy group trên đúng bốn polygon PP
đã ghi nhận: trước sửa không có `balloon`. Mỗi cột riêng qua cùng kiểm tra an
toàn; hộp union lại chạm cung viền ở góc dưới-phải không chứa chữ.

v20 giữ nguyên kiểm tra nền phẳng, biên kín, erosion và outline/halo. Nếu nhánh
union cũ không qua, chỉ thử footprint thật của từng cột có padding y như crop
nguồn. Mỗi footprint vẫn chịu giới hạn 10%/8 px cũ. Mọi nét tương phản không an
toàn trong union vẫn phải nối được với outline ngoài/halo được giới hạn.
Chỉ góc union không thuộc footprint, nằm ngoài mặt kín mới được nhận halo
JPEG ngoài; không mở rộng writable interior.

Kiểm tra trực quan bóng thứ hai phát hiện nhánh mask cũ còn định xóa giọt mồ
hôi gần chữ. Nhánh phục hồi mới vì vậy chỉ chọn connected ink có giao footprint
nguồn; không lấy mọi nét trong bán kính hai cỡ chữ. Nét chưa được giải thích
được bảo vệ cả halo; nếu chiếm vùng dàn chữ hoặc khiến glyph không xóa đủ thì
giữ fallback. Không coi một detector bbox là glyph mask hoặc phân loại ngữ nghĩa.
Nhánh union cũ không bị đổi mask hàng loạt; chưa chứng nhận nó phân biệt mọi
nét trang trí/chữ. Crop thu nhỏ còn chạm viền vẫn fallback, không nới ngưỡng.

## Đối chiếu cả bộ riêng

Fingerprint giữ nguyên; 10 ảnh khai báo nhưng chỉ 8 trang/78 nhãn Nhật hợp lệ
sau loại một ảnh trùng và một trang sai kích thước. Nhãn Nhật chưa được rà
độc lập; **0 Việt gold hợp lệ, không có clean-background gold**.

| Chỉ số | Production trước | v20 fresh detector + OCR |
|---|---:|---:|
| Vùng nguồn | 132 | 132 |
| Bóng đủ điều kiện integrated | 8 | 10 |
| Nhãn containment gán | 62/78 | 62/78 |
| Exact trên nhãn chưa rà | 35/78 | 35/78 |
| Edit / ký tự | 269/939 | 269/939 |
| CER chẩn đoán | 28,65% | 28,65% |
| Crop partition / seam | 10 / 5 | 10 / 5 |

Đã so từng vùng: không đổi JA, ID, bbox hoặc order. Hai overlay đổi
`label → white`; không mất bóng integrated cũ. Replay control/candidate giữ
routing và source-key. Lần fresh có bốn dấu chấm review được defer bởi policy
đã có trước v20; không tính đó là cải thiện OCR, không xóa nguồn hoặc đưa vào
plot memory. Mọi source-key vẫn giống bản ghi cũ.

Lần fresh CPU 4 threads: trang lạnh detector 23,11 s + OCR 8,12 s; các trang
sau detector 1,19–1,39 s, OCR 5,64–14,44 s. Cleanup p50 73,30 ms.
Đây không phải đo dịch cloud, first paint, p95 hoặc độ trễ tăng của v20.
Chưa tối ưu/đánh đổi tốc độ để lấy điểm chất lượng.

## QA renderer thật

Luồng: nguồn private → geometry production từ raw PP đã ghi → font/renderer
production → cuộn → Xem gốc. Edge cô lập, localhost, viewport desktop 1280 px.
Browser plugin không có; dùng Playwright hiện có. Native transport và bản Việt
do QA cung cấp, không gọi OCR/LLM trong phép thử renderer và không chấm nghĩa.

| Kiểm tra | MN109-06 | MN109-08 |
|---|---|---|
| Đúng trang, không blank/framework overlay | Qua | Qua |
| Chữ trong suốt, không viền/shadow, không overflow | Qua | Qua |
| Mực nguồn trong các ROI glyph | 1.174 → 0 pixel | 973 → 0 pixel |
| Thay đổi ngoài erasure halo | 0 pixel | 0 pixel |
| ROI giọt mồ hôi được bảo vệ | 0 pixel đổi | Không áp dụng |
| Cuộn giữ vị trí | Qua | Qua |
| Xem gốc khôi phục exact ảnh nguồn | Qua | Qua |
| Console lỗi / request ngoài localhost | Không | Không |

Đã xem screenshot RAM của cả hai bóng: chữ đi vào nền bóng gốc; giọt mồ hôi
còn nguyên. Screenshot/crop/patch không ghi ra đĩa. Có giữ kiểm tra responsive
sẵn có, không tính đó là nghiệm thu mobile. ROI không phải complete glyph gold
hoặc clean-background gold, nên không suy ra mọi pixel tranh đều phục hồi đúng.

## Test và tái lập

- Lượt cuối: 1.217 Python pass / 1 skip, gồm test cache/source binding; suite
  đầy đủ chạy 37,39 s. Skip là symlink Windows.
- 58 TypeScript pass, typecheck và build qua.
- Test đỏ trước sửa: safe unequal-column union bị fallback; test đỏ tiếp theo:
  giọt mồ hôi bị mask. Cả hai đã xanh, cùng các ca nền tối/ngang/resize, nét
  lạ ngoài footprint, actual column không an toàn và fallback khi nguồn nhỏ.
- Lượt pytest mặc định ban đầu lỗi quyền thư mục tạm, không phải code:
  chạy lại với basetemp mới trong artifacts qua toàn suite. Không sửa ACL hay
  bỏ các test lỗi để lấy xanh.

```powershell
.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --basetemp artifacts/<thu-muc-test-moi> -q
npm.cmd run check
.venv\Scripts\python.exe -B scripts/probe_balloon_footprints.py --folder '<bo-mau-rieng>' --reference artifacts/private-pages-production-partition-20261014.json --detector-replay artifacts/private-pages-open-overlap20-fresh-20261014.json --output artifacts/<ket-qua-rieng-moi>.json
.venv\Scripts\python.exe -B scripts/benchmark_pages.py --folder '<bo-mau-rieng>' --output artifacts/<fresh-output-moi>.json
```

Kết quả text riêng trong artifacts: `private-balloon-footprints-v20-20261016.json`,
`private-pages-production-v20-20261016.json`, `private-lettering-v20-20261016.json`.
Không đưa artifacts hoặc dataset vào bundle/repo công khai.

## Cổng còn đỏ

OCR/grouping còn lỗi, nhất là chữ không bóng, chữ nhỏ và crop gộp nhiều câu;
35/78 exact chưa phải chuẩn cần đạt. Fallback đọc cạnh trang tránh chồng chữ
nhưng không được gọi là integrated scanlation. Chưa có đánh giá Việt độc lập
để chứng minh lỗi nghiêm trọng ≤2%, chưa có background gold hoặc benchmark
đại diện để hứa hoàn hảo. Chưa xác minh lại native host trong Edge cá nhân.
Giữ nguyên mọi gate, không mở rộng dataset hay phát hành dựa trên hai bóng đẹp.
