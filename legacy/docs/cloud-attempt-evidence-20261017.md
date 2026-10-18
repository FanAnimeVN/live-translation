# Cloud benchmark attempt evidence — 2026-10-17

Status: implemented in isolated QA harnesses, no new cloud request or budget
reconciliation. This is not an OCR/translation quality improvement or release.

## Reproduced failures

The image and authored-text benchmark commands both indexed `choices[0]` while
constructing diagnostics. A returned envelope with a generation ID, a reported
charge and `choices: []` raised `IndexError` before durable response evidence.
The previous text harness also appended a route only after receiving a
response, leaving an unknown-billed transport failure without a per-attempt
record. A fixture with three repetitions proved it proceeded to three calls
after that failure instead of stopping after the first unresolved attempt.

These failures were reproduced with local fake provider/Vault boundaries. No
actual provider, credential, private page or model was used in the tests.

## Implementation

- `scripts/cloud_response_evidence.py` extracts an allowlisted generation ID,
  finite nonnegative charge, bounded integer token counters, known token
  details and bounded provider/finish metadata. It never records message
  content, prompt, image URL, arbitrary usage fields or headers.
- `capture_response` persists this envelope before model-output validation. It
  distinguishes reported, missing-ID, missing-cost, duplicate-ID and
  over-reservation states. Returned cost is evidence, not billing finality.
- Authored-text, image-OCR and native cloud QA record a local opaque attempt
  ID, request fingerprint, start timestamp and reservation before each call.
  The text harness now has durable flat attempts as well as per-case routes.
- Unknown-billed failures retain reservations. A missing/ambiguous charge or
  duplicate ID stops later benchmark requests; native QA latches the accounting
  failure for its current process. No output failure authorizes a replay.
- Duplicate generation IDs are not double-counted in the **reported-charge**
  subtotal; all attempt reservations remain. Incomplete cost evidence produces
  a null subtotal rather than pretending the unknown request cost zero.
- Text output is single-use: existing report/temp evidence or an existing
  exclusive destination claim is rejected before credential access. A claim
  is an overwrite guard, never proof of a live process.

The authored-only `--capture-output` option remains explicit and separate from
billing metadata. These QA timings include diagnostic persistence overhead;
they are not production page-latency measurements. The production native host,
reader memory, OCR routing, provider defaults and personal Edge are unchanged.

## Verification and remaining limits

Targeted cloud harness/evidence checks: **41 passed**, including both command
entry points with billed malformed responses, an unknown-billed network failure,
duplicate generation, invalid costs, metadata allowlisting and overwrite refusal.
The cases failed before their corresponding fixes; the network fixture observed
three calls before the fix and one afterward. Extreme integer cost evidence
also survives without a float-conversion crash; it remains over budget and
does not become authorization to continue.

Final full regression: **1,390 Python passed, 1 skipped**; **60 TypeScript
passed**; typecheck passed. No packaging or personal-browser update was made.

Read-only reconciliation still reports **$0.496429 reserved** against the
original cumulative $0.50 authorization, leaving **$0.003571**. These are
conservative reservations, not a claim that the provider charged $0.496429.
No legacy report was rewritten and no hold released. The old missing generation
IDs cannot be reconstructed by this change. There is no automatic generation
lookup, credential restoration, settlement conclusion or new paid authorization.

Current metadata sources explain returned `usage.cost` and later lookup by
response `id`; neither proves the old unknown requests were free:
[OpenRouter usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting),
[earlier reconciliation review](openrouter-billing-reconciliation-primary-20261017.md).

The next quality-bearing work remains private-image recognition and paired
pipeline evaluation. Japanese OCR historical scores are unchanged. At the
initial launch check only about 550 MiB physical RAM was available, below the
unchanged 2 GiB OCR48 guard; no real OCR48 load or inference was attempted here.
