# Complementary detector sources — 2026-10-17

## Decision

An offline geometry-only replay improves the CTD control from **44/78 to
49/78**, diagnostic CER **16.72% to 13.53%**, on the unchanged private
development pack. It is **not promoted**: compared with production PP, five
labels have higher edit counts and three lose their diagnostic assignment.
Production remains the historically measured **35/78, 28.65% CER**.

This is new source-selection evidence from existing fresh recognition reports,
not a new detector/model run, independent gold review or end-to-end result.
Neither runtime, personal Edge, model defaults nor authorization changed.

## Question and fixed recipes

Whole-page switching discards useful sources when the other detector finds
text the selected detector misses. The new isolated
`scripts/probe_detector_complement.py` tests a narrower alternative:

1. Retain CTD regions as the primary plane.
2. V1 adds a PP region only if it has no positive-area intersection with any
   primary or other secondary region. Overlap is review, not a score threshold.
3. Source-image inspection exposed a distinct completeness problem: CTD finds
   no region on the cover, but v1 rejects overlapping existing PP title sources.
   V2 therefore keeps an **entire existing PP overlap component** when all its
   members are disjoint from primary. If any member touches primary or a reader
   exclusion, the entire component remains review-only. It never picks the
   disjoint tail of an intersecting component or a preferred transcript.

V1 remains reproducible; v2 requires the explicit `--secondary-components`
recipe. No geometry/score threshold was swept to improve the labels. Selection
sees no gold boxes, reference text or edit counts. Scoring runs afterward.

## Paired results

The source fingerprint is unchanged; eight eligible development pages, 78
labels and 939 normalized reference characters. No label was edited/excluded.

| Recipe | Exact | Edits | CER | Regions | Added PP regions |
|---|---:|---:|---:|---:|---:|
| Production PP control | 35/78 | 269 | 28.65% | 132 | — |
| CTD control | 44/78 | 157 | 16.72% | 80 | — |
| CTD primary + disjoint PP singleton v1 | 49/78 | 136 | 14.48% | 103 | 23 |
| CTD primary + intact disjoint PP components v2 | 49/78 | 127 | 13.53% | 112 | 32 |

V2 versus CTD: eight labelled edit-count improvements, zero edit-count
regressions, one changed string at equal edit count; eight diagnostic assignments
gained, zero lost. These are containment diagnostics, not true detector recall.
V2 versus production: 25 improvements, five regressions, three changed strings
at equal edit count; 12 assignments gained, three lost. The lower average error
does not establish a safe replacement. A reverse-direction v1 check (PP primary,
CTD secondary) adds no regions and retains the PP result unchanged.

The final all-source-bounds validation rerun has identical assignments/text and
metrics to the first v2 replay. Its separate paired report records zero deltas.
Neither replay supplies a cold/warm/page latency or RAM acceptance measurement.
Stored detector/OCR times are not added together and presented as live speed.

## Source and reader boundaries

- Both original region planes survive as exact deep copies, including raw
  scores, source members when present, reader scopes and exclusions.
- Candidate presentation IDs are deterministic references to plane/page/source
  ID, never ordinal-based captured-source keys or reader-binding migrations.
- Positive-area overlaps and full secondary components are recorded, including
  unselected records. Nothing is called irrelevant or deleted from source.
- Every emitted candidate is review-only, has no memory or erasure authority
  and carries no invented captured-source scope. This output is **not a
  renderer/runtime contract**; no cleanup or translation uses it.
- Both entire source planes are checked against the actual image dimensions,
  including unselected sources that can veto another source. An integration
  regression reproduced acceptance of an out-of-bounds unselected veto before
  this check was added.
- The legacy parents lack some raw per-line polygons/classes. Their aggregate
  evidence is retained; missing detail is not invented. This is not upstream
  full-pipeline parity, license clearance or glyph-mask evidence.
- The simple RTL row order is explicitly unverified for complex panels. Reader
  speaker/name/pronoun bindings remain in their original source plane.

## Pixel inspection, not independent review

Original crops with a 20-pixel context halo were inspected in RAM. The review
included all six v1 regressions against PP, the five remaining v2 regressions,
all v2 improvements over CTD and its changed-equal-edit case. Some were viewed
in more than one sheet. This assistant had seen the predictions and scores;
the inspection is neither blind nor an independent Japanese review.

The residuals include blocked title/caption components, a real missing pause
mark, and punctuation/reference conflicts requiring review. Preserving a
component fixes the cover omission of v1 but not intersecting components or
recognizer mistakes. A dots-only supplied label associated with a title crop
also needs independent geometry/transcription review; it is not permission to
remove punctuation, alter the label or rescore. Private notes remain pending,
not accepted gold or training examples. No source/crop/preview was saved.

## Verification and reproduction

Focused selector/CLI checks: **14 passed**. Tests cover original-source
immutability, stable references, transcript/gold-independent membership, any
positive overlap, whole-component preservation/veto, transitive exclusion
barriers, invalid geometry and a complete RAM-only authored-dataset CLI replay.
The CLI test forbids inference/network, verifies source checksums and refuses
overwrite or changed recognizers. New component-boundary tests failed before
the v2 option; the unselected-bounds case reproduced an actual accepted bad
report before the bounds fix. An early touching-box fixture overlapped a
second secondary source and was corrected to test the two boundaries separately;
the selection rule was not weakened to make it pass.

Full regression: **1,430 Python passed / 1 skipped; 60 TypeScript passed;
typecheck passed**. These tests do not certify manga quality. No release build,
packaging, browser installation, new cloud call or heavy model load occurred.

```powershell
.\.venv\Scripts\python.exe scripts/probe_detector_complement.py --folder '<private source folder>' --primary artifacts/private-pages-ctd-current-lines-t8-20261016.json --secondary artifacts/private-pages-production-v20-20261016.json --output artifacts/<new-v1-report>.json
.\.venv\Scripts\python.exe scripts/probe_detector_complement.py --folder '<private source folder>' --primary artifacts/private-pages-ctd-current-lines-t8-20261016.json --secondary artifacts/private-pages-production-v20-20261016.json --secondary-components --output artifacts/<new-v2-report>.json
```

Recorded private evidence (ignored, not shipped):

- `artifacts/private-detector-complement-v1-20261017.json`
- `artifacts/private-detector-complement-pp-primary-v1-20261017.json`
- `artifacts/private-detector-complement-v2-20261017.json`
- `artifacts/private-detector-complement-v2-validated-20261017.json`
- `artifacts/private-detector-complement-validation-paired-20261017.json`
- `artifacts/private-detector-complement-source-review-20261017.json`

The next quality-bearing work is resolving overlapping source ownership and
obtaining independent readings for genuine recognizer residuals, not additional
threshold sweeps or calling replay a fresh fast detector. Reviewed Japanese
geometry/text is sufficient to grade OCR; missing Vietnamese/background gold
does not block that work. Automatic 78/78, held-out generalization, integrated
lettering, cost and latency gates remain unproven.

## Follow-through — intersecting pixels are not a blank-padding shortcut

The full MN109-02 source and selected cross-plane intersections were inspected
in RAM. The remaining title/caption component vetoes involve visible dark
content, not just empty bbox margins. This assistant inspection remains
post-prediction and non-blind; it does not independently resolve transcription,
ruby, artwork or source ownership.

A separate model-free scan of all eight pages counted every positive-area
primary/secondary bbox intersection, including unselected sources. Original
images were decoded to grayscale uint8 in RAM. For each intersection, the scan
used floor(left/top), ceil(right/bottom), clipped to image bounds, and recorded
the minimum pixel value. Of **116** intersections, **115** have a sample below
175, **one** has all samples at least 220, and none falls between those buckets.
Private numeric evidence and source-report checksum are retained in
`artifacts/private-detector-overlap-pixels-20261017.json`; no image was written.

These thresholds are descriptive pixel-support buckets, **not routing or
cleanup rules**. A dark pixel can belong to a glyph, ruby, panel border, art or
noise. A bright intersection does not prove two sources are duplicates or
establish which transcript is correct. Thus neither this count nor the one
bright case justifies relaxing overlap policy, removing characters, changing
labels or granting erasure authority. V2 remains 49/78, unpromoted. No fresh
recognition, paid inference, production mutation or new quality score occurred.

The complementary public-route investigation found no evidenced mapping or
advertised-parameter mismatch for the configured vision requests. In particular,
Haiku's selected Vertex route is explicitly listed. See the full
[route metadata note](vision-route-metadata-recheck-20261017.md). Public metadata
does not establish actual account/privacy eligibility or explain the old
`PROVIDER` failure; no speculative routing fix or inference retry was made.

At this checkpoint a new lightweight resource check reports **322,564,096 bytes**
available physical memory and **5,302,145,024 bytes** available commit. The
unchanged OCR48 2 GiB physical-memory launch gate remains unmet. Cloud project
reservations remain **$0.49962719 / $0.50**, not actual billed spend, with
**$0.00037281** unreserved. Further paid independent reading requires attributable
reconciliation or revised authorization; no credential re-entry is needed.
Missing Vietnamese/background gold does not block Japanese OCR work. The next
quality-bearing experiment is still independent source-grounded recognition
and ownership resolution, not another metadata guard or threshold sweep.

## Source retention checkpoint — the old CTD report cannot answer ownership

The existing CTD control report records **143 raw detections by count**, 80
grouped regions and **zero retained member polygons** across the eight pages.
Its `detector_evidence.raw_detections` is an integer, not a recoverable source
list. The production PP parent also lacks member polygons; the separate tiled
PP candidate retains 214 members in 140 units, but is a different, unpromoted
detector recipe. Do not invent CTD lines from union boxes or transplant tiled
PP source members into the old production report by nearest geometry.

`scripts/benchmark_ctd.py` now emits `ctd-retained-sources-v2` evidence on future
runs: the complete decoded polygon/score list and an explicit count, plus exact
member polygons/scores on grouped regions. Block mode additionally retains each
selected model candidate's original seven-number row, candidate index,
objectness, class probabilities and class index. Decoding thresholds, NMS,
grouping and OCR are unchanged. Classes remain upstream location evidence, not
semantic importance, speakers, memory facts or erasure permissions. Dense maps
stay RAM-only; only numeric evidence survives. This is an external comparator
change, not a companion capability or reader-binding migration.

The two boundary regressions failed before their fixes: missing `sourceMembers`
at detector output, then missing raw block class/score evidence after NMS. The
first test attempt hit the environment's inaccessible default pytest temp root;
the actual red/green runs used new ignored workspace temp directories. Tests
substitute the external model forward only, with authored numeric outputs;
real coordinate mapping, NMS and paper grouping execute. They also check that
later Region/backend mutations cannot rewrite retained evidence. These are not
real-model inference, upstream full-pipeline parity or new OCR quality results.

Comparator-specific verification: **12 passed**. Full Python regression:
**1,432 passed / 1 skipped**, 52.68 seconds; TypeScript **60 passed** and
typecheck passed. This checkpoint does not rerun the
private recognizer, change the 49/78 candidate/35/78 production scores, rewrite
historical reports, promote defaults, package/install, or consume cloud funds.
It removes a concrete missing-input problem for the next ownership experiment;
recognizer execution still needs its resource/budget conditions satisfied.

## Later execution — retained-source CTD control reproduced

A fresh resource check passed and the two-thread CTD line control actually ran
on all eight pages with `ctd-retained-sources-v2`. It retains all 143 decoded
polygon/score records and 143 exact grouped members in 80 regions. Compared
with the old eight-thread control, predictions/assignments/edit counts are
identical: 44/78, 157 edits. Thus the missing source input is now available,
not merely a source-code change. No old geometry was reconstructed or replaced.

OCR48 on these proposals also completed but loses to the manga-ocr control:
26/78, 195 edits, with 25 regressed label counts. It is not promoted. See
[fresh recognition evidence and limits](mit48-private-recognition-20261017.md).

## Further source-partition ablations — 2026-10-17

CTD + **tiled** PP (not the old production PP recipe), retaining whole disjoint
secondary components, gives 49/78 with **123** edits in 118 regions. This is
still replay/unpromoted: no CTD edit regressions but five versus production
and three production containment assignments lost. Fresh regrouping/recognition
of all 357 original members loses to CTD: naive source union 32/78, support
components 36/78, fixed-primary anchors 26/78. All three are rejected. Full
paired numbers, pixel inspection limits, run times and source accounting:
[measured source-union ablations](recorded-source-union-probe-20261017.md).

Existing ogkalu class-0 records are actual balloon **boxes**, not a new detector
family or segmentation masks. A strict numeric owner predicate gives unique
predicted owners to only 24/80 CTD and 26/140 tiled PP units, with no shared
container on either plane. Coverage is not ownership accuracy and does not
justify merging more units. Source/rights/graph alternatives are documented in
[the primary-source ownership review](bubble-ownership-primary-20261017.md).
Final regression: 1,472 Python passed / 1 skipped, 61 TypeScript passed,
typecheck/build passed. No production promotion, paid cloud call or Edge install.
