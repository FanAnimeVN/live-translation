# Context proposal: delta-only check

Checked **2026-10-17, 11:59 UTC**. This is an addendum to
[the primary-source check](context-multimodel-claims-primary-20261017.md)
and [the revalidation](context-model-claims-revalidation-20261017.md), not a
new model comparison. Only public documentation/metadata was requested; no
key, private data, inference, charge or product change was involved.

## Decision: no evidence to change model defaults

The repeated proposal supplies no new first-party Japanese-to-Vietnamese manga
evaluation or application latency evidence. Native IDs remain
`claude-haiku-5-5`, `deepseek-flash` (currently
**DeepSeek-V4.1-Flash-1017**), and `glm-5.3-flash`. Short-tier Haiku remains
$0.10/$0.50 per million input/output tokens; current DeepSeek Flash remains
$0.15/$0.60 off-peak or $0.30/$1.20 peak; GLM Flash remains $0.15/$0.50.
[Anthropic specifications](https://platform.claude.com/docs/en/models/haiku-5-5/overview),
[DeepSeek model/version/prices](https://api-docs.deepseek.com/quick_start/pricing/),
[Z.ai prices](https://docs.z.ai/guides/overview/pricing).

The checked OpenRouter endpoints still identify
`anthropic/claude-haiku-5.5`, `deepseek/deepseek-v4.1-flash` and
`z-ai/glm-5.3-flash`. A web-tool retrieval failure for the separate DeepSeek
`-1017` endpoint is **not** evidence that model is absent; its earlier catalog
snapshot must not be silently replaced with the older base route.
[Haiku endpoint](https://openrouter.ai/api/v1/models/anthropic/claude-haiku-5.5/endpoints),
[DeepSeek base endpoint](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints),
[GLM endpoint](https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints).

## Additional implementation cautions, not a new benchmark

- Haiku's official page says its newer tokenizer uses approximately **30% more
  tokens than Haiku 4.5 for the same text**. This is not a comparison against
  DeepSeek or GLM. Compare billed tokens for the actual workload, not identical
  token-count assumptions across tokenizers. It also says to omit native
  `temperature`, `top_p` and `top_k`; an adapter cannot assume a legacy sampling
  request is compatible. The checked OpenRouter Haiku endpoint does not list
  those parameters as supported.
  [Anthropic specifications and compatibility notes](https://platform.claude.com/docs/en/models/haiku-5-5/overview),
  [OpenRouter supported parameters](https://openrouter.ai/api/v1/models/anthropic/claude-haiku-5.5/endpoints).
- GLM Flash thinking still cannot be disabled; **200 tokens/s is advertised for
  FlashX**, not a measured complete manga-page latency for Flash. Its lower
  input price cannot establish cheaper summaries once reasoning/output and
  any extra summary call are counted.
  [Z.ai Flash/FlashX controls](https://docs.z.ai/guides/vlm/glm-5.3-flash).
- DeepSeek documents separate Search/Fetch billing. Token prices do not grant
  free automatic wiki research. Its native Flash now supports vision; the old
  text-only comparison is stale.
  [DeepSeek features and tool prices](https://api-docs.deepseek.com/quick_start/pricing/).

Therefore retain independently selectable translation/summary routes and the
existing evidence/cutoff/consent rules. Do not infer a universal 3.5-second manga
median, superior Vietnamese style, spoiler-safe wiki profiles, or a cheaper
three-model pipeline from these metadata. No new evidence here resolves those
application-specific questions; they still require the planned controlled
evaluation, not another default switch.
