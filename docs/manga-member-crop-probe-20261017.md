# Retained detector members: executed crop/order ablation

Desktop development checkpoint, 2026-10-17. No paid inference, model download,
personal Edge update, release package or production-default change. Source
images and crops stayed in RAM; private text/numeric reports are ignored under
`artifacts/`. This finishes the pending member-recognition experiments, not
another proposed model search.

## Fixed experiment boundary

`scripts/benchmark_manga_members.py` reads the unchanged pinned manga-ocr model
on each retained detector polygon's axis-aligned box with a clipped 2-pixel
original-source halo. No rotation, background masking, reconstruction, label
hint, text splicing or answer-aware selector. Original region boxes/IDs,
member polygons/scores, exclusions and complete parent source records remain.
Candidates have no memory or erasure authority. All source records/coverage
are validated before loading the model; locked assets must already verify.
The existing RAM gate and supervised finite subprocess timeout remain.

This isolates **recognizer crop granularity and reading order**, not a fresh
detector, complete upstream-pipeline reproduction, translation or lettering.
The same private pack has eight eligible pages, 78 supplied Japanese labels
and 939 normalized reference characters. Labels remain unreviewed; there is
no accepted Vietnamese/clean-background gold or held-out claim.

`raw_text` records the engine's returned string, not raw decoded tokens:
upstream manga-ocr still performs its existing whitespace/ellipsis/fullwidth
postprocessing. This experiment does not establish raw expressive-spacing
preservation and does not add a global punctuation repair.

## Measured results

| Same-proposal recipe | Exact / 78 | Edits / 939 | CER | Regions / members |
| --- | ---: | ---: | ---: | ---: |
| Retained CTD whole-region control | 44 | 157 | 16.72% | 80 / 143 |
| CTD individual members + order v2, fresh OCR | 44 | 149 | 15.87% | 80 / 143 |
| CTD unchanged member strings + direction v3 replay | 45 | 145 | 15.44% | 80 / 143 |
| Tiled PP whole-region control | 35 | 265 | 28.22% | 140 / 214 |
| Tiled PP individual members + order v2, fresh OCR | 26 | 346 | 36.85% | 140 / 214 |
| Tiled PP unchanged member strings + direction v3 replay | 26 | 346 | 36.85% | 140 / 214 |

CTD member v2 improves seven label edit counts but worsens five, with two
changed strings at equal edit count. V3 fixes one of those regressions against
the whole control: seven improvements, **four regressions**, two changed-equal
strings, no assignment changes. Tiled PP member OCR improves four, worsens
**17**, and changes three at equal edit count. Its v3 replay changes no aligned
label prediction. Both blanket member-recognition replacements are rejected.

The current production control is **35/78, 269 edits, 28.65% CER, 132 regions**,
not the 140-region tiled parent. Against production, CTD member v3 improves
28 edit counts but worsens 13, with 12 gained and 11 lost containment
assignments. These assignment changes are diagnostic, not independent text
recall/miss measurements. Lower aggregate CER does not pass the no-loss gate.

## Real pixel observations and the narrow order fix

Fourteen CTD changed labels, including both changed-equal cases, were inspected
on contextual source pixels in RAM. This inspection was after predictions and
is **not blind or independent Japanese gold review**. No label was rewritten.

- MN109-03:b02 has a short near-square right-hand column and a tall left-hand
  column. The old binary direction vote classified every non-tall fragment as
  horizontal evidence; the tie chose horizontal and reversed these columns.
- Explicit comparator-only v3 applies the existing 1.5 aspect criterion
  symmetrically: tall votes vertical, wide votes horizontal, near-square
  abstains. A tie retains legacy direction and records fallback. Source
  geometry, not recognized text or gold, determines order. This fixes that
  label by four edits without changing its member strings. V2 remains the
  default recipe so completed experiments stay reproducible.
- MN109-06:b07 visibly includes a heart. Whole-region recognition retains it;
  the member crop reading replaces it with a small kana and happens to match
  the supplied label exactly. This apparent exact-match gain is **not** a
  faithful improvement. It remains a pending pixel/reference review, not
  permission to discard expression or correct the gold automatically.
- MN109-06:b03 and MN109-08:b03 include genuine member-recognition character
  regressions. Useful lexical corrections elsewhere do not justify universal
  member replacement. Stylized punctuation/crop and existing label conflicts
  also remain unresolved.

There is no gold-aware runtime selection between whole/member readings. V3
is a measured comparator correction, not evidence that all grouping/crop
ownership is solved or authority to ship the candidate as production OCR.

## Resource measurements and provenance

Two-thread CPU runs, same locked recognizer:

| Experiment | Model load | Sum of eight page OCR/order sections | Process peak working set |
| --- | ---: | ---: | ---: |
| CTD members | 14.348 s | 98.841 s | 865,951,744 bytes |
| Tiled PP members | 10.580 s | 142.591 s | 868,089,856 bytes |

These exclude fresh detection, cloud translation and browser display. They
are **not** live first-bubble/page p95, total wall time or total/system RAM.
V3 is model-free replay; inherited member times are not replay latency.
Both inference workers and both replays completed successfully; no extra
worker is required to reproduce the numeric comparison.

Private reports:

- `artifacts/private-manga-members-ctd-20261017-r8.json`
- `artifacts/private-manga-members-ctd-direction-v3-20261017-r8.json`
- `artifacts/private-manga-members-tiled-20261017-r8.json`
- `artifacts/private-manga-members-tiled-direction-v3-20261017-r8.json`
- `artifacts/private-manga-members-ctd-direction-v3-vs-whole-20261017-r8.json`
- `artifacts/private-manga-members-ctd-direction-v3-vs-production-v20-20261017-r8.json`

Provenance correction: the earlier private file named
`private-manga-members-ctd-direction-v3-vs-production-20261017-r8.json`
actually compared the older scope report (34 exact / 274 edits), **not** the
current production-v20 control. It is retained unchanged as diagnostic
history. Use the explicitly `vs-production-v20` report for current comparisons.

The original member inference used v2 throughout. The PP worker was launched
before v3 was added; unchanged v2 defaults preserve that recipe. V3 replays
are separate reports, not retrospective relabeling of completed inference.

## Verification and next evidence

Existing agreed comparator/source seams have regression coverage for source
preservation, clipped original pixels, order, expression strings, exclusions,
invalid geometry, absent decoder metadata (null, not fabricated confidence),
complete private reporting and inference-free replay. The runner/replay and
near-square correction were reproduced red then green; two additional
horizontal/tie cases verify existing v3 behavior. Focused result: **19 passed**.
Full-suite results are recorded below after execution.

Final execution on this source state: **1,495 Python passed / 1 skipped** in
47.37 seconds; **61 TypeScript passed**, typecheck and build passed. Python
used an isolated ignored temporary/cache directory. These are software
regressions and build evidence, not semantic accuracy or live-provider latency.
No installed runtime or release bundle was updated.

Do not spend another iteration on blind union/rotation/member replacement.
The remaining useful work is independently reviewing disputed pixels and
calibrating source-owned uncertain-region handling, or an independently
image-grounded verifier under a new attributable budget. No new paid calls
were made; development reservations remain $0.49962719/$0.50, not actual spend.
This checkpoint cannot certify 78/78 or release quality.
