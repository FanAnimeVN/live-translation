# Context proposal: r13 delta check

Checked **2026-10-17, 13:09–13:12 UTC**. Scope: public, unauthenticated
documentation and existing implementation only. No key/account access, private
story upload, inference, charge, model download or default change. This note
does not rerun the already completed context implementation or establish manga
quality. Earlier findings remain in [the first-party review](context-multimodel-claims-primary-20261017.md)
and [the implementation checkpoint](context-memory-cloud-20261017.md).

## No newly demonstrated model winner

The proposal's model families are real in the consulted first-party sources.
It is not necessary to treat their names as fictitious, but their availability
does not verify the proposed Japanese-to-Vietnamese quality or 3.5-second
application median.

| Family | Rechecked owner documentation | Consequence |
| --- | --- | --- |
| Haiku 5.5 | Native ID `claude-haiku-5-5`; text/image input; $0.10/$0.50 per million input/output tokens for prompts up to 100,000, $0.50/$2.50 above that. | Credible translation candidate, not a proven manga winner. |
| DeepSeek V4.1 Flash | Native `deepseek-flash` currently serves **DeepSeek-V4.1-Flash-1017**, supports vision and thinking/non-thinking. Uncached input/output $0.15/$0.60 off-peak or $0.30/$1.20 peak. | Pin route/version when comparing; do not import the older text-only claim. |
| GLM-5.3-Flash | Native `glm-5.3-flash`; input/output $0.15/$0.50, cached input $0.03. Thinking cannot be disabled. | Input price alone does not establish the cheapest or fastest summary route. |

Sources: [Anthropic specifications](https://platform.claude.com/docs/en/models/haiku-5-5/overview),
[DeepSeek model/version/pricing](https://api-docs.deepseek.com/quick_start/pricing/),
[Z.ai Flash controls](https://docs.z.ai/guides/vlm/glm-5.3-flash),
[Z.ai prices](https://docs.z.ai/guides/overview/pricing).

Public OpenRouter records return the reviewed
[`anthropic/claude-haiku-5.5`](https://openrouter.ai/api/v1/models/anthropic/claude-haiku-5.5/endpoints),
[`deepseek/deepseek-v4.1-flash`](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints)
and [`z-ai/glm-5.3-flash`](https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints)
IDs. The web-tool retrieval of the separate DeepSeek `-1017` endpoint failed;
that is **not** evidence of nonexistence or permission to equate it with the
older base route.

No consulted source supplies a paired manga JA→VI evaluation for these routes.
Token-generation throughput, model positioning and input price are not complete
page latency or evidence that three paid stages beat one. DeepSeek Search/Fetch
also have separate request pricing; a low model-token rate does not include an
unrestricted wiki research service. [DeepSeek tool pricing](https://api-docs.deepseek.com/quick_start/pricing/).

## Architecture: retain the implemented safe subset

This is an implementation inference, not a provider guarantee:

- **Do not auto-import character profiles.** Wikipedia explicitly permits
  spoilers without warnings, including information outside plot sections.
  Names, kinship and allegiances can reveal future facts. Identity-only lookup
  with explicit consent is distinct from importing such facts into translation
  context. [Wikipedia's spoiler guideline](https://en.wikipedia.org/wiki/Wikipedia:Spoiler).
- **Cold start remains valid without wiki.** Manual story identity plus evidence
  from acknowledged read pages is sufficient. Do not guess relationships after
  an arbitrary 3–5 pages, or treat prefetch as reading.
- **Do not summarize Vietnamese alone.** Preserve original Japanese evidence,
  source IDs and chapter/page cutoffs. Translation and model paraphrases can
  be wrong; a question/request/promise is not a completed event. Unknown
  speakers remain unknown. Reader locks retain authority.
- **Do not overwrite one ever-growing lorebook.** Keep SQLite events and
  evidence canonical; bounded retrieval/Markdown is a cutoff-filtered view.
  Model summaries are reviewable proposals, not unqualified plot facts.
- **Do not turn background into automatic extra charges.** Independent summary
  model selection, separate cloud consent, exact new-read authorization,
  cancellation/stale-result protection and offline network prohibition remain
  necessary. Saving settings must not send a backlog.

These safeguards already exist in
[`metadata.py`](../companion/manga_live/metadata.py),
[`config.py`](../companion/manga_live/config.py),
[`prompts.py`](../companion/manga_live/prompts.py) and
[`host.py`](../companion/manga_live/host.py), as documented in the
[context checkpoint](context-memory-cloud-20261017.md). This inspection is not
a new test run or proof of semantic fidelity.

## Actionable delta

No additional wiki agent, default switch, GLM adapter or lorebook redesign is
justified by the repeated proposal. Continue the current real-source
detection/grouping/OCR work; evaluate context-summary fidelity independently
when a new attributable budget and reviewed references exist. Preserve
translation/summary route separation and the existing short evidence-grounded
context. Additional research metadata does not raise OCR exact-match or certify
release quality.
