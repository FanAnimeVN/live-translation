# OCR48 private recognition: completed comparisons, no promotion

## Decision

OCR48 from the pinned manga-image-translator checkout has now actually loaded
and recognized the private pages. Neither tested beam on the tiled proposals,
nor tensor beam on CTD proposals, beats its corresponding manga-ocr control.
Do not replace the product recognizer with this configuration.

Production remains the historical **35/78, 269/939 edits (28.65% CER)**.
The best recorded complementary-source replay remains **49/78, 127 edits**,
unpromoted because it still regresses/losses assignments against production.
These experiments do not establish automatic 78/78, Vietnamese quality or an
integrated-artwork result.

Earlier documents' low-RAM/load-blocked statements describe their earlier
checkpoints, not the current state. A fresh read-only preflight passed the
unchanged 2 GiB free-physical-memory launch gate. No guard was lowered and no
unrelated application was closed.

## Fixed sources and experiments

- Eight eligible private development pages, 78 supplied Japanese labels and
  939 normalized reference characters. Fingerprint unchanged:
  `445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`.
- External source commit `d6de6ab62a7be6afc0d07a3184149cdefbcd32f2`, verified
  checkpoint/alphabet, restricted CPU load, PyTorch 2.14.1, two CPU threads.
- Conventional `copy` loader for all actual recognition. Batch one, original
  per-line polygon rectification, width at most 2048, beam five and sequence
  limit 255. Literal tensor/scalar upstream methods are separate recipes.
- No gold box/text selects a crop, recognizer, orientation, ordering or output.
  Alignment is performed afterward. Raw low-score text and incomplete endings
  remain in the private report, not silently dropped to inflate accuracy.
- Tiled PP: frozen 140 ownership units / 214 retained source members.
- Fresh CTD: 80 ownership units / 143 retained source members and all 143 raw
  decoded detections. A paired check against the old eight-thread CTD report
  finds zero changed predictions, assignments or label edit counts. The new
  two-thread run therefore reproduces **44/78, 157 edits** while recovering
  actual source polygons for further work; polygons were not reconstructed
  from old union boxes.

These are same-proposal comparisons, **not identical-input model ablations**:
manga-ocr reads existing axis-aligned region/partition crops, whereas OCR48
reads rectified individual source lines followed by explicit ordering. They
do not measure upstream full-pipeline/direction-consensus parity.

## Paired quality results

| Proposal / fixed recognizer recipe | Exact | Edits | CER |
|---|---:|---:|---:|
| Tiled PP + recorded manga-ocr control | 35/78 | 265 | 28.22% |
| Tiled PP + OCR48 tensor, order v1 | 20/78 | 314 | 33.44% |
| Tiled PP + OCR48 scalar, order v1 | 20/78 | 317 | 33.76% |
| Same tensor readings, order v2 replay | 20/78 | 304 | 32.37% |
| Same scalar readings, order v2 replay | 20/78 | 307 | 32.69% |
| Fresh CTD + manga-ocr control | 44/78 | 157 | 16.72% |
| CTD + OCR48 tensor, order v1 | 26/78 | 195 | 20.77% |
| Same CTD tensor readings, order v2 replay | 26/78 | 195 | 20.77% |

Both tiled OCR48 v1 beams improve nine label edit counts but regress 29,
with four changed strings at equal edit count, against their tiled control.
CTD OCR48 tensor improves nine labels but regresses 25, with two changed
equal-edit strings, against the CTD control. Assignments do not change in
these same-unit comparisons; this does not prove true detector recall.

No transcript voting, reference-aware per-label selection, punctuation deletion
or gold correction was used. The supplied Japanese labels still need independent
review; there are no Vietnamese/clean-background references in this score.

## Real ordering defect and bounded replay

Original source crops were inspected in RAM for four tiled tensor regressions,
including the drifted fragments on MN109-05. A lower fragment can begin a few
pixels farther right than the upper fragment of the same vertical column.
Sorting only by x reads the lower fragment first. This reconfirms the defect
seen in the separate Baberu experiment; it is not an independent/blind review.

`benchmark_mit48.py --reorder-from` now tests the same already-fixed 60%
source-projection precedence rule used in that experiment: disjoint same-column
fragments go top-to-bottom; corresponding horizontal fragments left-to-right.
Other relationships retain original stable priority. No text-dependent rule,
parameter sweep, recognition, merging, new ownership or erasure is introduced.

For each tiled beam, v2 reduces ten character edits across two labels, with
zero label edit regressions, changed-equal strings or assignment changes.
Neither label becomes exact. CTD replay changes no labelled prediction.
This is useful ordering evidence, not enough to promote the losing OCR route.

Replay checks complete original inference, source revision/fingerprint, every
member identity/polygon/score/exclusion, raw v1 concatenation, image bounds and
unchanged diagnostic alignment. It retains all original line records and their
token/score/status fields; the output explicitly has no memory/erasure authority.
Gold is consulted only to verify/grade the source-only result. Replay timings
are distinguished from inherited recognition timings.

## Measured execution and limitations

Successful load-only probes, separate processes, no source images/inference:

| Loader | Load time | Process peak working set |
|---|---:|---:|
| copy | 5684.86 ms | 699,154,432 bytes |
| mmap/meta | 8893.64 ms | 293,126,144 bytes |

These are one measurement per loader. They establish successful restricted
materialization and lower **observed load-only process peak** for this mmap
run, not numerical/token parity, a faster loader or inference memory safety.
All recognition below deliberately uses the standard copy route.

| Actual recognition | Load | Sum of line calls | Process peak working set |
|---|---:|---:|---:|
| Tiled tensor, 214 lines | 5.70 s | 91.10 s | 828,588,032 bytes |
| Tiled scalar, 214 lines | 5.39 s | 95.18 s | 830,476,288 bytes |
| CTD tensor, 143 lines | 5.45 s | 83.44 s | 832,421,888 bytes |

Sums are observed line-call time, not supervisor wall time, page end-to-end
latency or live p95. The fresh CTD control separately spent 149.57 s in
detection and 65.83 s in recognition across eight pages. None includes cloud
translation, extension transport, context retrieval or presentation; none proves
the live-reading latency gates. No repeated cold/warm acceptance sample was run.

Tiled tensor: 207/214 end-token terminations and 187/214 upstream threshold
acceptances; tiled scalar: 214/214 for each. CTD tensor: 142/143 terminations,
131/143 threshold acceptances. All raw lines remain scored. Tensor uses
`exp(sum(logp))`, scalar `exp(mean(logp))`; these are not interchangeable
correctness probabilities. The scalar result does not confirm or disprove the
separate static concern about tensor-beam decoder-history association.

The older report helper's `process_memory.scope` text incorrectly mentions a
detector. Those historical files are not rewritten: no detector was loaded by
OCR48 (only the separate CTD control loads one). New reports now name their
actual load-only or recognition process scope. No process-tree/system-peak
RAM claim follows from a single child process working-set counter.

## Verification and next work

Comparator tests: **42 passed**. The new order/replay tests failed before their
implementation; the misleading memory-scope assertion also failed before its
fix. Tests cover vertical/horizontal drift, unchanged expressive text and input
records, exclusion/identity/polygon/text/alignment mismatch, partial reports,
out-of-bounds sources and no recognizer launch during replay.

Full regression: **1,452 Python passed / 1 skipped**, 48.64 s; **61 TypeScript
passed**; typecheck and extension build passed. This suite result protects
software behavior, not real-manga semantic quality. No renderer change was made
by this experiment and no personal Edge/installer/package was updated.

No paid inference, download, key access, image persistence or GPL product
integration occurred. Development reservations remain $0.49962719/$0.50 with
$0.00037281 unreserved, not actual billed spend.

Next quality-bearing step: use the now-retained CTD/PP source evidence to
resolve overlapping ownership before re-recognizing an entire residual crop;
do not splice unreviewed transcripts or transplant geometry from another
detector. Japanese source review remains necessary for genuine pixel/label
conflicts. Missing Vietnamese/background gold does not block Japanese OCR
work. Further paid independent readings require attributable reconciliation
or new authorization, not reuse of an exhausted reservation.

Private numeric/text evidence stays in ignored `artifacts/`:

- `private-mit48-load-{copy,mmap}-20261017-r2.json`
- `private-mit48-{tensor,scalar}-tiled-copy-20261017-r2.json`
- `private-mit48-{tensor,scalar}-paired-tiled-20261017-r2.json`
- `private-mit48-{tensor,scalar}-order-v2-20261017-r2.json`
- `private-pages-ctd-retained-lines-t2-20261017-r3.json`
- `private-ctd-retained-paired-20261017-r3.json`
- `private-mit48-tensor-ctd-copy-20261017-r3.json`
- `private-mit48-tensor-paired-ctd-20261017-r3.json`
- `private-mit48-tensor-ctd-order-v2-20261017-r3.json`
