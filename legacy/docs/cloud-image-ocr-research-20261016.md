# Cloud image OCR: bounded evaluation, not a new default

Checked 2026-10-16. Public, first-party documentation/catalog reads only; this research made no paid requests, read no credentials and accessed no private images. Prices/capabilities are a dated snapshot, not a quality result. User consent now covers authored images/crops and the rights-confirmed private benchmark through OpenRouter, within the existing cumulative $0.50 authorization. Existing text-only BYOK must not silently become image upload.

## Available candidates

| Exact OpenRouter model ID | Image input → text output | Advertised input / output USD per million tokens | Reasoning control in catalog |
| --- | --- | --- | --- |
| `anthropic/claude-haiku-5.5` | Yes | $0.10 / $0.50 below 100,000 prompt tokens; $0.50 / $2.50 at the long-context threshold | Optional; `none` supported; default medium |
| `google/gemini-3.5-flash-lite` | Yes | $0.30 / $2.50; image input is separately listed at $0.30/M image tokens | Mandatory; `minimal` is the lowest listed effort |
| `qwen/qwen3.8-flash` | Yes | $0.15 / $0.47 | Optional; default enabled; token-budget support advertised |

All three expose `response_format` and `structured_outputs` in the live public catalog. Gemini's canonical catalog slug is `google/gemini-3.5-flash-lite-20260721`; Haiku's is `anthropic/claude-haiku-5.5-20261007`; Qwen's is `qwen/qwen3.8-flash-20260826`. Catalog identity does not establish manga OCR quality. [Live OpenRouter models catalog](https://openrouter.ai/api/v1/models).

The Haiku endpoint listing includes `google-vertex/global`, `anthropic`, `amazon-bedrock`, and other endpoints; support must be checked per endpoint, not just at model-family level. Its standard-price Vertex endpoint advertises JSON-schema output. [Haiku endpoints](https://openrouter.ai/api/v1/models/anthropic/claude-haiku-5.5/endpoints).

Qwen's endpoint listing includes `alibaba` and `alibaba/us-east-1`, both with schema/response-format support at the listed rate. That is not evidence either satisfies the project's privacy filters. [Qwen endpoints](https://openrouter.ai/api/v1/models/qwen/qwen3.8-flash/endpoints). Alibaba's own model page confirms image/text/video input, text output and structured output; its direct-service prices are not OpenRouter prices. [Alibaba Qwen3.8 Flash](https://www.alibabacloud.com/help/en/model-studio/qwen3-8-flash).

**Evaluation choice, not deployment decision:** start Haiku OCR with thinking explicitly disabled and Gemini with minimal thinking as a countercheck. Haiku is inexpensive and has a suitable output-control path; only real crop/page evaluation can justify promotion. The prior text-translation pilot does not rank OCR.

## Transport and output contract

OpenRouter image understanding uses `/api/v1/chat/completions`, multipart message content and `image_url` entries. Private local images can be embedded as base64 data URLs; multiple images use separate entries. Supported MIME types include PNG/JPEG/WebP/GIF. Put text instructions before images. For this project, use RAM-encoded PNG bytes only, no public hosting, Files API, remote URL fetching or local image artifacts. [OpenRouter image inputs](https://openrouter.ai/docs/guides/overview/multimodal/image-understanding).

Use `response_format.type="json_schema"`, `strict:true`, and `provider.require_parameters:true`. Router documentation explicitly warns that schema enforcement varies by endpoint, so locally validate every response regardless of strict mode. [OpenRouter structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs).

Proposed crop contract: exact known IDs; bounded Japanese text string; status `readable`, `blank`, or `uncertain`; no translation, guessed speakers, plot knowledge or tools. Blank is a valid empty string. Preserve punctuation, line breaks, elongation and spaced delivery rather than demanding polished sentences. Reject duplicate/missing IDs, overlong output, extra fields and unknown IDs. Full-page detection/reading-order experiments must be separate from fixed-crop recognition. Never treat generated coordinates as glyph masks or cleanup authorization.

Reasoning is billed output. `exclude:true` hides it but does not disable or unbill it. On most providers reasoning and visible text share `max_tokens`; a small total can return a charged empty/length-truncated response. Gemini's mandatory reasoning must not receive `effort:none`. Use explicit bounded output and record finish reason, reasoning-token usage and visible output separately. [OpenRouter reasoning-token controls](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

## Image token accounting

**Base64 length is payload/RAM accounting, not vision-token accounting.** No universal token-per-byte formula applies to image content.

Anthropic documents visual tokens as `ceil(width/28) × ceil(height/28)` after image preprocessing. Claude 4.7+ has a 2,576px long-edge limit and a 4,784-token visual budget; larger images are downscaled. Lossy compression can hurt fine text. Small/rotated/low-quality images and spatial coordinates remain error-prone. At a project maximum long edge of 1,568px, the raw patch formula is at most 3,136 tokens/image. Apply a reservation margin, not an assumption that OCR is exact. [Anthropic vision limits and costs](https://platform.claude.com/docs/en/build-with-claude/vision).

Google's Gemini 3/4 media-resolution documentation lists 280/560/1,120 image tokens at low/medium/high and 2,240 at ultra-high. It recommends high for most image analysis and dense content. This is the native Google interface: the OpenRouter image contract consulted here does not establish a portable mapping of `image_url.detail` to every native setting. Do not assume low-res pricing or lossless full-page detail without measuring the actual endpoint. [Google media resolution](https://ai.google.dev/gemini-api/docs/media-resolution).

Alibaba's vision guide gives image tokens as `height × width / (32 × 32) + 2` after its resolution handling. Its OpenAI-compatible API also exposes model-specific pixel limits. Do not reuse Qwen2/Omni formulas indiscriminately or assume native extras pass through OpenRouter. [Alibaba vision accounting](https://www.alibabacloud.com/help/en/model-studio/vision-model), [Alibaba compatible API](https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions).

The proposed harness ceiling of **16,384 reserved vision tokens per image**, at ≤1,568px long edge and ≤2.5M pixels, is deliberately above these documented estimates. It is a conservative project reservation, not a claim about exact billed usage. Add text/schema/framing allowance, reserve the entire output limit including reasoning, and reject a request if the reservation would cross the run/cumulative limit. Images/batches that violate the bounded contract must fail before network access.

### Router price-unit pitfall

`provider.max_price.prompt` and `.completion` are documented in USD/M tokens. `.image` is described as maximum price **per image**, while Gemini catalog `pricing.image` is an image-**token** rate. Therefore copying Gemini's `0.0000003` into `provider.max_price.image` is not justified as a total image-cost ceiling. Treat this unit ambiguity explicitly: use reviewed prompt/completion ceilings plus a conservative vision reservation; reject unknown request fees or separately priced image mechanisms. `max_price` filters endpoints, not aggregate session spend. Restrict exact endpoint/provider and disable fallbacks; no opportunistic more-expensive provider. [Provider selection and price filters](https://openrouter.ai/docs/guides/routing/provider-selection).

## Privacy is endpoint-specific

`provider.zdr:true` requires ZDR endpoints and cannot weaken stricter account/guardrail settings. Current docs say this excludes first-party Anthropic and Google AI Studio; Bedrock/Vertex remain possible. ZDR can still permit provider-side in-memory implicit caching under OpenRouter's definition. This is not a promise that content never enters any cache. Fail closed if no eligible endpoint; do not relax privacy to obtain a result. [OpenRouter ZDR](https://openrouter.ai/docs/guides/features/zdr).

Also set `data_collection:"deny"`, no tools/plugins/web search, exact provider allowlist and no fallback. Provider terms vary and no-training is not synonymous with no-retention. [Provider data policies](https://openrouter.ai/docs/guides/privacy/provider-logging).

OpenRouter says prompt/response content is not stored unless optional input/output logging is enabled; metadata such as tokens and latency is stored. Do not claim zero metadata collection. Do not alter the user's account settings implicitly; avoid enabling content logging or any debug/error path that writes the request. [OpenRouter data collection](https://openrouter.ai/docs/guides/privacy/data-collection).

## Bounded staged evaluation

These are project recommendations, not published model benchmarks:

1. Keep the already allocated $0.13 caps counted against $0.50; safely allocate no more than $0.37 in further caps. A $0.25 image/OCR evaluation cap leaves room for actual runtime verification. Do not reset counters after restart or on a retry.
2. First send a few authored clean/vertical/expressive crops and blank/texture controls. Validate schema, blank hallucination rate, image-token usage and provider identity before expanding. One bounded retry spends another reserved call; timeouts/cancellations do not prove zero charge.
3. Then use the audited private 78 labels in small batches of ≤4 crops. Gold is for scoring only, never included in the model prompt. Preserve exact and normalized CER separately, and review all mismatches rather than stripping troublesome quotes.
4. Compare all 8 eligible full pages separately. Crop OCR gains do not measure detector omissions, grouping, full-page spatial accuracy, text-role filtering, safe cleanup or Japanese→Vietnamese meaning.
5. Record per-call reservation, provider-reported cost, tokens, endpoint, elapsed time, finish reason and accepted IDs in private text/metrics artifacts. Keep image bytes, data URLs and full request objects out of artifacts/logs/exceptions. Stop on missing/ambiguous cost or token evidence before another paid batch.
6. Do not change the translation default or runtime image-upload mode based on catalog pricing or an authored pass. Require private-data evidence and an explicit image-upload setting with cost/privacy explanation; offline must still be mechanically unable to construct/send cloud-image requests.

Provider-side workspace/key guardrails are useful extra defense, but their ownership/accounting differs from a local harness ledger; a model rate filter alone is not a $0.50 authorization boundary. No management/account writes were performed in this research. [OpenRouter spend controls](https://openrouter.ai/docs/guides/best-practices/spend-controls).
