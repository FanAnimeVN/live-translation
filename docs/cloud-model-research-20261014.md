# Cloud Nhật → Việt: shortlist kiểm thử 2026-10-14

**Chốt ở mức nghiên cứu:** giữ DeepSeek Flash làm ứng viên mặc định, so với Gemini Flash-Lite, Qwen Flash và Haiku mới; Gemini Flash là đối chứng chất lượng. Chưa model nào được chứng minh tốt nhất cho manga của chúng ta. OCR, cleanup, context và cache kết quả vẫn local; cloud chỉ nhận text cần dịch và context đã giới hạn spoiler.

Đã đọc nguồn chính thức và catalogue/endpoint công khai; không truy cập key, gọi suy luận trả phí, gửi dataset hay đổi cài đặt. Giá là USD/1M token input/output, không phải giá cố định hoặc độ trễ đã đo.

## 1. Năm ID nên benchmark trên OpenRouter

| ID request chính xác | Giá tham chiếu | Context / output tối đa catalogue | Điều kiện so sánh |
|---|---|---|---|
| `deepseek/deepseek-v4.1-flash` | Route hãng: **0,15 / 0,60 off-peak; 0,30 / 1,20 peak** | 1.048.576 / phụ thuộc route | Tắt reasoning; giữ model/provider/quantization trong kết quả |
| `google/gemini-3.5-flash-lite` | Standard **0,30 / 2,50** | 1.048.576 / 65.536 | `minimal`; thinking không tắt hoàn toàn |
| `qwen/qwen3.8-flash` | Alibaba **0,15 / 0,47** | 1.000.000 / 131.072 | Tắt reasoning; đối chứng rẻ |
| `anthropic/claude-haiku-5.5` | **0,10 / 0,50** khi prompt dưới 100K | 1.000.000 / 128.000 | Tắt reasoning; bỏ sampling parameters không hỗ trợ |
| `google/gemini-3.8-flash` | Standard **0,75 / 3,75** đến hết 2026 | 1.048.576 / 65.536 | `low`, **không `minimal`**; đối chứng đắt hơn |

ID, canonical version và capability đã xác minh trong [catalogue sống](https://openrouter.ai/api/v1/models). Giá/route: [DeepSeek endpoints](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints), [Gemini Lite endpoints](https://openrouter.ai/api/v1/models/google/gemini-3.5-flash-lite/endpoints), [Qwen endpoints](https://openrouter.ai/api/v1/models/qwen/qwen3.8-flash/endpoints), [Haiku endpoints](https://openrouter.ai/api/v1/models/anthropic/claude-haiku-5.5/endpoints), [Gemini Flash endpoints](https://openrouter.ai/api/v1/models/google/gemini-3.8-flash/endpoints).

Snapshot canonical slugs: DeepSeek `...-20260910`, Lite `...-20260721`, Qwen `...-20260826`, Haiku `...-20261007`, Flash `...-20260902`. Lưu slug thực tế trong benchmark; không dùng alias `~…-latest`. Catalogue sống không đảm bảo tài khoản cụ thể có route khả dụng.

**Không so giá sàn với Standard:** API trực tiếp hiện trả DeepSeek giá sàn OpenInference FP4 **0,0441 / 0,63**, còn bản web cache cho route khác **0,112 / 0,336**; FP4/FP8/provider phải tách điều kiện. Gemini Lite Flex **0,15 / 1,25**, Flash Flex **0,375 / 1,875** là tier khác; không dùng để quảng cáo độ trễ Standard. [DeepSeek endpoints](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints), [service tiers](https://openrouter.ai/docs/guides/features/service-tiers)

Ngoài shortlist: Hy-MT2-7B hiện còn ID `tencent/hy-mt2-7b`, **0,074 / 0,295**, context 8.192/output 4.096; dùng làm specialist baseline khi cần, không cần mở rộng đợt đầu. Gemini 3.1 Lite vẫn có ID nhưng không ưu tiên thêm một thế hệ Lite vào cùng pilot. [Catalogue](https://openrouter.ai/api/v1/models)

## 2. Cấu hình adapter để tránh lỗi/chi phí thừa

- OpenRouter: `reasoning.enabled=false` cho model cho phép; `exclude=true` chỉ giấu suy luận, vẫn tính tiền. Đọc reasoning tokens và `finish_reason`; không chữa JSON bị cắt bằng cách tự thêm nghĩa. [Reasoning controls](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
- DeepSeek **direct** dùng ID `deepseek-flash` = V4.1 Flash, `thinking:{type:"disabled"}`. Đây không phải ID OpenRouter. Prompt cache direct tự động, best-effort; giữ prefix ổn định và đo `prompt_cache_hit_tokens`, không mặc định hit ngay lần đầu hoặc lưu vĩnh viễn. [Direct pricing](https://api-docs.deepseek.com/quick_start/pricing/), [thinking](https://api-docs.deepseek.com/guides/thinking_mode/), [cache](https://api-docs.deepseek.com/guides/kv_cache/)
- Gemini Lite dùng `minimal`; Flash 3.8 chỉ `low/medium/high`. Không gọi minimal là zero-thinking. Giá Flash Standard dự kiến tăng **1,50 / 7,50 từ 2027-01-01**. [Thinking levels](https://ai.google.dev/gemini-api/docs/generate-content/thinking), [Google pricing](https://ai.google.dev/gemini-api/docs/pricing)
- Qwen direct có hybrid thinking, `enable_thinking=false`; OpenRouter dùng unified reasoning, không chép field provider-specific tùy tiện. [Alibaba controls](https://www.alibabacloud.com/help/en/model-studio/deep-thinking)
- Haiku 5.5: bỏ `temperature/top_p/top_k`; suy luận tắt ở effort high trở xuống. Minimum cacheable prefix 512 token; không thêm văn bản vô ích chỉ để đạt ngưỡng. Bedrock chưa hỗ trợ structured outputs cho model này. [Haiku overview](https://platform.claude.com/docs/en/models/haiku-5-5/overview), [breaking changes](https://platform.claude.com/docs/en/models/haiku-5-5/whats-new-haiku-5-5)
- `json_schema`, `strict:true`, `additionalProperties:false` và `require_parameters:true` cho route tương thích; vẫn kiểm ID/số mục/nội dung local. DeepSeek direct hiện tài liệu hướng dẫn `json_object`, cảnh báo nội dung rỗng và truncation. Schema hợp lệ không đồng nghĩa dịch đúng. [OpenRouter structured output](https://openrouter.ai/docs/guides/features/structured-outputs), [DeepSeek JSON](https://api-docs.deepseek.com/guides/json_mode/)

## 3. Privacy và tích hợp trả phí: các giới hạn thật

OpenRouter không lưu prompt/output nếu không opt-in, nhưng có usage metadata; upstream có chính sách riêng. `data_collection:"deny"` **không phải** chứng nhận zero retention. Dùng thêm `zdr:true` nếu cần ZDR; route không đạt chính sách phải báo unavailable, không âm thầm nới quyền. ZDR không bao phủ plugins/tools; tắt search/auto-router cho dịch. [Collection](https://openrouter.ai/docs/guides/privacy/data-collection), [provider policies](https://openrouter.ai/docs/guides/privacy/provider-logging), [ZDR](https://openrouter.ai/docs/guides/features/zdr)

Hiện ZDR loại first-party Anthropic và AI Studio; Vertex vẫn có route eligible. In-memory prefix caching được OpenRouter coi tương thích ZDR; điều này không phải cam kết không tồn tại dữ liệu trong RAM. Pin endpoint/tier và kiểm policy trước benchmark. [ZDR](https://openrouter.ai/docs/guides/features/zdr)

**Điểm cần xử lý trước phát hành:** Gemini Developer API terms hiện cấm API client nhắm tới hoặc có khả năng được người dưới 18 tuổi truy cập. Unpaid tier có thể dùng dữ liệu để cải thiện sản phẩm; paid không dùng để training nhưng vẫn log giới hạn cho abuse/legal. Một extension manga rộng rãi không được bỏ qua điều kiện tuổi bằng BYOK hoặc proxy; hợp đồng Vertex/enterprise áp dụng phải được rà riêng. [Google terms](https://ai.google.dev/gemini-api/terms)

OpenRouter không miễn/đổi Model Terms của upstream; chủ ứng dụng chịu trách nhiệm với customer usage và bảo vệ key. DeepSeek terms §3.6(4) hạn chế bán/chuyển nhượng/sublicense toàn bộ hoặc phần dịch vụ khi chưa được phép. Cần xác nhận quyền tích hợp gói credit theo hợp đồng cụ thể; không kết luận mọi app thương mại đều bị cấm, cũng không mặc định có key là được bán lại. [OpenRouter terms](https://openrouter.ai/terms), [DeepSeek terms](https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html)

## 4. Quyết định qua số đo, không qua tên model

So cùng thoại/context tự tạo được phép đưa cloud, thứ tự model đảo giữa các lượt; tách cold/warm/cache. Chấm nghĩa, phủ định/chủ thể, `em–chị` đã khóa, tên/honorific, nhịp `わ・た・し〜〜`, không bịa gender/spoiler và không thêm dấu quote. Đo cả first accepted bubble/page, retries, refusals, reasoning, token/cost trên **kết quả được chấp nhận**, không chỉ tok/s.

Khởi điểm routing: `sort:"latency"`, `require_parameters:true`, `data_collection:"deny"`, giá trần/token trần và một repair tối đa. A/B chính thức pin provider cụ thể với `allow_fallbacks:false`; tối ưu động sau. Preferred latency chỉ là preference, không SLA; `max_price` là bộ lọc thực sự. [Routing](https://openrouter.ai/docs/guides/routing/provider-selection)

Chỉ chọn mặc định khi qua các lỗi đã biết và mẫu giữ riêng. Bộ dataset OCR Nhật không có đủ bản dịch Việt để chứng minh chất lượng dịch; quyền xử lý local không tự cho phép gửi text/ảnh có bản quyền cho cloud. Chưa có số đo mới trong ghi chú này; pilot cũ nằm ở `cloud-benchmark-sources.md` và không được biến thành lời hứa real-time.
