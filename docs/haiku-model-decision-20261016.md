# Haiku 5.5: translation decision checkpoint

Checked 2026-10-16. Public official documentation and existing authored-test metrics only. No paid requests, secrets or private manga data accessed; no default/code/configuration changed.

## What is actually available

Claude Haiku 5.5 is real and active, released 2026-10-07. Anthropic's API ID is `claude-haiku-5-5`; OpenRouter uses `anthropic/claude-haiku-5.5`, with the dated canonical slug `anthropic/claude-haiku-5.5-20261007`. Text and image input produce text; vision support is not proof of Japanese manga OCR or translation quality. [Anthropic overview](https://platform.claude.com/docs/en/models/haiku-5-5/overview), [OpenRouter model](https://openrouter.ai/anthropic/claude-haiku-5.5).

Official standard pricing is **$0.10 input / $0.50 output per million tokens** for prompts up to 100,000 tokens; longer prompts use **$0.50 / $2.50**. Input-cache hits and writes have different rates. These community-quoted Haiku prices are therefore supported, but they do not establish per-page cost or a universal cost advantage over every DeepSeek route. [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing).

For the relevant OpenRouter route, the public endpoint listing advertises `google-vertex/global` at $0.10/$0.50; regional Vertex routes list $0.11/$0.55. Other endpoints exist, and availability to a particular account is not guaranteed by a public listing. The catalog's long-context override begins at `min_prompt_tokens:100000`, so keep manga requests safely below this boundary rather than depending on exact-boundary interpretation. [Actual Haiku endpoints](https://openrouter.ai/api/v1/models/anthropic/claude-haiku-5.5/endpoints).

Adaptive thinking defaults on. It **can be disabled at low, medium or high effort**, but not xhigh/max. Native `thinking:{type:"disabled"}` is supported; old manual `budget_tokens` is not. Omit `temperature`, `top_p` and `top_k` rather than sending unsupported sampling values. Our existing adapter already disables reasoning and omits sampling for Haiku. [Anthropic thinking](https://platform.claude.com/docs/en/build-with-claude/thinking), [Haiku migration](https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide), [local adapter](../companion/manga_live/cloud_models.py).

## What our translation evidence says

Existing authored text-only pilot: `artifacts/cloud-mvp-model-pilot-20261016/cloud-benchmark.json`, prompt `ja-vi-v22-directed-wait-no-stack`. Four case groups/model, one repeat; no new calls made here.

| Model | Accepted / narrow checks | Median response | Provider-reported cost, four groups | Actual route |
| --- | --- | ---: | ---: | --- |
| Haiku 5.5 | 4/4; 4/4 | 2.276 s | $0.001389400 | Anthropic |
| DeepSeek V4.1 Flash | 4/4; 4/4 | 1.578 s | $0.001160232 | Together |
| Gemini 3.5 Flash-Lite | 4/4; 4/4 | 2.183 s | $0.002899900 | Google AI Studio |
| Qwen3.8 Flash | 4/4; 3/4 | 2.938 s | $0.000866778 | Alibaba |

These are **API text response times**, not first-bubble/browser/page times, and not reliable p95. Haiku was not faster or cheaper than DeepSeek in this particular pilot. DeepSeek had 3,072 cache-hit prompt tokens; Haiku had none. Token counts/output lengths and routes also differed. This is not a controlled model-only A/B or human blind translation ranking. All four-group checks passing does not certify natural Vietnamese, stable pronouns or the ≤2% serious-error target. [Existing demo evidence summary](mvp-cloud-demo-20261016.md).

The pilot used an Anthropic first-party route for Haiku, whereas the new image tests require ZDR-compatible routing. Do not relabel that old latency as the current Vertex route's measurement. Endpoint price/privacy/caching conditions need to accompany any fresh comparison.

OpenRouter lists many DeepSeek V4.1 endpoints with different prices; the Together endpoint used by this pilot lists $0.30/$1.20, while other routes have materially different rates. Thus a community claim about a particular DeepSeek peak/off-peak price must not be applied to every router request, model revision or cached workload. [DeepSeek route prices](https://openrouter.ai/deepseek/deepseek-v4.1-flash).

## OCR is a separate decision

The later Haiku image-crop run stopped at 36/78 labels; its OCR errors and full-page localization failures do **not** invalidate its translation ability. Conversely, four exact authored OCR crops do not prove better manga translation. The separate Gemini OCR option can be paired with Haiku text translation; choosing OCR does not require choosing the same translation model. [Separate OCR findings](cloud-image-ocr-results-20261016.md).

## Recommendation

**Keep Haiku as a first-class, serious translation option; do not call it the proven winner yet.** The current default in code is still DeepSeek V4.1 Flash. The recorded evidence explains retaining that baseline, not rejecting Haiku or disputing its verified price.

If the reader explicitly chooses Haiku for the demo, using it as that reader's selected translation model is reasonable and should persist; label the choice honestly, preserve locks/context and do not silently change existing saved provider/model choices. A global default promotion should follow a matched-route comparison on permissioned manga dialogue with reviewed Vietnamese references, ambiguity/pronoun/negation checks, repeated latency and cost per accepted group. OCR, grouping, UI and cold detector load must be measured separately. No additional benchmark spending is authorized by this note and no budget is reset.
