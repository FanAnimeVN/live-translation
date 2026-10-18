# Small-budget cloud OCR challenger — primary-source check, 2026-10-17

Research and a **local, non-network cost calculation only**. No credential was
accessed, no inference request was sent, no private image/text was read for this
research, and no production setting or quality gate was changed. Existing
private reports were inspected only for aggregate model/config fields. Budget
authority is cumulative: the main ledger reports USD **0.003571** remaining of
the existing USD 0.50 consent; this note does not reconcile/release reservations
or authorize more spending. Billing guarantees remain covered by
[the existing reconciliation note](openrouter-billing-reconciliation-primary-20261017.md).

## One practical distinct candidate

Recommend **one bounded experiment with `qwen/qwen3.8-flash`**, not a new default.
It is already in `vision_ocr.MODELS`. The existing `cloud-image-*/report.json`
aggregate model fields contain Haiku 5.5 and Gemini 3.5 Flash-Lite image attempts,
but no Qwen3.8 Flash image attempt. Qwen is a different model family, rather than
a repeated Gemini request with a new prompt. This establishes novelty relative
to those recorded runs, not OCR quality.

The public catalogue advertises text/image/video input and text output, with
reasoning optional and on by default. Canonical model slug observed:
`qwen/qwen3.8-flash-20260826`; use the exact request ID above and record returned
model/provider evidence, not a moving `latest` alias. No claim is made that this
is an immutable provider checkpoint.
[OpenRouter catalogue](https://openrouter.ai/api/v1/models).

The public endpoints response lists Alibaba routes `alibaba` and
`alibaba/us-east-1`, each at **USD 0.15/M prompt and 0.47/M completion tokens**,
with a 1,000,000-token context and 131,072 maximum completion tokens. Both list
`max_tokens`, `reasoning`, `response_format`, and `structured_outputs`. No
separate `image` or `request` charge is listed in their pricing objects. These
are current listings, not a frozen quote or proof of account accessibility.
[Exact endpoint response](https://openrouter.ai/api/v1/models/qwen/qwen3.8-flash/endpoints).

No second candidate is proposed for this tiny remaining allowance: adding a
different model requires reviewing its image accounting, routing and contract,
and cannot justify silently weakening the existing allowlist or using a
zero-price/free route with unverified privacy/availability. This is not a
claim that no other suitable vision model exists.

## Image billing and reasoning controls

Alibaba's official vision documentation describes Qwen3.8-family image
accounting as scaled pixel area / (32 × 32), plus two image boundary tokens.
High-resolution processing allows up to 16,384 visual tokens; the documented
default pixel limit is 2,621,440, and the source is downscaled when required.
The documentation calls the formula an estimate and defers actual usage to the
API response. Do **not** calculate image tokens from PNG/base64 length, or assume
that OpenRouter forwards Alibaba-specific `max_pixels` /
`vl_high_resolution_images` controls.
[Alibaba image/video documentation](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/vision).

For this experiment retain the harness's **16,384 visual-token reserve per
image**, plus its existing text/schema and 2,048-token framing allowance. The
two boundary tokens fit within that framing allowance; this remains a
conservative local reservation, not an independent provider billing guarantee.
Do not lower it merely because the chosen crop is small.

Alibaba documents Qwen3.8 Flash as hybrid thinking, enabled by default, with
`enable_thinking=false` in its **direct** API.
[Alibaba thinking documentation](https://www.alibabacloud.com/help/en/model-studio/deep-thinking).
Use the already-reviewed OpenRouter request field
`reasoning: {"enabled": false, "exclude": true}` instead of copying a native
Alibaba-only field. `exclude` alone hides reasoning, not its bill. OpenRouter
documents reasoning as completion-billed and says it shares `max_tokens` on
most providers; a truncated/empty result is failed evidence, not permission for
an unbudgeted retry.
[OpenRouter reasoning controls](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

## Exact local reservation calculation

Used the unchanged `vision_ocr.request` crop rules/schema with one RAM-only
64 × 64 white synthetic image and ID `probe`, then passed that body to
`ImageBudget.amount`. No HTTP, Vault access, private image or model inference.
The reviewed endpoint prices were applied as
`provider.max_price = {prompt: 0.15, completion: 0.47, request: 0}`.

The current local calculation gives **3,335** text/schema/framing tokens,
alongside the unchanged **16,384** image-token allowance:

`reserve = ((16,384 + 3,335) × 0.15 + max_tokens × 0.47) / 1,000,000`

| Completion cap | One-request reservation, USD | Fits USD 0.003571 remaining? |
|---:|---:|---|
| 2,048 (existing Qwen default) | 0.00392041 | No |
| 512 | 0.00319849 | Yes, one request only |
| 256 | 0.00307817 | Yes, one request only |

**These are cap calculations, not measured charges.** Recalculate from the
actual complete request, ID, schema and latest rates before reserving. Use a
benchmark-only explicit completion cap; do not shrink OCR rules, remove safety
fields, reduce image reserve, alter labels, or change the product default to
make the budget pass. Select source detector proposals before seeing OCR/gold;
score against labels only after inference. A 512-token one-crop request provides
more JSON/output headroom than 256 while still fitting this example. Either can
truncate; no accuracy or latency inference follows from fitting the budget.

## Existing harness compatibility and route caveat

Inspected `companion/manga_live/cloud_ocr.py`, `vision_ocr.py`, and
`scripts/benchmark_cloud_ocr.py`. There is no separate `image_tokens.py` in the
searched `companion`/`scripts` tree; the reservation implementation is
`ImageBudget.amount` in the benchmark script.

- Qwen3.8 Flash passes the existing model allowlist and advertised parameter
  requirements. Its listed positive prompt/completion prices are within
  `price_caps` limits; absent `image`/`request` fields resolve to zero under the
  existing whitelist. A future nonzero separate image charge must fail closed.
- The current crop request uses `only: ["alibaba"]`, `data_collection: "deny"`,
  `zdr: true`, `allow_fallbacks: false`, `require_parameters: true`, strict JSON
  schema, and `temperature: 0`. The base provider slug can encompass both listed
  Alibaba endpoints; record the actual provider/route when returned.
- **The public endpoint catalogue does not prove eligibility under the combined
  ZDR, deny, account, price, and parameter restrictions.** OpenRouter documents
  ZDR and collection policy as routing filters and `require_parameters` as a
  compatibility filter. Preserve all filters. An unavailable compliant route is
  a failed attempt, not permission to relax privacy, switch model, retry, or
  release its reservation automatically.
  [OpenRouter routing controls](https://openrouter.ai/docs/guides/routing/provider-selection),
  [ZDR semantics](https://openrouter.ai/docs/guides/features/zdr).

This note makes **no Japanese OCR accuracy, end-to-end speed, 78/78, model
superiority, or release-readiness claim**. The single crop would be an isolated
development probe; promotion still requires the full paired coverage and
regression evidence.
