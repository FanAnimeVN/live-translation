# Independent detector-crop OCR probe — 2026-10-17

## Quality decision

No new OCR accuracy improvement is established. Production remains the
historical 35/78; CTD 44/78 and review-only hybrid 48/78 are not promoted.
The independent cloud attempt described here failed before an accepted OCR
result. Do not score a provider failure as either a correct reading or proof
that the recognizer cannot read the source.

## Implemented experiment boundary

`scripts/benchmark_cloud_ocr.py --source proposal-crops` uses explicit retained
detector source IDs and their original crop geometry, not supplied gold boxes.
It verifies the unchanged dataset fingerprint and complete selected-page
evidence, retains source members/raw scores and records exclusions without
uploading excluded crops. Source images/crops remain in RAM.

The verifier receives original crop pixels without the primary OCR transcript
or gold text. Scoring occurs only after inference. This selected-crop probe is
not full-page recall, a 78-label result, speaker evidence or erasure authority.
The parent proposal checksum and selected-source provenance are kept in ignored
private evidence, not story memory.

`--completion-tokens 512` is an explicit benchmark-only output ceiling. It does
not change product defaults, the structured-output contract, privacy filters
or the existing 16,384 visual-token reservation. Truncated output fails; it
does not authorize automatic retry or fallback. `--plan-only` does not read
Vault, infer, create output or upload an image; it does fetch the public model
catalogue for price preflight.

## Actual attempt and cumulative authorization

One `qwen/qwen3.8-flash` detector-crop request was attempted under the existing
image consent. Private execution evidence is
`artifacts/cloud-image-qwen-proposal-r016-20261017/report.json`.

- One request; no retry/fallback or relaxed privacy route.
- Reservation: USD 0.00319819. The observed failure code was `PROVIDER`.
- No accepted OCR text, generation ID or reported charge; reported cost is
  **null**, not zero. The run stopped as `missing_or_unbounded_usage`.
- Cumulative project reservations: USD **0.49962719** of the original USD 0.50;
  remaining authorization USD **0.00037281**. These are conservative project
  holds, **not a claim about the amount actually charged**.
- A read-only scan of eight image-probe reports found no generation IDs. Do
  not replay a request to recover its ID or release holds from aggregate usage.
  Further paid inference requires attributable reconciliation or an explicit
  revised authorization. This document grants neither.

The old failed report lacks the exact HTTP status. Do not infer a 404, routing
restriction, model outage or other specific provider cause from `PROVIDER`.
The source-provenance-on-failure hardening was added after this attempt; the
historical report is not rewritten to pretend it used that later code.

## Credential visibility correction

The benchmark Vault entry exists outside the restricted execution context.
The restricted status check returned absent; an authorized, elevated
**boolean-only** check returned present and Vault available. Thus the earlier
claim that the credential had disappeared was not established. Do not ask for
the key again based on that restricted result. No secret value belongs in a
command, report or documentation. This checkpoint does not read Vault again.

## Measurement fixes and tests

The CLI integration regression reproduced `CER=0.0` when a truncated response
left zero scored characters. The summary now returns `cer: null` in that case.
Accepted blank controls remain countable, but a zero-character reference set
has no defined character-error rate. Failed/no-output requests are not perfect
OCR and must remain distinct from accepted samples.

Future HTTP failures retain only a validated integer status from the actual
transport exception/context. No error body, headers, request URL, key or message
is read into evidence. This metadata does not establish zero charge, a retry
policy or the cause/status of the old Qwen failure.

The CLI tests exercise the real `post_json` wrapping with fake HTTP 404, 429 and
503 transports. They failed first because no status survived, then passed with
one attempt, retained unknown-cost reservation and no retry. Non-HTTP messages
and invalid status values cannot invent HTTP evidence. All provider/Vault/image
boundaries are authored or mocked in these tests; no new paid request occurs.

Focused cloud-image/evidence regression: **36 passed**. Earlier full regression
after detector-proposal/CER changes: **1,408 passed, 1 skipped**. TypeScript
**60 passed**, typecheck passed. The status-capture addition is separately
verified by the subsequent full-regression checkpoint below.

Final full regression including numeric HTTP-status evidence: **1,416 passed,
1 skipped**. This verifies software behavior, not improved OCR accuracy or
production page latency. No build/package/install was performed in this
checkpoint; source and ignored private evidence remain separate.

## Next quality-bearing execution

The useful next evidence is an independent original-pixel reading on retained
proposals, compared with the primary on the same inputs, with disagreements and
missing content reported rather than automatically corrected by fluency or
majority vote. Japanese source-label review remains separate from selecting a
model output. Missing Vietnamese/clean-background gold does not block OCR.

The prepared OCR48 comparator still requires its unchanged 2 GiB free-physical
launch gate. The current check found about **512 MiB** available, so no heavy
model load was attempted. No resource threshold, production default, reader
binding, dataset label, package or personal Edge session changed.

A source-grounded automatic 78/78 remains a goal, not a result. Assisted
corrections, unresolved labels and automatic OCR must be reported separately;
these already-tuned pages remain development/regression, not held-out data.
