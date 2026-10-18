# Read-grounded, multi-model context — implementation checkpoint

Scope: desktop cloud-first development. No personal-browser installation or
paid inference was performed for this change. This is not a release or an OCR,
translation-quality, or real-provider latency claim.

## Decision on the proposed architecture

Separate translation and summarization routes are useful; a third unrestricted
wiki-research agent is not automatically useful or safe. Models remain
candidates, not quality winners. Current identity, price, reasoning and caching
caveats are documented with first-party sources in
[the primary-source check](context-multimodel-claims-primary-20261017.md).

- Translation retains the existing cloud model selection and reader locks.
- Summary cloud adapters initially support the reviewed OpenRouter IDs
  `deepseek/deepseek-v4.1-flash` and `anthropic/claude-haiku-5.5` independently
  of the translation model. Both request non-thinking output through the
  existing provider adapter; no provider/model fallback is introduced.
- GLM-5.3-Flash is not silently added: mandatory thinking and its effect on
  output budgets, cost and latency require a separate real-model evaluation.
- No claim of a 3.5-second median or superior Japanese-to-Vietnamese manga
  translation follows from public pricing or token-generation throughput.

## Wiki and cold start

Keep the existing explicit Wikidata title/alias search and reader-confirmed
story identity. Offline mode does not search. It does not fetch plot summaries,
character profiles, kinship, true identities or allegiances for translation.
Those can spoil even when presented as innocuous background facts. External
character research with source/reveal-cutoff review is not implemented here.

No wiki result is required: create a manual story identity and accumulate only
source-supported event proposals from pages the reader marks read. Unknown
speaker/listener IDs remain unknown. Do not infer a relationship merely because
3–5 opening pages have been read. Reader-confirmed names, directed pronouns and
canonical terms remain separate and retain their existing temporal authority.

## Compact events, not a rolling transcript

The new cloud summary prompt treats Japanese as primary evidence and Vietnamese
as potentially mistaken. It preserves a question, request, promise, hypothesis
or reported claim as such; it must not convert one into a completed occurrence.
At most 600 summary characters, four event proposals, 160 characters per
proposal and four source IDs per proposal are accepted. Output is capped at
900 tokens; the prompt has a 48,000-byte UTF-8 bound. Oversized input is refused,
not silently split into additional paid calls. Malformed/unsupported evidence
is rejected without a repair charge.

For this new route, durable event proposals retain cited original Japanese
utterances, unknown/confirmed source roles and chapter/page provenance. The
page summary does not duplicate all dialogue; uncited lines and Vietnamese
dialogue are not copied into durable summary evidence. Some cited dialogue must
remain: an ID pointing only to an expired cache would no longer be evidence.
Legacy/local summaries are unchanged; this does not delete old transcripts or
claim the whole application now stores no dialogue. Transient page cache and
recent-dialogue retrieval also remain separate.

Model prose stays unconfirmed/reviewable. The existing translation-context
retriever uses the original Japanese evidence, not an unverified model
paraphrase as an established plot fact. This protects against summary error
propagation; it does not prove semantic correctness of the displayed summary.
No full chapter completion is inferred from scrolling or page acknowledgements.

SQLite remains canonical, Markdown remains a bounded cutoff-filtered view and
JSON remains the full private backup. No destructive schema migration or
overwrite of a single continually growing lorebook is introduced. Future
chapter rollups need evidence/coverage validation, not a fixed 10–15-page rule.

## Consent, scheduling and foreground priority

Defaults remain local backend and automatic summaries off. Preparing or saving
settings, opening the library, saving a key or restarting the companion cannot
send pending cloud summary backlog. Cloud summaries require BYOK OpenRouter,
text consent, separate summary consent and the versioned capability
`read-evidence-cloud-v1`. An older companion is not treated as cloud-capable.
Manual cloud summaries require an additional confirmation of a paid text call
and keep the selected story/page cutoff. Local summary weights are not required
for the cloud route.

Background cloud work is separately opt-in. Only exact job IDs acknowledged
by a new `memory.read` after configuration are armed in the current native-host
session, at most 64. Prefetch/display is not reading. Settings/key changes and
shutdown clear this authorization; it is not reconstructed on restart.
Authorization is consumed before I/O, so a failed/cancelled/unknown-billed call
does not retry on idle. Explicit retry does not authorize all old cloud jobs.
Switching away from cloud does not silently enable a heavyweight local summary
worker or its backlog.

Foreground work cancels the summary wait. Exactly one cloud-summary HTTP
attempt may remain live while urllib finishes its bounded request; a second
summary is refused rather than launching more background threads. The late
response cannot commit stale memory. Cancellation does not guarantee the
provider stopped billing. No live network latency was measured here.

## Paid-attempt receipts

`summary-usage.sqlite3` is a separate bounded per-profile ledger, not story
memory or context export. A durable `sent` receipt precedes I/O. At most 512
receipts are retained; read-only status exposes ten recent records. Fields are
an independent attempt ID, timestamp, selected model, transport outcome,
numeric token/cost counters and a validated provider generation ID if returned.
There are no images, dialogue, story IDs, URLs or keys in these receipts.

Unknown/missing charge is `null`, never a guessed zero. `received` means a
response arrived, not that the summary is correct or accepted. Interruption
after send can leave an unresolved receipt. These records are not a complete
invoice, spending cap or authorization to enlarge the development budget.

## Verification and remaining work

Tests use authored dialogue, actual configuration/SQLite/native queue/provider
request construction, and fake external HTTP responses. Rendered settings and
library checks use isolated Playwright Edge with mocked native messages.
Browser plugin not available. Screenshots remain RAM-only; this is not personal
Edge, installed-extension E2E, real-model evaluation or mobile readiness.

Regression checks cover independent model selection, separate/revoked consent,
no settings-triggered charges, exact new-read queue selection, error without
idle retry, cancellation without foreground HTTP wait, bounded receipts,
compact cited evidence, malformed outputs, cutoff retrieval, manual decline,
cloud without local weights and legacy companion feature gating. A rendered
test also found and fixed re-selecting the current story leaving its library
blank instead of refetching.

Final verification on this source state:

- Python: **1,439 passed, 1 skipped** (`pytest tests/python -q`, isolated ignored
  temporary directory, 51.18 seconds). This is suite runtime, not API latency.
- TypeScript: **61 passed**; `npm run typecheck` passed.
- `npm run build` passed; no companion installer/release package was deployed.
- `npm run test:options` passed against the final build at
  `http://127.0.0.1:65303/options.html`, 1280×900 and the retained 390×844
  responsive regression. Page identity, meaningful render, no framework overlay,
  console health, RAM screenshots and interaction checks passed. This viewport
  regression does not claim mobile readiness.
- The idle/settings race was reproduced red, then verified green: a concurrent
  offline opt-out cannot consume a local backlog job. Optional receipt-read
  failure remains a visible accounting warning, not a disconnected companion.

Real cloud summarization still needs attributable budget and paired semantic
evaluation. Existing independent Japanese/Vietnamese gold review and clean-art
gold requirements remain unmet. This work does not improve the measured OCR
baseline or promote an unproven detector/model.

Development authorization is unchanged: $0.50 total, $0.49962719 conservative
reservations and $0.00037281 unreserved; reservations are not actual charges.
See [billing reconciliation](openrouter-billing-reconciliation-primary-20261017.md).

## Follow-through: recent context now retains the right source dialogue

An executed red/green investigation found reversed page order and render/source
metadata consuming the recent-dialogue budget. The retriever now projects only
dialogue fields with authoritative page cutoffs, gives newest complete lines
budget priority, then restores reading order. Existing scope filters, source
records and locks remain unchanged. Independent per-page replay of actual
recorded OCR increases retained entries 39→117 for production and 18→70 for
CTD; this is not a semantic score or new OCR result. Final tests: 1,490 Python
passed / 1 skipped, 61 TypeScript, typecheck/build passed. No paid request or
personal Edge update. [Detailed implementation and replay](context-reading-order-replay-20261017.md).
