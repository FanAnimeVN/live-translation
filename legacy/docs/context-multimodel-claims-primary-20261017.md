# Context model claims: primary-source recheck — 2026-10-17

Checked public metadata at approximately **09:25 UTC**. Research only: no keys,
Vault, private manga, reader memories, authenticated/account endpoints, inference,
paid requests, model downloads, or product/default changes. The shell initially
denied public GET networking; the same unauthenticated metadata GETs succeeded
with network permission. This is not an inference retry.

## Conclusion

All three proposed model families are publicly listed. Haiku 5.5's inexpensive
short-prompt tier is real. The evidence does **not** establish that any of these
models is the best Japanese-to-Vietnamese manga translator, produces faithful
chapter summaries, or achieves a 3.5-second median in this application. A separate
research model, translation model, and background summary model is a plausible
architecture; it is not a measured quality improvement or permission for extra
cloud work. Keep existing defaults until the repository's consent, private
ground-truth evaluation, cost, and latency requirements are satisfied.

## Exact identities and advertised availability

| Proposed role | OpenRouter request ID | Current `canonical_slug` | Provider-native ID |
| --- | --- | --- | --- |
| Wiki research | `deepseek/deepseek-v4.1-flash` | `deepseek/deepseek-v4.1-flash-20260910` | `deepseek-flash` now serves **DeepSeek-V4.1-Flash-1017** |
| New DeepSeek snapshot | `deepseek/deepseek-v4.1-flash-1017` | `deepseek/deepseek-v4.1-flash-20261017` | Same current native alias above |
| Translation | `anthropic/claude-haiku-5.5` | `anthropic/claude-haiku-5.5-20261007` | `claude-haiku-5-5` |
| Background summaries | `z-ai/glm-5.3-flash` | `z-ai/glm-5.3-flash-20260826` | `glm-5.3-flash` |

Sources: [public OpenRouter catalog](https://openrouter.ai/api/v1/models),
[DeepSeek model/version table](https://api-docs.deepseek.com/quick_start/pricing/),
[Haiku specifications](https://platform.claude.com/docs/en/models/haiku-5-5/overview),
[Z.ai model documentation](https://docs.z.ai/guides/vlm/glm-5.3-flash).
Do not silently equate the older OpenRouter base slug with the new native
DeepSeek alias. These are public advertisements, not proof of account access,
route privacy eligibility, or successful execution.

## Advertised prices and cache caveats

USD per **one million tokens**, excluding any search/tool fees:

| Exact OpenRouter endpoint `tag` | Input / output | Cache read | Conditions |
| --- | --- | --- | --- |
| Haiku `google-vertex/global` | $0.10 / $0.50 | $0.01 | Short prompt tier |
| Same Haiku endpoint, higher tier | $0.50 / $2.50 | $0.05 | `pricing.overrides.min_prompt_tokens:100000` |
| DeepSeek base model, `deepseek` | $0.15 / $0.60 | $0.003 | Off-peak; weekend rate at this check |
| Same DeepSeek endpoint, peak | $0.30 / $1.20 | $0.006 | Weekday time overrides |
| GLM `z-ai/fp8` | $0.15 / $0.50 | $0.03 | No prompt-length tier in this endpoint snapshot |

Sources: [Haiku endpoint records](https://openrouter.ai/api/v1/models/anthropic/claude-haiku-5.5/endpoints),
[DeepSeek endpoint records](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints),
[GLM endpoint records](https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints).
Other providers advertise different rates, quantization, limits and supported
parameters; compare a whole eligible endpoint, not minima from different routes.
For example, the checked GLM `open-inference/fp4` endpoint lists
$0.0293 input / $0.4182 output / $0.0094 cache read, which is distinct from the
owner-operated `z-ai/fp8` endpoint. Neither cheaper route establishes quality.

Anthropic's prose says the lower tier applies **up to** 100,000 prompt tokens
and the higher tier **over** 100,000. All input counts toward that threshold,
including cache reads and writes; a cache hit does not retain the lower tier
for a longer request. OpenRouter's explicit `min_prompt_tokens:100000` leaves
an exact-boundary discrepancy: reserve the higher rate at that boundary until
resolved. [Anthropic pricing and threshold definition](https://platform.claude.com/docs/en/about-claude/pricing).

The checked Haiku endpoint lists 5-minute/1-hour cache writes of $0.125/$0.20
below the threshold and $0.625/$1.00 in the higher tier, and
`supports_implicit_caching:false`. Cache discounts therefore must not be
assumed from ordinary repeated requests. Haiku's minimum cacheable prefix is
512 tokens; shorter prefixes run without caching.
[Haiku endpoint pricing](https://openrouter.ai/api/v1/models/anthropic/claude-haiku-5.5/endpoints),
[Anthropic cache requirements](https://platform.claude.com/docs/en/build-with-claude/prompt-caching).

DeepSeek's direct API currently uses the same off-peak/peak rates above.
Peak is 01:00–04:00 and 06:00–10:00 UTC on weekdays excluding Chinese public
holidays. Native Search and Fetch are separately billed APIs; their advertised
rate is $0.75 per 1,000 successful requests each, with a documented temporary
exception for named integrations. Do not assume token pricing includes wiki
retrieval. [DeepSeek current pricing](https://api-docs.deepseek.com/quick_start/pricing/).
Z.ai's native Flash price is also $0.15/$0.50, with $0.03 cached input;
**Flash is not free**. FlashX is a separate, more expensive model.
[Z.ai pricing](https://docs.z.ai/guides/overview/pricing).

## Reasoning and latency are material to the proposal

The current catalog marks Haiku thinking optional, default effort `medium`;
DeepSeek thinking optional, enabled by default at `high`; GLM thinking
**mandatory**, enabled by default at `max`, supporting `max/high/low`.
[OpenRouter catalog](https://openrouter.ai/api/v1/models).
Z.ai independently confirms that Flash thinking cannot be disabled. Its
200-token/second claim specifically concerns **FlashX**, not a manga-page
latency guarantee. [Z.ai Flash/FlashX controls](https://docs.z.ai/guides/vlm/glm-5.3-flash).
Hiding reasoning using `exclude:true` does not stop its generation or billing;
reasoning commonly shares the output-token budget, and can exhaust it before
visible text appears. [OpenRouter reasoning accounting](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

The inspected endpoint APIs expose null 30-minute latency/throughput fields for
all three models. Separately, OpenRouter's public Haiku page shows changing
provider P50 statistics: at this check, standard Vertex displayed 1.98 seconds
latency and 166 tokens/second, Anthropic 0.86 seconds and 150 tokens/second.
These are provider observations, not this extension's result.
[Haiku provider statistics](https://openrouter.ai/anthropic/claude-haiku-5.5).
OpenRouter distinguishes time to first token from decoding time; our complete
page additionally includes capture, OCR, context, validation and rendering.
[OpenRouter latency definition](https://openrouter.ai/docs/guides/best-practices/latency-and-performance).
No consulted first-party source establishes the proposed **3.5-second median
Japanese-to-Vietnamese manga translation** or our p95 acceptance targets.
Anthropic's launch evaluations cover broader knowledge/coding/computer-use
tasks, not that manga workload.
[Haiku launch evaluations](https://www.anthropic.com/claude-haiku-5-5).

## Wiki facts and summaries need independent cutoff evidence

Wikipedia explicitly allows plot spoilers without warnings, including in
character descriptions, leads, infoboxes and categories.
[Wikipedia's own spoiler guideline](https://en.wikipedia.org/wiki/Wikipedia:Spoiler).
Wikidata statements have optional references and qualifiers; this does not
guarantee a chapter/page reveal boundary for every value.
[Wikidata statement model](https://www.wikidata.org/wiki/Help:Statements).

Architecture inference: extracting only names, relationships or profiles can
still import a later identity, kinship or allegiance. Treat external research
as reviewable candidates with source revision, quotes and an evidenced reveal
cutoff; absence of cutoff evidence means ineligible for the live translation
context. Generate incremental summaries only from eligible, already-read
evidence, carry evidence IDs/cutoffs forward, preserve unknown speakers and
reader-locked choices, and reject summaries that introduce unsupported facts.
A model's large context window or summarization marketing does not supply
those guarantees. No real-manga quality or application latency was measured
by this research.
