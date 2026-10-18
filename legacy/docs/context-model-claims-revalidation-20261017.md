# Multi-model context proposal: additive revalidation

Verified **2026-10-17, approximately 11:36 UTC** against public first-party
documentation/catalogs. Addendum to
[the earlier primary-source check](context-multimodel-claims-primary-20261017.md)
and [the implemented context checkpoint](context-memory-cloud-20261017.md),
not another implementation or benchmark. No authenticated endpoints, keys,
private text/images, inference, paid requests or default changes were involved.

## What remains valid, and what the proposal overstates

| Claim | Revalidation |
| --- | --- |
| Haiku 5.5 exists and has inexpensive short-prompt pricing | Confirmed: native ID `claude-haiku-5-5`; OpenRouter ID `anthropic/claude-haiku-5.5`, catalog snapshot `20261007`. |
| Haiku is the best manga Japanese-to-Vietnamese translator, median 3.5 seconds | Not established by the consulted sources. Advertised latency-sensitive positioning and public provider statistics are not this application's semantic evaluation or end-to-end latency. |
| DeepSeek V4.1 Flash is available | Confirmed, but identify the snapshot: the native `deepseek-flash` alias currently serves **DeepSeek-V4.1-Flash-1017**. The OpenRouter base ID and `deepseek/deepseek-v4.1-flash-1017` are distinct catalog records; do not equate them silently. |
| DeepSeek Flash is text-only | Not true of the current native Flash: official documentation lists vision. Legacy native V4 Flash aliases are retired and rerouted to the current model. |
| GLM-5.3-Flash is a cheap background-summary candidate | Available, but thinking **cannot be disabled**. Low input pricing alone does not establish total cost, faithful summaries or bounded completion latency. FlashX is separate. |

Identity sources: [Anthropic specifications](https://platform.claude.com/docs/en/models/haiku-5-5/overview),
[DeepSeek current model/version table](https://api-docs.deepseek.com/quick_start/pricing/),
[Z.ai Flash controls](https://docs.z.ai/guides/vlm/glm-5.3-flash),
[OpenRouter public catalog](https://openrouter.ai/api/v1/models).

## Price and timing details that affect selection

USD per million tokens, standard owner pricing; not blended route minima:

| Model | Uncached input / output | Caveat |
| --- | --- | --- |
| Haiku 5.5 | $0.10 / $0.50 | $0.50 / $2.50 for prompts over 100,000 tokens. |
| Current DeepSeek Flash | $0.15 / $0.60 off-peak; $0.30 / $1.20 peak | Weekday peak periods: 01:00–04:00 and 06:00–10:00 UTC, excluding Chinese public holidays. |
| GLM-5.3-Flash | $0.15 / $0.50 | Cached input $0.03; mandatory thinking. Flash is not free. |

Sources: [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing),
[DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/),
[Z.ai pricing](https://docs.z.ai/guides/overview/pricing).

Anthropic counts cache reads/writes in the prompt-length threshold. OpenRouter
still advertises `min_prompt_tokens:100000`, whereas Anthropic prose says
**over** 100,000: reserve the higher rate at the exact boundary. The checked
Haiku endpoints report null recent-latency fields and do not support implicit
caching. Repeating a short prompt is not proof of a discounted cache hit.
[Haiku endpoint records](https://openrouter.ai/api/v1/models/anthropic/claude-haiku-5.5/endpoints).

Illustration, not a bill or cross-tokenizer benchmark: at 3,000 uncached input
and 500 billable output tokens, these owner rates give $0.00055 for short-tier
Haiku, $0.00070 for GLM Flash and $0.00075 for off-peak DeepSeek. Actual token
counts, reasoning and routing differ. A separate summary model is not inherently
cheaper. Excluding reasoning from the response does not stop its generation or
billing. [OpenRouter reasoning accounting](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

## Bounded recommendation

Retain independent translation/summary selection already implemented; do not
add a third research agent merely to match the proposed diagram. Haiku is a
credible price/latency candidate, not a proven quality winner. Keep GLM as a
challenger until its complete billed output and evidence fidelity are measured.
Do not choose from changing general-intelligence rankings or advertised tok/s.

For this product, compact memory must retain Japanese evidence IDs and read
cutoffs, not turn a guess about relationships into a fact. Searching external
character profiles before reading has no evidenced spoiler boundary. These are
product constraints/inferences, not model guarantees; retain the existing
identity-only, explicit-consent wiki path and cold-start read-evidence flow.
No new paid evaluation is authorized by this note, and none of these metadata
checks improves the measured OCR baseline or proves release quality.
