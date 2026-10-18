# Japanese → Vietnamese manga: cloud benchmark sources

Checked **2026-10-12** against primary sources. Research only: no paid inference requests, API-key access, dataset downloads, or application changes. Prices below are USD per **1 million text tokens**, input / output, before account funding fees and taxes. These are observed listings, not fixed quotes or measurements of translation quality.

## Models to measure

The request IDs were checked in the live [OpenRouter model catalogue](https://openrouter.ai/api/v1/models). Use explicit IDs and record the returned model, provider, canonical slug, reasoning usage and actual billed cost for every run; moving `~…-latest` aliases are unsuitable for reproducible comparisons.

| Request model ID | Observed input / output price | Context / maximum output tokens | Proposed test setting |
| --- | --- | --- | --- |
| `deepseek/deepseek-v4.1-flash` | **$0.0333 / $0.1332**, Baidu Qianfan promotional listing; catalogue base **$0.15 / $0.60** | 1,048,576 / 393,216 | Thinking disabled |
| `qwen/qwen3.8-flash` | **$0.15 / $0.47** | 1,000,000 / 131,072 | Thinking disabled; verify returned usage |
| `tencent/hy-mt2-30b-a3b` | **$0.074 / $0.295** | 8,192 / 4,096 | Translation baseline; no reasoning control advertised |
| `tencent/hy-mt2-7b` | **$0.074 / $0.295** | 8,192 / 4,096 | Smaller translation baseline |
| `google/gemini-3.1-flash-lite` | **$0.25 / $1.50**, Standard | 1,048,576 / 65,536 | `minimal` |
| `google/gemini-3.5-flash-lite` | **$0.30 / $2.50**, Standard | 1,048,576 / 65,536 | `minimal`; thinking mandatory |
| `google/gemini-2.5-flash-lite` | **$0.10 / $0.40** | 1,048,576 / 65,535 | Thinking off; legacy comparison only |

Price sources: [DeepSeek V4.1 Flash](https://openrouter.ai/deepseek/deepseek-v4.1-flash), [Qwen3.8 Flash](https://openrouter.ai/qwen/qwen3.8-flash), [Hy-MT2-30B-A3B](https://openrouter.ai/tencent/hy-mt2-30b-a3b), [Hy-MT2-7B](https://openrouter.ai/tencent/hy-mt2-7b), [Gemini 3.1 Flash-Lite](https://openrouter.ai/google/gemini-3.1-flash-lite), [Gemini 3.5 Flash-Lite](https://openrouter.ai/google/gemini-3.5-flash-lite), [Gemini 2.5 Flash-Lite](https://openrouter.ai/google/gemini-2.5-flash-lite). Context, output limits and reasoning metadata: [live catalogue](https://openrouter.ai/api/v1/models).

DeepSeek's direct API now names this generation `deepseek-flash` = **DeepSeek-V4.1-Flash**; it supports thinking and non-thinking and defaults to thinking. This is a direct-provider ID, not the OpenRouter request ID. [DeepSeek pricing/model table](https://api-docs.deepseek.com/quick_start/pricing/)

Provider choice matters: DeepSeek's catalogue includes time-based **$0.30 / $1.20** overrides, while the model page shows the much lower promotional provider price. Google 3.1 Flex endpoints list **$0.125 / $0.75**, separately from Standard, and Priority/region endpoints have other prices. Keep service tier and endpoint in the result; do not attribute the lowest displayed price to every route. [DeepSeek catalogue](https://openrouter.ai/api/v1/models), [DeepSeek provider prices](https://openrouter.ai/deepseek/deepseek-v4.1-flash), [Google endpoint metadata](https://openrouter.ai/api/v1/models/google/gemini-3.1-flash-lite/endpoints)

Tencent's first-party model card lists **Japanese and Vietnamese**, translation among 33 languages, and context/glossary/style-guided translation. This makes Hy-MT2 a relevant specialist comparison; it does not establish superiority on manga. [Tencent model card](https://huggingface.co/tencent/Hy-MT2-7B)

Lifecycle discrepancy: OpenRouter currently reports `expiration_date: 2026-10-20` for Gemini 2.5 Flash-Lite. Google's own page currently says no shutdown date is announced for 2.5 Flash/Lite and limits access to existing users; it recommends newer models for new projects. Treat this as an OpenRouter availability risk, not a confirmed Google-wide shutdown. [OpenRouter catalogue](https://openrouter.ai/api/v1/models), [Google deprecations](https://ai.google.dev/gemini-api/docs/deprecations)

Optional extra: `z-ai/glm-5.3-flash` is listed at **$0.0232 / $1.20**, but its catalogue marks thinking mandatory, so low input price alone does not make it the cheapest interactive translator. [Model pricing](https://openrouter.ai/z-ai/glm-5.3-flash), [catalogue](https://openrouter.ai/api/v1/models)

## Reasoning, JSON and routing constraints

- For models permitting it, use OpenRouter's `reasoning: {"enabled": false}`. `reasoning.exclude: true` and legacy `include_reasoning: false` only hide reasoning; they do not turn it off. Reasoning is billed as output and can consume the completion budget. Mandatory models reject `effort: "none"`. [OpenRouter reasoning](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
- DeepSeek's direct API disables thinking with `thinking: {"type": "disabled"}`. Do not copy that provider-specific field into an OpenRouter request without confirming its mapping. In DeepSeek thinking mode, temperature and presence/frequency penalties are ignored. [DeepSeek thinking controls](https://api-docs.deepseek.com/guides/thinking_mode/)
- Google documents `minimal` for Gemini 3.1/3.5 Flash-Lite and explicitly says it **does not guarantee zero thinking**. Use minimal as a separate condition from a true non-thinking test. [Google thinking levels](https://ai.google.dev/gemini-api/docs/generate-content/thinking)
- Prefer `response_format.type: "json_schema"` with a strict schema and `provider.require_parameters: true`; route only to compatible endpoints. Validate bubble IDs, counts and schema locally as well. The model catalogue advertises structured outputs for the table's models, but endpoint support still matters. [OpenRouter structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs)
- DeepSeek's native documented fallback is `json_object`: include “json” and an example in the prompt, allow enough output tokens, and handle occasional empty content. Valid JSON alone does not guarantee the requested schema. [DeepSeek JSON mode](https://api-docs.deepseek.com/guides/json_mode/)

## Data handling

OpenRouter says prompt/completion storage is opt-in, and upstream providers have their own training/retention policies. Do not infer a policy from the model owner's name. Use `provider.data_collection: "deny"` and, when required, `provider.zdr: true`; an unavailable compliant endpoint is a failed test, not permission to relax the policy. [OpenRouter collection policy](https://openrouter.ai/docs/guides/privacy/data-collection), [provider policies](https://openrouter.ai/docs/guides/privacy/provider-logging), [routing controls](https://openrouter.ai/docs/guides/routing/provider-selection)

ZDR applies to inference endpoints, not every optional tool/plugin; OpenRouter permits in-memory implicit caching under ZDR. Its current documentation says enforcing Google ZDR excludes AI Studio routes while Vertex remains eligible. Recheck actual endpoint eligibility immediately before a run. [OpenRouter ZDR](https://openrouter.ai/docs/guides/features/zdr)

## Manga109 access and benchmark rights

The [official project](https://manga109.github.io/manga109-project-website/en/index.html) contains **109 volumes**; the commercially permitted research subset **Manga109-s contains 87**. The official [annotations page](https://manga109.github.io/manga109-project-website/en/annotations.html) publicly displays a visual example and XML excerpt, including text-region coordinates and Japanese transcription. This verifies a public preview, not an unrestricted benchmark download or Vietnamese reference translations.

Both official Hugging Face datasets are gated: sign in, accept the licence, describe the intended use, and await approval. Manga109 requires an academic institutional email and academic, non-commercial use; companies/general users are directed to Manga109-s. The published processing estimate is several days to a week. [Manga109 access/licence](https://huggingface.co/datasets/hal-utokyo/Manga109), [Manga109-s access/licence](https://huggingface.co/datasets/hal-utokyo/Manga109-s)

Manga109-s permits ML/image-processing experiments and commercial use of experiment results, including published pretrained models with acknowledgement. It still forbids dataset redistribution, selling dataset images alongside results, and treating copied/modified manga images as products. Published whole-page examples are capped at **20% of each volume**, with attribution/citation requirements. A commercial research licence is not permission to ship translated manga pages as product content. [Manga109-s terms](https://huggingface.co/datasets/hal-utokyo/Manga109-s)

**Interpretation requiring confirmation:** the terms prohibit transfer/redistribution to third parties and the inspected pages do not explicitly grant cloud-processor access. Consequently, permission to send these images or extracted copyrighted text to OpenRouter is unverified. Use author-owned/explicitly cloud-cleared samples for cloud tests; use Manga109 locally only under its accepted terms. Do not commit dataset content. The source provides Japanese annotations, so Vietnamese gold translations and directed pronoun rules still need qualified human annotation. [Manga109 terms](https://huggingface.co/datasets/hal-utokyo/Manga109), [Manga109-s terms](https://huggingface.co/datasets/hal-utokyo/Manga109-s), [annotation structure](https://manga109.github.io/manga109-project-website/en/annotations.html)

## Recommended measurement design

Start with DeepSeek V4.1 Flash non-thinking, Qwen3.8 Flash non-thinking, Hy-MT2-30B-A3B/7B, and Gemini 3.1/3.5 Flash-Lite minimal. Keep 2.5 only as an available legacy baseline. This is a test shortlist, not a quality ranking.

Use identical, rights-cleared Japanese bubble text and identical preceding-page context; score OCR separately from translation. Include omitted subjects, directed Vietnamese pronouns, names, slang, onomatopoeia, ambiguous speakers and chapter/page cutoffs. Blind human review should measure meaning, natural Vietnamese, pronoun consistency, unsupported additions and omitted bubbles. Record p50/p95 end-to-end latency, time to first token, JSON/schema failures, retries, refusals, tokens and actual cost per accepted page. Repeat with pinned providers before selecting a default. No generic coding/intelligence benchmark establishes Japanese → Vietnamese manga translation accuracy.

## Private pilot recorded on 2026-10-13

Two passes each used six author-created groups (18 short utterances) per model, through OpenRouter. No manga images, dataset labels or reader memory were sent. The first pass used prompt v8/default routing; the second used v9/latency routing with parameter enforcement. Both retained `data_collection: deny`. Individual route price ceilings and two-attempt token reservations were checked before generation. The key was ephemeral and not written to the reports or plaintext files.

| Model | First pass median group response | Second pass median group response | Second pass reported cost, 6 groups |
|---|---:|---:|---:|
| DeepSeek V4.1 Flash | 2,832 ms | 1,802 ms | USD 0.001766964 |
| Gemini 3.5 Flash-Lite | 1,874 ms | 1,495 ms | USD 0.0033245 |

Both models returned accepted schema/contract results in 6/6 groups each pass. This is **not 100% translation accuracy**. DeepSeek correctly retained compulsion in the tested causative-passive, potion counter, honorifics and directed reader rules. Gemini's first pass invented male `anh–em` for an unidentified senpai; the second avoided a single gender but produced an awkward `anh/chị` alternative. These reports precede the v10 placeholder guard and v11 directed-request guard: unit tests prove their repair contracts, not a new measured cloud accuracy result. The guards are deliberately narrow, not a validator for all Vietnamese kinship.

For private beta, prefer testing DeepSeek with latency routing before changing to Gemini solely for speed. Keep offline 1.8B as an unqualified beta option: the real CPU recheck still changed “being made to go” into permission. A subsequent local 7B v10 pilot fixed that sample but still reversed the recipient in a confirmed sibling request and used the wrong medicine counter; it took 24–35 seconds per group of three utterances. It is not promoted as the live default.

The original 7B report used semantic checks v2 and passed 2/3 narrow groups. Review exposed a missing first-clause role check; v3 catches it, leaving only the scope group passing these specific guards. The raw v2 report has not been rewritten to pretend it used v3. This is a small known-error audit, not blind Japanese–Vietnamese grading. Artifact: `artifacts/semantic-7b-v10-pilot.json`.

This is sequential pilot evidence, not a controlled routing-only A/B: prompt, cache hits, provider and time also changed. These timings exclude OCR/overlay, contain too few samples for a reliable p95 and do not prove real-time reading. Cost totals are reported `usage.cost`, not an independently reconciled account bill. Total reported cost of the two passes: **USD 0.009390064**.

Private ignored artifacts: `artifacts/cloud-benchmark.json`, `artifacts/cloud-latency-pilot/cloud-benchmark.json`, `artifacts/semantic-baseline-lifetime-check.json`. Future runs also record prompt version, request-body hash and requested routing; HTTP headers/API keys are never recorded. [OpenRouter routing controls](https://openrouter.ai/docs/guides/routing/provider-selection)
