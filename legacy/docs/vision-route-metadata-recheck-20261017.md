# Vision route metadata recheck — 2026-10-17

Checked public metadata at approximately **01:22 UTC**. Read-only research: no
Vault/key, private dataset/artifact, authenticated API, inference, image upload,
model download, account write or paid request. The first public Gemini fetch
was blocked by the shell sandbox; the same unauthenticated GET succeeded with
network permission. This is not an inference retry. No request policy, model,
default or product code was changed.

Read `companion/manga_live/vision_ocr.py`, `cloud_ocr.py`, the benchmark's
`price_caps`, and [the previous crop-challenger note](cloud-crop-challenger-primary-20261017.md)
before checking the sources below.

## Result: no evidenced route/parameter mismatch in the current request

`vision_ocr.request` selects `only:["alibaba"]` for Qwen and
`only:["google-vertex/global"]` for both Haiku and Gemini. All three choices
are present in their respective current public endpoint listings. In
particular, **Haiku on Vertex/global is explicitly listed**; mapping an
Anthropic model to that route is not itself a bug. The selected routes
advertise the request's `reasoning`, `max_tokens`, `response_format` and
`structured_outputs`; Qwen also advertises the `temperature` which only the
Qwen request sends.
[Qwen endpoints](https://openrouter.ai/api/v1/models/qwen/qwen3.8-flash/endpoints),
[Haiku endpoints](https://openrouter.ai/api/v1/models/anthropic/claude-haiku-5.5/endpoints),
[Gemini endpoints](https://openrouter.ai/api/v1/models/google/gemini-3.5-flash-lite/endpoints).

This is advertised compatibility, **not** proof that the entire schema/body
will be accepted or that any account has a route satisfying all privacy and
price restrictions. It does not explain the previous generic `PROVIDER`
failure: that attempt's HTTP status/response is unavailable. Do not reconstruct
its cause from this later snapshot, free a budget reservation, or retry to find
out.

## Exact catalogue identities and reasoning declarations

All three model records declare image input and text output. Model-level
reasoning declarations currently read as follows; these are not endpoint
execution results. [Public model catalogue](https://openrouter.ai/api/v1/models).

| Request ID | `canonical_slug` | Current `reasoning` fields relevant here |
| --- | --- | --- |
| `qwen/qwen3.8-flash` | `qwen/qwen3.8-flash-20260826` | `mandatory:false`, `default_enabled:true`, `supports_max_tokens:true` |
| `anthropic/claude-haiku-5.5` | `anthropic/claude-haiku-5.5-20261007` | `mandatory:false`, `default_effort:"medium"`, supported efforts include `"none"` |
| `google/gemini-3.5-flash-lite` | `google/gemini-3.5-flash-lite-20260721` | `mandatory:true`, `default_enabled:true`, `default_effort:"minimal"`, efforts `high`, `medium`, `low`, `minimal` |

Consequently the existing disabled-reasoning request for Qwen/Haiku and
`effort:"minimal"` for Gemini have no demonstrated conflict with those model
declarations. `exclude:true` controls exposure, not whether reasoning is billed.
OpenRouter documents disabled reasoning and maps Gemini's effort to its
thinking level; a model's actual internal consumption is not fixed by choosing
minimal. [Reasoning controls](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

## Per-endpoint records, not the model's cheapest aggregate

Each endpoint response has top-level `data`, whose `id` and `architecture`
describe the model, and `data.endpoints`, an array. Individual entries expose
`provider_name`, `tag`, `service_tier`, `supported_parameters`, `pricing`,
`context_length`, `max_completion_tokens`, and `max_prompt_tokens`. Compare
records belonging to the configured route; model-level aggregated support or
minimum price is not enough. Relevant current values:

| Model and selected `tag` | `provider_name` / `service_tier` | `context_length` | `max_prompt_tokens` | `max_completion_tokens` | `pricing.prompt` / `.completion` raw USD/token |
| --- | --- | ---: | ---: | ---: | --- |
| Qwen `alibaba` | `Alibaba` / `null` | 1000000 | 983616 | 131072 | `"0.00000015"` / `"0.00000047"` |
| Qwen `alibaba/us-east-1` | `Alibaba` / `null` | 1000000 | 983616 | 131072 | `"0.00000015"` / `"0.00000047"` |
| Haiku `google-vertex/global` | `Google` / `null` | 1000000 | `null` | 128000 | `"0.0000001"` / `"0.0000005"` |
| Gemini `google-vertex/global` | `Google` / `null` | 1048576 | `null` | 65536 | `"0.0000003"` / `"0.0000025"` |

Sources: [Qwen records](https://openrouter.ai/api/v1/models/qwen/qwen3.8-flash/endpoints),
[Haiku records](https://openrouter.ai/api/v1/models/anthropic/claude-haiku-5.5/endpoints),
[Gemini records](https://openrouter.ai/api/v1/models/google/gemini-3.5-flash-lite/endpoints).

Exact selected-route `supported_parameters` arrays at this check:

```json
{
  "qwen:alibaba and alibaba/us-east-1": ["reasoning", "include_reasoning", "max_tokens", "temperature", "top_p", "seed", "presence_penalty", "response_format", "tools", "structured_outputs", "top_k", "frequency_penalty", "stop", "logprobs", "top_logprobs", "tool_choice"],
  "haiku:google-vertex/global": ["reasoning", "include_reasoning", "max_tokens", "response_format", "tool_choice", "tools", "verbosity", "structured_outputs", "stop", "reasoning_effort"],
  "gemini:google-vertex/global": ["reasoning", "include_reasoning", "max_tokens", "seed", "response_format", "stop", "structured_outputs", "tools", "tool_choice", "reasoning_effort"]
}
```

The keys above are explanatory labels, not upstream response field names.
Gemini's selected Vertex route does **not** list `temperature`, whereas its
model aggregate and AI Studio endpoints do. Current `vision_ocr` correctly
does not send temperature to Gemini; a future generic `temperature:0` addition
would have an advertised mismatch under `require_parameters:true`.
[Gemini endpoint declarations](https://openrouter.ai/api/v1/models/google/gemini-3.5-flash-lite/endpoints).

Haiku's selected endpoint has a `pricing.overrides` entry with
`min_prompt_tokens:100000`, `prompt:"0.0000005"`, and
`completion:"0.0000025"`. Gemini's selected endpoint additionally exposes
`image:"0.0000003"` and `internal_reasoning:"0.0000025"`. Qwen's selected
pricing objects have no `image` key. None of these selected endpoint pricing
objects has a `request` key. Do not turn absent fields into proof of no charge,
or copy a token rate into a per-image cap; retain the already-reviewed billing
interpretation and conservative complete-request reservation.
[Haiku pricing](https://openrouter.ai/api/v1/models/anthropic/claude-haiku-5.5/endpoints),
[Gemini pricing](https://openrouter.ai/api/v1/models/google/gemini-3.5-flash-lite/endpoints),
[Qwen pricing](https://openrouter.ai/api/v1/models/qwen/qwen3.8-flash/endpoints).

## Routing semantics and limits of a no-inference preflight

OpenRouter documents base-slug matching: `alibaba` can match its eligible
regional siblings, while a full suffix narrows the route. Standard slugs do
not automatically select paid service-tier siblings. Gemini's listed
`google-vertex/global/flex` and `/priority` must therefore not be treated as
the configured standard route. `only` filters candidates, `require_parameters`
filters unsupported parameters, `allow_fallbacks:false` disables backup
providers, and `data_collection:"deny"` restricts collection policy. Retain
all these controls. [Provider selection and slug matching](https://openrouter.ai/docs/guides/routing/provider-selection).

`zdr:true` further restricts routing and cannot override stricter account or
guardrail settings. Current docs identify Vertex as a possible ZDR route for
Google/Anthropic, unlike their excluded first-party/AI Studio endpoints. The
public responses inspected here do not expose sufficient per-endpoint privacy
and account evidence to certify the conjunction. ZDR may permit transient
in-memory prompt caching under OpenRouter's definition.
[ZDR rules](https://openrouter.ai/docs/guides/features/zdr).

A narrow preflight can safely **reject known metadata incompatibility before
Vault access or an inference reservation**, while returning only “advertised
compatible; execution unproven” on success:

- Require matching `data.id`, image input and a well-formed endpoint array.
- Match allowed tags with documented prefix/tier semantics, not
  `provider_name` display text, and do not replace the configured provider.
- Check the actual LLM request parameters against each selected endpoint's
  declarations; do not naively require `model`, `messages`, `provider`, or
  image content fields to appear in `supported_parameters`. Treat strict
  schema support separately from generic `response_format`.
- Validate finite positive per-endpoint rates, tier overrides applicable to
  the conservative request bound, known image billing and output/context
  ceilings. A `null` limit is unknown, not zero or infinity. Do not use another
  provider's cheaper catalogue minimum to satisfy the selected route's cap.
- Preserve local consent/offline gates before public metadata networking;
  plan-only/offline tests can inject a dated public snapshot without networking.
- Metadata success neither reserves nor releases money, changes privacy,
  triggers inference nor establishes availability. Preserve complete local
  response validation and fail closed on a later provider error.

These are implementation recommendations, not a new gate already deployed.
No Japanese OCR, translation quality, latency, 78/78, runtime-readiness or
account-access result follows from this note.
