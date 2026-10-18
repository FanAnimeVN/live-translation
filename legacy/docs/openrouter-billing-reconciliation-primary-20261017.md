# OpenRouter billing reconciliation — primary-source review

Checked 2026-10-17. Documentation research only: no credentials read, authenticated endpoint called, model inference performed, or local budget reservation changed.

## Decision

**Do not release legacy per-attempt reservations solely from a low aggregate key-usage snapshot or elapsed wall time.** This is a conservative project inference, not an OpenRouter billing rule. Aggregate usage lacks attempt attribution, and the inspected documentation supplies no hard maximum settlement delay or immutable billing-finality marker. Preserve unresolved amounts until attributable provider records or an explicit revised user budget resolve them.

The parent reports that the seven legacy image reports contain no generation IDs and the benchmark Vault entry is absent. This note does not independently verify those local facts or establish the account's actual spend.

## Documented interfaces and units

| Interface | Relevant data | Interpretation |
|---|---|---|
| `GET https://openrouter.ai/api/v1/generation?id=gen-…` | Bearer authentication; required generation ID; `data.total_cost`, `usage`, `created_at`, `model`, `provider_name`, `finish_reason`, `cancelled`, `is_byok` | Per-generation request/usage metadata, not a new completion. Missing/invalid IDs and HTTP errors do not prove zero cost. [Generation reference](https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation) |
| Same generation response | `total_cost` and `usage`: USD; `cache_discount`: nullable discount; `upstream_inference_cost`: nullable provider cost; `latency`, `generation_time`, `moderation_latency`: milliseconds; `tokens_prompt`/`tokens_completion` and `native_tokens_*`: nullable counts | Use the charged total, not current price × guessed tokens. `request_id` groups generations from one API request; `upstream_id` is the provider ID; `provider_responses` can include fallback attempts. Do not confuse these IDs. [Official OpenAPI schema, `GenerationResponse`](https://openrouter.ai/openapi.json) |
| `GET https://openrouter.ai/api/v1/key` | Bearer authentication; `data.usage`, `usage_daily`, `usage_weekly`, `usage_monthly`; separate `byok_usage*`; `limit`, `limit_remaining`, `limit_reset`, `include_byok_in_limit` | All-time and UTC-window usage are key aggregates, not this project's transaction list. Null limit means unlimited, not an available project budget. `label` may expose part of a credential and is unnecessary in reports. [Current-key reference](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key), [Limits](https://openrouter.ai/docs/api_reference/limits) |

OpenRouter's credits use USD as their base currency. Purchasing-credit fees and provider inference pricing are different matters. [Official FAQ](https://openrouter.ai/docs/faq#credit-and-billing-systems)

## Settlement, query costs and unavailable guarantees

OpenRouter documents charging when a request finishes. Its in-flight mechanism estimates token expense, holds it while running, replaces it with actual expense on completion/failure for a short settlement window, then releases the hold. It excludes some non-token charges from its estimate. These are **provider-side account holds**, not this project's consent reservations. The docs give no numeric upper bound for that window or key-aggregate propagation. A transient `in_flight_budget_exhausted` error can occur after requests stopped; its `Retry-After` is a retry hint, not a project-budget reconciliation certificate. [Limits: in-flight spending budget](https://openrouter.ai/docs/api_reference/limits#in-flight-spending-budget)

Usage accounting returns `usage.cost` in completed nonstreaming responses or the final SSE message; the guide describes it as the account charge. `/generation` offers asynchronous historical lookup. `upstream_inference_cost` there is available only for external-provider BYOK and is otherwise zero/null. An OpenRouter key supplied to this extension is **not itself** proof of that external-provider BYOK mode. [Usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting)

The inspected GET references do not declare a per-query token/inference charge, but also do not explicitly promise free/unmetered metadata queries. They are read-only retrieval operations; bound retries and handle authentication/rate/server errors. Do not describe a request as definitely free from the absence of a listed price. [Generation reference](https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation), [Current-key reference](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-api-key)

No inspected source specifies a retention SLA/TTL for generation metadata, a maximum delay until lookup succeeds, or a guarantee that an old `total_cost` can never be corrected. A 404 must remain unresolved, not be converted to zero. The Logs guide says metadata is stored by default, whereas prompt/completion retrieval is a separate content endpoint requiring prior opt-in; this audit should never request `/generation/content` or enable logging. [Logs and API access](https://openrouter.ai/docs/guides/features/logs)

Activity exports aggregate spend, tokens and request counts by time/grouping; external BYOK spend is an estimate at market rates and may differ from provider discounts. Such summaries can corroborate accounting but cannot uniquely recover missing legacy IDs. [Activity export](https://openrouter.ai/docs/cookbook/administration/activity-export)

## Narrow implementation recommendation — project policy, not provider guarantees

1. Record each attempt's local ID, reserved ceiling, exact returned generation ID and reported charge before parsing/validating generated OCR text. Malformed model content can still be billed. Keep retries separate and deduplicate generation IDs.
2. A read-only audit may fetch metadata for known IDs, validate finite nonnegative amounts and matching IDs, and report discrepancies. Never replay the original prompt to discover its charge.
3. Preserve a reservation for missing IDs, missing charge, 404, failed authentication, timeout or ambiguous attribution. Do not substitute `upstream_inference_cost`, nullable values, or zero token counters for the account charge.
4. If aggregate usage is used as a cross-check, retain observation time, key identity without credential material, UTC window/reset semantics, known request scope and outstanding attempts. It is not a closed ledger merely because two snapshots match.
5. Reconciliation requires an explicit append-only decision associating each replaced reservation with its authoritative charge/evidence; flag discrepancies rather than silently changing authorization. Unknown attempts stay reserved. A report alone must not authorize another paid request.

This can prevent unnecessary permanent over-reservation for **identified** completed attempts. It does not recover absent credentials/IDs, establish a final all-time bill, enlarge the user's consent ceiling, or authorize further cloud benchmarks.

## Implementation follow-through — no reconciliation performed

The QA harnesses now persist allowlisted generation/charge evidence before
model-output validation, retain unknown-billed attempts, stop later calls on
unresolved/duplicate billing evidence, and refuse overwriting text-run reports.
The known failures were reproduced with fake provider envelopes and transport
errors before the fixes. See [implementation and verification](cloud-attempt-evidence-20261017.md).
No metadata endpoint was called, old reservation replaced or credential read in
that implementation work. The original cumulative reservation remains
$0.496429 / $0.50; this change does not free the difference between reported
successful charges and unresolved historical holds.

## Later execution checkpoint — credential visibility and retained holds

The earlier local claim that the benchmark credential was absent came from a
restricted execution context. An authorized elevated boolean-only check found
the entry present and Vault available; do not treat the earlier result as key
loss or ask for re-entry on that basis. No secret value is recorded here.

One subsequently authorized detector-crop request failed without a generation
ID or reported charge. Cumulative reservations are now $0.49962719 of the same
$0.50 consent, leaving $0.00037281; no old hold was released. These figures are
not actual billed spend. Execution and measurement limits are appended in the
[private-crop probe checkpoint](cloud-proposal-probe-20261017.md). No evidence
here retrospectively attributes the failed request or grants another paid run.
