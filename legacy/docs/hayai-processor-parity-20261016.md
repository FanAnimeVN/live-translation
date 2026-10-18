# Hayai Nova: phép thử parity PIL/Fast có căn cứ

2026-10-16. Nghiên cứu mã nguồn và phép thử tensor tự tạo rất nhỏ; **không chạy weights, không mở ảnh/text private, không cài dependency, không gọi API tính phí và không thay production**.

## Kết luận

**Có lý do chạy một comparator Fast trong môi trường cách ly**, nhưng chưa có bằng chứng Fast sửa được CER của bộ private. Khác biệt không chỉ là tên class: PIL và Fast dùng hai backend resize khác nhau và thứ tự số học normalization khác nhau. Giữ nguyên kết luận của [lượt Hayai trước](hayai-comparator-results-20261014.md): comparator PIL đã đo kém baseline trên tập đó; chưa phải kết luận mọi cấu hình upstream Hayai đều kém hơn.

Mục tiêu lượt tiếp theo là bác bỏ/xác nhận **input-tensor parity** trước; không dùng kết quả 13 mẫu tự tạo để đổi engine, và không lặp lại việc thử padding/resampling khác rồi gọi đó là upstream parity.

## Nguồn và dispatch chính xác

Recipe trong Hayai revision `2803d0dc005fa4396ab1e7c5a472d2c450a247f7` dùng `AutoProcessor` của Google, ảnh PIL RGB và ba tensor `pixel_values`, `pixel_attention_mask`, `spatial_shapes`; tokenizer Hayai dùng riêng. Bản local đã pin của Google revision `b53b807d3a2d5e2b3911292f2d69e5341cdc064c` khai báo `Siglip2ImageProcessorFast`, patch 16, mặc định 256, bilinear (`resample=2`), `/255`, mean/std 0.5 và `do_convert_rgb=null`. Hai file local đã được đọc, không thực thi mã repo. [Hayai card đã pin](https://huggingface.co/JustANormalTinkerer/hayai-ocr-v2.5-nova/blob/2803d0dc005fa4396ab1e7c5a472d2c450a247f7/README.md), [Google config đã pin](https://huggingface.co/google/siglip2-base-patch16-naflex/blob/b53b807d3a2d5e2b3911292f2d69e5341cdc064c/preprocessor_config.json).

Trong Transformers 4.57.6, `Siglip2Processor` bọc `AutoImageProcessor`; đường ảnh chỉ chuyển kwargs vào image processor. Không cần tải tokenizer Gemma của Google để so đường ảnh. [Siglip2Processor](https://github.com/huggingface/transformers/blob/v4.57.6/src/transformers/models/siglip2/processing_siglip2.py), [ProcessorMixin dispatch](https://github.com/huggingface/transformers/blob/v4.57.6/src/transformers/processing_utils.py#L580-L610).

`AutoImageProcessor` chọn Fast từ hậu tố config khi `use_fast` không được đặt; **nếu thiếu torchvision thì có thể fallback sang slow**, ngay cả khi yêu cầu `use_fast=True`. Vì vậy chỉ log cờ `use_fast` không đủ: phải assert class thực tế. Script hiện tại chủ động gọi `Siglip2ImageProcessor`, nên không thể coi là đã chạy Fast. [Dispatch 4.57.6](https://github.com/huggingface/transformers/blob/v4.57.6/src/transformers/models/auto/image_processing_auto.py#L526-L574), [comparator hiện có](../scripts/benchmark_hayai_nova.py).

Web fetch hai trang Hugging Face đã pin không thành công trong phiên này; các chi tiết card/config trên được kiểm tra từ bản local đã pin, không giả vờ đã đọc được trang web mới. SHA256 local `preprocessor_config.json`: `1125703e5446d5b6ff4d5893a33bac128cdd21dc12e3dad2469a648fb0ae3bf7`.

## Khác biệt có thể kiểm chứng

| Khâu | PIL hiện tại | Fast native 4.57.6 |
|---|---|---|
| Ảnh vào | NumPy HWC từ PIL RGB | `pil_to_tensor`: tensor CHW, uint8 |
| Kích thước đích | Binary search NaFlex theo patch budget | Import **cùng helper** từ file slow |
| Resize | `PIL.Image.resize`, bilinear | torchvision v2 `F.resize` trên tensor; `antialias=True` |
| Chuẩn hóa mặc định | NumPy float64 `/255`, cast float32, trừ 0.5/chia 0.5 | Fused mean/std thành 127.5; float32 trừ/chia 127.5 |
| Flatten patch | Patch theo hàng rồi cột; bên trong patch theo H,W,C | Permute khác do đầu vào CHW, nhưng kết quả cùng thứ tự H,W,C |
| Padding | Sau normalize, pad giá trị 0 và prefix mask int32 | Cùng quy ước |

Nguồn khâu hình học/patch: [slow SigLIP2](https://github.com/huggingface/transformers/blob/v4.57.6/src/transformers/models/siglip2/image_processing_siglip2.py), [Fast SigLIP2](https://github.com/huggingface/transformers/blob/v4.57.6/src/transformers/models/siglip2/image_processing_siglip2_fast.py). Nguồn backend/số học: [Pillow resize và NumPy rescale](https://github.com/huggingface/transformers/blob/v4.57.6/src/transformers/image_transforms.py), [Fast base resize, conversion và fused normalize](https://github.com/huggingface/transformers/blob/v4.57.6/src/transformers/image_processing_utils_fast.py).

Hai backend resize là một seam thực; **chưa đo sai khác pixel resize** vì không có torchvision. Bilinear cùng tên và antialias cùng ý định không chứng minh bitwise equality. Không tự thay bằng `torch.interpolate` rồi gọi đó là torchvision parity. [API torchvision resize](https://docs.pytorch.org/vision/main/generated/torchvision.transforms.v2.functional.resize.html).

Đã thực hiện phép thử **không resize**, không model: tạo RGB 16×16 chứa đủ 256 giá trị uint8, gọi slow native local với `do_resize=False`, budget 2, so với biểu thức fused float32 đã đọc ở Fast. Kết quả:

- Shapes: pixel `[1,2,768]`, mask `[1,2]`, spatial `[1,2]`; dtype lần lượt float32/int32/int64.
- Spatial `[[1,1]]`, mask `[[1,0]]`; patch padding toàn zero.
- 384/768 kênh hợp lệ khác bit (128/256 mức xám), max abs `5.9138983488082886e-08`.
- Ở pixel 128: slow `0.003921627998352051`; fused `0.003921568859368563`.

Đây là khác biệt số học cụ thể, **không phải chạy class Fast và không phải bằng chứng ảnh hưởng OCR**. Sai số cỡ này riêng lẻ không giải thích được 20 crop tăng lỗi. Không đòi bitwise equality mặc định rồi đánh fail mọi sai số float vô hại.

## Recipe cách ly và điều kiện falsifiable

Không cài torchvision vào `.venv` production. Metadata hiện tại được kiểm tra trực tiếp: Transformers 4.57.6, torch 2.14.1, Pillow 12.3.0, NumPy 2.3.5; torchvision không có. Bảng tương thích upstream đọc trong phiên này chưa liệt kê torch 2.14: **không đoán cặp wheel**, không dùng `--no-deps` để ép. Chọn một cặp torch/torchvision CPU Windows tương thích được công bố, pin/hash trong môi trường comparator riêng; ghi rõ mọi version và chạy cả slow lẫn Fast trong cùng môi trường đó. [Bảng tương thích chính chủ](https://github.com/pytorch/vision#installation).

Sau khi provisioning riêng được cho phép, xây trực tiếp hai native class từ **cùng thư mục Google đã pin**, `local_files_only=True`; assert tên class slow/Fast chính xác và fail nếu torchvision không import được. Không cần Google weights, AutoModel hay mã Hayai. Đặt offline flags và guard socket như comparator cũ; truyền cùng ảnh RGB RAM, `patch_size=16`, budget 512 rõ ràng và `return_tensors='pt'`. Không để wrapper default 256 lẫn vào phép thử 512. Đây là tái lập đường ảnh theo 4.57.6, **không phải chứng nhận toàn runtime GPU/Transformers của tác giả**.

Kiểm tra tensor, trước mọi inference:

1. Cùng ảnh byte-for-byte/RGB, kích thước đầu vào, config hash, crop và thứ tự; không padding/cắt/chia dòng hay strip text thêm.
2. `spatial_shapes` bằng nhau tuyệt đối `[n_h,n_w]`; mỗi chiều >=1; `n_h*n_w <= budget`; kích thước resize `[16*n_h,16*n_w]`. Nếu khác, dừng vì đây không còn là chỉ khác pixel interpolation.
3. Shapes `[B,budget,768]`, `[B,budget]`, `[B,2]`; pixel float32, mask int32, spatial int64 trên CPU. Mọi pixel finite.
4. Mask chỉ gồm prefix `n_h*n_w` số 1 rồi số 0; đúng count; tất cả padded pixel **0 sau normalize**, không phải -1.
5. Test pattern màu/tọa độ để xác nhận RGB và flatten: patch index `p=y_patch*n_w+x_patch`, phần tử `q=(dy*16+dx)*3+c`. Test đơn sắc không bắt được đảo channel/patch.
6. **Isolate resize**: chạy cả hai với rescale/normalize tắt, so uint8 resized patch hợp lệ (exact count, max/mean abs diff). Sau đó chạy không resize trên cùng ảnh patch-aligned để tách sai số normalization.
7. Full normalized tensor: báo max/mean/p95 abs error, tỷ lệ exact, `>1e-6`, `>=1/255`; không chỉ một `allclose(atol=1e-2)`. Một bước uint8 có quy mô normalize `2/255`; không giấu thay đổi nét chữ trong tolerance rộng. Các ngưỡng này là phân loại chẩn đoán, không chứng nhận chất lượng OCR.
8. Giữ toàn bộ pixel/crop trong RAM; chỉ lưu summary/version/hash và tensor statistics. Test khởi đầu: RGB ramp, checkerboard, nét 1px, trắng/đen; kích thước lẻ, rộng/dọc cực đoan, upscale/downscale ở 256/384/512. Sau đó mới phép thử có quyền trên toàn bộ partition private; không chọn crop bằng đáp án.

Nếu tensors bằng nhau trong sai số số học nhỏ: không mặc định coi Fast là lời giải chất lượng; dừng việc dùng processor làm lời giải thích chưa có bằng chứng. Nếu resize khác, phép thử OCR kế tiếp phải giữ cùng pinned weights, tokenizer, CPU FP32, batch 1, greedy/max token và raw punctuation; paired slow/Fast trên cùng partition rồi báo mọi cải thiện/regression. Bất kỳ thay đổi torch/Pillow cũng là confound: chạy lại slow control trong chính môi trường mới. Chỉ sau bằng chứng này mới cân nhắc đổi comparator; production vẫn giữ nguyên.

## Bổ sung: chẩn đoán chỉ dùng torch, không cài torchvision

**Defensible diagnostic, not verified Fast parity.** A manually reviewed torch-only recipe can probe the tensor-resize hypothesis without installing torchvision or importing downloaded Python. Label it `torch-recipe`, pin the recipe source tag, and record installed torch. It cannot prove the author's complete runtime parity. The earlier warning against replacing torchvision with a generic `interpolate` call means that matching branches/strides matters, not that investigating its actual underlying operation is forbidden.

For RGB PIL input, torchvision's `pil_to_tensor` copies HWC bytes, reshapes HWC, then permutes CHW **without** `.contiguous()` or `/255`. The Transformers PIL branch retains this layout when channel inference is FIRST. Do not substitute `to_tensor` (which scales and makes CHW contiguous), and do not pass the PIL image directly to torchvision resize: that dispatches back to Pillow. [Pinned conversion, torchvision v0.28.0](https://github.com/pytorch/vision/blob/v0.28.0/torchvision/transforms/functional.py#L168-L197).

For a nonempty tensor, fixed `[height,width]`, CPU uint8 bilinear: preserve the same-size early return; otherwise reshape to BCHW. If channels-last, batch size 1 and batch stride differs from `numel`, the kernel resets only batch stride to `numel` via `as_strided`. On AVX2/AVX512, uint8 stays uint8; otherwise v0.24 casts float32, interpolates, rounds, then restores uint8. The call uses `size=[height,width]`, `mode='bilinear'`, `align_corners=False`, `antialias=True`, no `scale_factor`. Do not round a second time on the native uint8 branch. Float32/64 inputs stay their dtype. Empty input and other interpolation/device/dtype cases are outside this restricted RGB recipe. [Pinned resize branches, torchvision v0.24.0](https://github.com/pytorch/vision/blob/v0.24.0/torchvision/transforms/v2/functional/_geometry.py#L227-L305).

Version caveat: v0.28 keeps this interpolate/stride structure but adds eager native uint8 support for aarch64/arm64 and treats scripted bilinear as native-capable. Compiled mode already selects native uint8 in v0.24. A CPU eager Windows diagnostic must log capability, architecture and these flags rather than pretend all machines take one branch. Transformers' special compiled ROCm workaround is not the CPU eager path. [Pinned newer branches, torchvision v0.28.0](https://github.com/pytorch/vision/blob/v0.28.0/torchvision/transforms/v2/functional/_geometry.py#L238-L326).

Current local capability probe returned `AVX512`, `AMD64`, scripting false, compiling false. That would select the native uint8 branch under either inspected tag; it is not a run of those torchvision kernels.

After resize, apply the previously established fused float32 normalization; then restore the exact HWC-within-patch order, zero padding, prefix mask and spatial dimensions. Compare both native-uint8 and float-cast recipes only as explicitly separate candidates, not answer-selected per crop. Record input/output strides and valid-pixel statistics. Later, verify the chosen recipe against a real pinned Fast class before naming it Fast parity; a difference in OCR from a manual recipe is evidence about that candidate only. No torch resize candidate was implemented or run in this research task.

## Những gì lượt này không chứng minh

Không chạy Fast thực, không đo private CER mới, không đọc dữ liệu benchmark, không đo latency extension hay cải thiện tốc độ. Không thay engine/default, không sửa quotes bằng regex, không cấp quyền erase/memory từ OCR mới. Ghi chú duy nhất này là thay đổi file của lượt nghiên cứu.
