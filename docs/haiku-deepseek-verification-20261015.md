# Haiku 5.5 / DeepSeek V4.1 Flash: model-choice verification

Checked 2026-10-15 against public first-party sources. Research only: no paid inference, keys, private manga data, memories, model defaults or code were accessed/changed. Public availability is not proof that a specific account has a compatible route.

## Finding

**Haiku 5.5 is a credible leading candidate, not a verified manga-translation winner.** Both requested IDs are currently listed. Published prices do not establish Japanese–Vietnamese quality or our extension's end-to-end latency. Do not infer comparative performance from a mocked UI screenshot or a model name.

## Current prices and identities

USD per million tokens; standard, non-batch base rates unless stated:

| Service / model | Uncached input | Output | Qualification |
|---|---:|---:|---|
| OpenRouter `anthropic/claude-haiku-5.5` | 0.10 | 0.50 | Prompt up to 100K; higher tier 0.50 / 2.50 |
| OpenRouter `deepseek/deepseek-v4.1-flash` | 0.02376 | 0.72 | Catalogue base route, not a universal provider price |
| Anthropic direct `claude-haiku-5-5` | 0.10 | 0.50 | Up to 100K prompt; over 100K is 0.50 / 2.50 |
| DeepSeek direct `deepseek-flash` | 0.15 / 0.30 | 0.60 / 1.20 | Off-peak / peak respectively |

The [OpenRouter model catalogue](https://openrouter.ai/api/v1/models) lists canonical slugs `anthropic/claude-haiku-5.5-20261007` and `deepseek/deepseek-v4.1-flash-20260910`. Haiku has 1M context, 128K maximum completion and optional reasoning; DeepSeek has 1,048,576 context and optional reasoning. Both list structured-output support. Endpoint compatibility still needs checking rather than assuming every route implements every capability.

Direct Haiku pricing, text/image support and effort controls are documented in the [Anthropic model overview](https://platform.claude.com/docs/en/models/haiku-5-5/overview). Direct DeepSeek prices, cache rates, peak/off-peak schedule, default thinking and the `deepseek-flash` → V4.1 mapping are documented in [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/). Direct DeepSeek cache-hit input is 0.003 off-peak / 0.006 peak; it must not be compared with uncached Haiku input as though these are identical workloads.

**Vision correction:** current DeepSeek pricing marks Vision supported for `deepseek-flash` = V4.1 Flash. A community claim that DeepSeek Flash is text-only may describe an older version; it is not accurate for this current comparison. Neither model's image capability authorizes sending private manga images: this project's cloud translation path remains text-only.

**Cost inference:** Haiku is cheaper than direct DeepSeek for uncached short prompts at these published rates, but not universally cheaper on OpenRouter: Haiku's listed input price is higher while its output price is lower. Actual cost depends on provider/tier, cache, tokenization, input/output lengths, reasoning and accepted-result retries. Compare the paid route actually used, not one model's lowest input price with another model's standard endpoint.

## Speed and quality evidence

The [OpenRouter Haiku page](https://openrouter.ai/anthropic/claude-haiku-5.5) advertises provider-dependent latency/throughput observations, including a best-provider P50 latency of 0.40 s at inspection. The [DeepSeek page](https://openrouter.ai/deepseek/deepseek-v4.1-flash) showed 0.33 s best-provider P50. These live aggregates use different routes and workloads; they are neither controlled translation comparisons nor first accepted bubble/page latency. They cannot establish that either model is faster in this application.

No inspected official source supplies a controlled head-to-head Japanese–Vietnamese manga translation score covering our honorifics, directed pronouns, names, negation, expressive typography, context cutoffs and difficult OCR. General reasoning/coding rankings and publisher speed claims do not fill that gap. No new comparative inference was run for this note.

### Community numbers: what the primary benchmark actually says

The claimed 241.9 versus 222 tokens/s and ranks 2/182 versus 10/117 were not reproduced in today's live sources. [Artificial Analysis's Haiku Max page](https://artificialanalysis.ai/models/claude-haiku-5-5) currently shows 238.2 tokens/s, Intelligence Index 43 and class rank 2/176. Its rank rules compare proprietary models by blended price tier, but open-weight models by parameter-size class. Thus the two rank denominators are not a common field, even before snapshot-date differences. The [DeepSeek Max page](https://artificialanalysis.ai/models/deepseek-v4-1-flash) currently shows 176.6 tokens/s, Index 39 and class rank 7/116.

Throughput starts after the first chunk; it excludes waiting for that chunk. The same Haiku Max page reports TTFT 336.91 s, whereas DeepSeek Max reports 1.13 s. These are benchmark configurations, not forecasts for our short translation requests. They illustrate why output tokens/s alone is not live-reading speed. Max-effort quality results also cannot be assigned to reasoning-disabled translation. Use the same index version, effort, endpoint, prompt workload and measurement interval; then separately measure accepted translation latency in our pipeline.

### Standard, long-context and Flex are different comparisons

The Haiku 100K prompt boundary is a pricing-length tier, not a Flex discount; it is irrelevant only while our actual request stays below that boundary. [OpenRouter service tiers](https://openrouter.ai/docs/guides/features/service-tiers) define Standard as regular capacity, Flex as cheaper but slower/less available, and Priority as faster at a higher price. Batch/Flex headline discounts cannot support a Standard real-time promise. Record the endpoint and actual returned tier; do not assume every model/provider has every tier or let a cost comparison mix them.

## Discrepancy with yesterday's research

`cloud-model-research-20261014.md` already listed both IDs, but its OpenRouter DeepSeek floor examples (0.0441 / 0.63 and cached web 0.112 / 0.336) differ from today's catalogue/page base price (0.02376 / 0.72). Preserve them as dated observations, not current quotes or evidence of an error-free benchmark. Endpoint selection and pricing can change. Current endpoint sources: [Haiku](https://openrouter.ai/api/v1/models/anthropic/claude-haiku-5.5/endpoints), [DeepSeek](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints).

## Decision boundary

Recommendation: choose **Haiku 5.5 as the leading cloud candidate for the next measured translation comparison**, using Standard compatible routing and a short, bounded prompt with reasoning explicitly disabled where supported. Retain DeepSeek as a selectable comparator, not a silent paid fallback. This is a direction decision, not a claim that a benchmark passed or a production-default change.

Do not silently change saved readers' Offline/cloud consent. Before selecting a new production default, compare the same eligible text/context, compatible explicit routes and reasoning settings, then measure accepted translation quality, first bubble/page p50/p95, retries and billed cost. Preserve private benchmark rights and the remaining authorized spending ceiling. Current private OCR labels do not constitute independently reviewed Vietnamese translation gold.
