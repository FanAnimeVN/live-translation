# Xem gốc: đã sửa; chất lượng manga chưa đạt

Lượt đối chứng tiếp theo đã tách sai lệch raster của browser khỏi lỗi overlay, thêm raw control/native-pixel geometry và scope v4: [báo cáo mới nhất](quality-review-20261014-latest.md). Các số liệu bên dưới là lượt trước.

Cập nhật 2026-10-14. **Không gọi API, không nạp OCR/LLM; ảnh/crop/patch/screenshot private chỉ RAM.** Không đổi weights, prompt v20, OCR local-v3, layout v16, scope v3 hoặc nhãn benchmark. Không promote frozen host/Edge cá nhân.

## Lỗi và sửa

`renderVisibility()` trước đây chỉ xếp `position()` vào RAF. Trì hoãn RAF rồi Alt+T còn 5 vùng dịch và 3 lớp xóa chữ đang hiện trên MN109-08. Test UI tự tạo cũng đỏ: “Original must hide text and erasure immediately, before RAF”.

Đã sửa `extension/content.ts`: xem gốc ẩn chữ/erasure đồng bộ; chữ/polygon/PNG mới bắt đầu ẩn, kể cả native/decode trả muộn. Trở lại bản dịch chờ tọa độ/clip hiện tại, không hiện lớp cũ ở vị trí lỗi. Không thay mask, lời dịch, speaker hoặc chi phí.

## Kết quả và giới hạn

| Kiểm tra | Kết quả |
|---|---|
| Regression RAF/late balloon/late PNG | Qua sau khi đã đỏ trước sửa |
| Private replay MN109-08 | ID/chữ/cuộn qua; initial/restored/stopped hash khớp |
| MV3/Native Messaging thật, output replay | Handshake/runtime/ID/cuộn/Alt+T/390 px/stop/console/cleanup qua |
| Python / TypeScript | 755 qua + 1 skip Windows symlink / 41 qua; typecheck/build qua |
| UI/options/art/lettering QA | Qua Edge riêng; OCR/dịch fixture giả lập |
| Cổng không va chạm lettering private | **FAIL**, 4 cặp textBox giao nhau |

Replay nhẹ đã khôi phục chính xác cả **trước** sửa: đây là sửa race đã tái hiện, **chưa giải thích dứt điểm** hash mismatch của inference nặng trước. Replay `total_ms=1` là sentinel, không quảng cáo tốc độ/cache hit. Browser plugin không có; dùng Playwright/Edge riêng, không đóng app người dùng.

Ảnh RAM đầu trang xác nhận r000/r001 và r004/r005 chồng chữ. Cặp diagnostic khác: r001/r002 và r001/r003. Giao textBox không tự chứng minh giao glyph; không dùng để gộp câu, thu chữ dưới sàn hoặc che tranh. Nhãn dự phòng/OCR/nghĩa dịch còn lỗi. Bộ private vẫn 8 trang/78 crop; crop exact 48/78, full-page exact 34/78; chưa có Việt gold hợp lệ hoặc clean-background gold.

## Tái lập không tốn credit

Chạy từ repo bằng source đã build:

```powershell
npm run check
npm run test:ui
node scripts/private-render-replay.mjs --folder 'C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001' --page MN109-08 --native-result 'D:\Projects\Live translation\artifacts\private-browser-mn10908-20261014-original-failure.json' --hold-visibility-frame --assert-no-lettering-overlap
```

Lệnh cuối **phải còn fail ở lettering**, nhưng các check chức năng/xem gốc xanh. Bỏ `--assert-no-lettering-overlap` chỉ chạy cổng chức năng, không thay tiêu chuẩn chất lượng. `--ram-preview` trả ảnh translated-first-viewport vào pipe RAM, không lưu raster.

Native replay dùng `scripts/browser-pipeline-smoke.mjs --direct-source --render-replay`, kèm `--replay-native-result`, `--private-folder`, `--private-page` rõ ràng. Entry QA chặn warmup/retranslate/summary/metadata/provider; kiểm tra fingerprint/source/patch coverage trước chạy. Native evidence sau guard mới: system-temp `mangalive-real-browser-5ReFG7\evidence\result.json`; diagnostic cuối: `artifacts/private-render-replay-mn109-08.json`, không ship.

**Tiếp theo:** sửa gom cột/thứ tự và va chạm dàn chữ trên crop thật; kiểm tra glyph/nền ngoài mask, giữ source/gold nguyên. Chỉ tối ưu/publish khi chất lượng qua, không lấy fixture đẹp thay nghiệm thu manga thật.
