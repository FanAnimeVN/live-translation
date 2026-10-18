# Rejected local adaptive batching experiment — 2026-10-15

Removed from the interactive pipeline. Recursive splitting did not resolve
the four-short-bubble reproduction and multiplied failed local work. Its
metrics also omitted failed parent calls. A bounded number of calls alone is
not a useful latency guarantee.

The source was not unusually long: a 14-character unfinished quotation alone
reproduces the generation ceiling. The production compact JSON instruction
can confuse dialogue quotation with JSON serialization. A shorter focused
JSON prompt still failed the four-bubble probe (305 generated tokens, about
22 seconds, finish reason `length`). Do not hide that failure by increasing
the cap, stripping quotes, accepting an incomplete JSON prefix or splitting
and re-running an entire failed batch.

The pipeline again makes one translator call per scheduled batch. The
translator retains its existing single, failed-ID-only semantic repair.
Neither offline nor cloud errors cause recursive batch retries or a switch
to a paid backend. Local adapter candidates require real-model comparison
before promotion; passing mocked tests is not translation-quality evidence.

## Follow-up diagnosis and recovery

The single-region baseline, no-schema comparison and short four-region probe
live in `scripts/probe_short_translation.py`; all source is authored, not a
reader dataset. Raising temperature to 0.7 did not solve the four-region
failure (305 output tokens; about 26 seconds). A per-region output-only
candidate finished faster but lost sibling vocatives, confirmed directed
pronouns and glossary, and completed unfinished quotations. It is rejected,
not a production replacement. Prompt/cache policy v22 is unchanged.

Native truncation keeps its classification and rejects unfinished output,
but no longer claims the reader selected an oversized area. Frontend recovery
also overrides the old message by code. Opening model settings is a separate
reader action; it neither changes the saved backend nor starts an API call.
Progress now distinguishes local CPU translation from cloud. Explicit Start
and completed region-selection gestures bypass the scroll debounce; observer
events cannot postpone them. Scroll/prefetch retain debouncing and the same
no-duplicate, cancellation, source-revision and paid-retry guards.

PNG preparation now uses asynchronous lossless `toBlob` and FileReader rather
than synchronous `toDataURL`. This is a responsiveness change, not a proved
wall-clock speedup: full initial image dispatch still measured about 246 ms
in the rendered QA run. Canvas drawing/encoding remains work. Pixel equality
with the submitted PNG is checked. Stop/restart during a held encoder must
discard the old source before any native image request; source, session and
URL revisions are rechecked after asynchronous preparation. Images stay in
RAM, with no quality reduction or cloud image upload.

Cloud succeeds on the authored four-bubble Native Messaging/Edge path without
lowering output guards. A measured isolated run before the explicit-start
debounce adjustment took 28.30 s cold / 5.64 s warm-new-page / 0.58 s cached
reader-to-completion (includes harness polling). Native warm breakdown:
1.22 s detector, 2.25 s OCR, 1.63 s translation. Cold initialization dominated.
This is one small fixture, not a p95, semantic certification or proof that the
personal Edge profile uses cloud. The earlier cloud attempt timed out before
provider dispatch; the later run and dataset-text pilot are separate evidence.

## Decoder-constraint follow-up — rejected, not a production engine fix

`source-quote-schema` in `scripts/benchmark_mt2_templates.py` is a diagnostic
only. An initial single-region run stopped in 20 tokens / 6.41 s, but that
result did not generalize to four regions. Primary-source inspection of the
installed llama.cpp converter found that bare regex classes bypass normal
JSON escaping, and that `pattern` bypasses a separate `maxLength`. See
`docs/local-json-schema-primary-20261015.md` for pinned-source evidence.

The diagnostic now limits intervention to one asymmetric opening quote,
leaves unquoted/closing-only/nested source unchanged, and handles JSON short
escapes explicitly. Its source, prompt, sampling and output cap remain intact.
The probe's repair schema is selected from the actual failed-ID subset, not
the original complete batch. These harness corrections are not app changes.

The corrected four-region run in ignored
`artifacts/short-local-source-quote-schema-four-final-20261015.json` stopped
without truncation, but was **still wrong**: it placed another bubble's reply
inside the first value and left the final value as a quotation mark. The
existing lexical contract accepted that last shape before the new regression
check. Total model generation was 15.79 s across two calls, not an acceptable
near-instant translation and not a semantic pass. Do not promote this decoder
candidate, increase its cap, strip source quotes or use its `ok` flag as a
meaning-quality score.

The production output guard now asks the existing single failed-ID-only repair
when lexical source text becomes punctuation-only output. It preserves actual
punctuation-only source and exact reader-locked symbolic labels. The regression
was red before the guard; this is a narrow lost-text safeguard, not a complete
cross-ID semantic validator. Replaying the two recorded private cloud regions
found zero current contract issues; no fresh inference, image upload or API
call was performed. No private-manga quality rate is established by this replay.

All four model/output error classes now have frontend recovery wording that
does not repeat an old host's misleading smaller-selection instruction. Native
semantic error messages also suggest checking OCR/terms or changing model,
not recursively shrinking and re-running the page. The reader screen displays
the **saved** CPU/cloud provider/model rather than an unsaved settings draft;
opening its cloud configuration does not change mode, load another worker or
call an API. Opting into prefetch in cloud mode explains that uncached unread
pages also consume the reader's API allowance before Start.

Verification after these changes: **1086 Python passed, 1 skipped**; typecheck,
**53 TypeScript tests** and extension build passed. Isolated Edge content and
options QA passed at desktop and 390 px mobile sizes (content also at 760 px),
including old-host errors, no automatic/duplicate retry, settings-only recovery,
saved-vs-draft model identity and cloud prefetch disclosure. Native responses
were mocked for rendered QA; it does not certify the personal Edge profile or
real translation quality. Browser plugin was unavailable; existing Playwright
Edge harnesses were used. New extension build: **0.1.0-dev.7b3df6be0cf2**.

No new paid calls, reader setting changes, model-default changes, installer
registration changes or release packaging were performed. Reloading an unpacked
extension alone is not proof that an existing manga tab's injected script has
updated: reload the manga tab too before starting the fresh reading session.

## Fresh authorized launcher/cloud check — not personal Edge acceptance

A subsequent reader consent authorized a new maximum **0.01 USD**, authored
four-bubble OCR text only. `scripts/cloud_native_probe.py --consent --budget
0.01 --model google/gemini-3.5-flash-lite` used a copied real development
launcher, real length-framed host calls, PP detection, manga-ocr and the
production translator/validation. It used the benchmark Vault credential under
the real Windows account, a disposable profile, no registry changes, no images
sent to cloud and no paid fallback. The package identity matched current source
(`pkg-sha256:405ec9d2d3621a879955678f39052cb1747e9ada00a30c64913914e5b5a5f8b8`).

| Sample | Framed upload → completed result | Native detector / OCR / translation |
| --- | --- | --- |
| Cold | 50.890 s | 38.990 / 8.653 / 3.178 s |
| Warm, different page ID | 6.370 s | 1.396 / 2.239 / 2.688 s |
| Same-page cache revisit | 37.41 ms | No detector/OCR/translation; cache 2.56 ms |

All three returned four distinct translated regions with balloon erase masks.
Two provider attempts returned responses: conservative reservations total
**0.008975 USD**, provider-reported cost **0.0021822 USD**. The cached sample
created no third provider attempt. These are not independently reconciled
billing, browser display timings, a reliable p95 or an instant-reading result.
One available-RAM observation during this run was 743 MiB, not a peak-memory
measurement or proof that RAM alone caused the cold delay. The test process
finished; it is not an ongoing monitor or authorization for another paid run.

Technical completion still exposes real quality defects: OCR prepended an
unsupported opening Japanese quote to two authored bubbles. Translation kept
that source error. The reply used `ta` in the cold result and `tôi` in the warm
result although the source omitted its self-pronoun; both speakers remained
unknown. Do not infer a sibling binding, strip the quotes globally, hand-edit
the generated result, or report semantic acceptance from four valid JSON IDs.

`scripts/lettering-qa.mjs --native-result
artifacts/authored-cloud-native-20261015-budget001.json` then replayed the
**unaltered** cold native output, verifying the exact authored PNG hash before
rendering. Desktop 1280×900 and 390×844 checks passed source-bound wording/IDs,
font floor and no clipping/box overlap. Eight source-glyph ROIs had zero
residual ink at both sizes; original-view restoration matched source pixels.
Screenshots were inspected in RAM only. Transport in this renderer replay was
mocked; this is not a fresh inference or the full MV3/native browser path.
The same replay also passed a real scroll delta, image resize to 620 px and
stop-to-untouched-source pixel equality (not just equality between two hidden
states). Existing expressive-pacing and recorded-detector-crop renderer modes
passed those stronger checks without a model/API request. Final verification:
**1151 Python passed, 1 skipped; 54 TypeScript passed; typecheck/build passed**.
The on-disk extension remains `0.1.0-dev.d27ed6dd1316`; this turn changed QA
scripts/tests/documentation, not production translation behavior or its defaults.

The browser tool's extension-settings URL policy denial was not bypassed.
No personal saved mode/key/settings or installed-profile reconnect was read,
changed or certified. The existing complete browser smoke script was not run
as a substitute. Its screenshots now also remain in RAM and its native version
check includes package identity; those harness edits do not fix local inference.

The independent private MN109-08 renderer recheck still fails: **three** visible
text-box collisions with current scope (the earlier fourth involved a now
deferred punctuation-review region). No production grouping, model, prompt,
erasure policy, acceptance gate or release package was changed. Private text
evidence is in ignored `artifacts/authored-cloud-native-20261015-budget001.json`
and `artifacts/private-overlap-repro-20261015-next.json`, never release inputs.
