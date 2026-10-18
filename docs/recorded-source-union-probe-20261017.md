# Recorded-source grouping: measured ablations — 2026-10-17

Development experiment only. No production/default, personal-browser install,
release packaging, label change, new weight download or paid inference. The
private eight-page pack still has 78 unreviewed Japanese labels, not independent
Vietnamese or clean-background gold. All raster data stayed in RAM; private
text/numeric evidence stays in ignored `artifacts/`.

## Matched controls and fresh recognition

The parents are the newly retained CTD line control (143 exact original source
members in 80 regions) and tiled PP (214 members in 140 regions), using the same
manga-ocr weights and unchanged source/gold fingerprint. Tiled PP is not the
132-region production detector. No source geometry is transplanted into an old
report, and no old OCR text selects a new crop or resolves overlap.

| Recipe | Exact / 78 | Edits / 939 | CER | Regions |
|---|---:|---:|---:|---:|
| Production control, unchanged | 35 | 269 | 28.65% | 132 |
| Retained CTD control | 44 | 157 | 16.72% | 80 |
| Tiled PP parent | 35 | 265 | 28.22% | 140 |
| CTD + intact disjoint tiled PP components, replay v2 | 49 | 123 | 13.10% | 118 |
| All member polygons + original paper grouping, fresh OCR v1 | 32 | 381 | 40.58% | 169 |
| Cross-plane support components + paper grouping, fresh OCR v2 | 36 | 228 | 24.28% | 143 |
| Fixed primary partitions + unique member support, fresh OCR v3 | 26 | 493 | 52.50% | 178 |

The 49/78 result is **replay**, not a newly accelerated detector or fresh OCR.
It adds 38 original secondary regions. Against CTD it improves nine label edit
counts, worsens none, gains nine containment assignments, loses none and changes
one string with equal edit count. Against production it still worsens five
labels and loses three assignments. Thus it is not promoted. It is distinct
from the earlier CTD + production-PP replay with 49/78 and **127** edits.

V1 and v2 both executed genuinely fresh recognition of all new crops. Each
retains all **357** original members exactly once, plus both complete parent
source planes, classes/flags and provenance. V2 fixes the polygon-IoU support
threshold at 0.5 before grading, joins only cross-plane supports and constructs
one recognition view per support component. It does not assert semantic
duplicates. V2 has 119 support edges and 238 recognition views before paper
grouping. The older v1 report predates these two fields: they are absent, not
measured zero.

Compared with CTD, v1 improves 13 edit counts but regresses 26 and loses nine
assignments; v2 improves 13 but regresses 19 and loses ten. Both are rejected.
Containment assignment changes are not independently proven detector misses:
an overwide union may fail the supplied label boundary despite retaining text.

The two-thread CPU runs recorded model load of 13.826 s / 12.476 s and summed
per-page recognition/diagnostic sections of 112.827 s / 93.428 s for v1/v2.
These sums exclude grouping/load and are neither total wall time nor live-page
p50/p95; they do not establish the application's speed targets.

## What original pixels show

A model-free polygon/crop scan found 85 secondary regions with positive-area
primary bbox overlap. Only four have all cross-plane member polygons disjoint;
only two additionally avoid symmetric OCR-crop/source-polygon contamination.
The two apparently crop-safe cases include artwork-like strokes and real SFX,
not established missing ordinary dialogue. Relaxing rectangle overlap alone
does not solve the principal ordinary-dialogue failures.

Original contextual crops were inspected in RAM after viewing predictions:

- MN109-08:b03: v1's broad union includes separate left/right text blocks.
- MN109-05:b05: v1 includes adjacent balloon blocks and a small handwritten
  aside/art below them.

These observations support crop contamination/over-grouping. This assistant
inspection was post-prediction, non-blind and not independent Japanese gold
review. No source/preview image was saved; labels were not edited or normalized
to make predictions match. SFX, handwriting and unknown roles remain visible
source evidence, not automatically irrelevant regions.

## Implemented experiment boundary

`scripts/probe_recorded_source_union.py` offers the isolated
`group_recorded_sources(...)` seam and a complete private run command. It:

- validates exact original polygons, scores, identities, page bounds and both
  source planes before model work; refuses reader exclusions or confirmed roles
  rather than rebinding them;
- keeps source strings for audit but never uses them, labels or edit scores to
  choose grouping; preserves parallel member/ref provenance;
- retains tiny/oversize rejected members as explicit review proposals and
  refuses more than 64 units instead of truncating;
- emits only review/label proposals without scope, speaker, balloon, memory or
  erasure authority; an OCR box/support component is not a glyph mask;
- uses the existing crop partitioner, offline guard, verified local recognizer,
  finite subprocess timeout and unchanged 2 GiB available-memory launch gate;
- reserves a new private output name, writes partial reports as incomplete and
  computes aggregate/paired scores only after all eligible pages finish.

The authored-data CLI test uses real RAM image decoding, source grouping,
partitioning and reporting, replacing only the external recognizer boundary.
It does not demonstrate manga OCR accuracy. The grouping/public-run tests were
red before implementation. Initial full verification: **1,469 Python passed,
1 skipped** (49.20 s), **61 TypeScript passed**, typecheck/build passed. Those
counts preceded the additional primary-anchor ablation below.

## Existing learned-container evidence

The already provisioned ogkalu comparator is not a new RT-DETR candidate under
another name. Its original private report actually contains **46** accepted
class-0 balloon boxes across the eight pages (0, 2, 12, 7, 8, 7, 9, 1). These
records can support a numeric ownership replay without another detector load
or download, but do not establish contours, correct ownership, semantic role
or erasure authority. Independent ownership labels remain missing. See the
[primary-source artifact/license/contract review](bubble-ownership-primary-20261017.md).

No promoted quality improvement is claimed from this note. The current
production baseline remains 35/78. Japanese review, semantic translation
evaluation, art protection/restoration and held-out/live latency gates remain
unmet; a better mean CER cannot waive lost content or damaged-art checks.

## Follow-through: fixed primary partitions are insufficient by themselves

A third ablation actually ran to completion with the same parents/recognizer.
It freezes every original primary region as its own anchor. A secondary member
may attach only when it has the existing fixed IoU ≥0.5 support for exactly one
anchor and has no positive polygon overlap with any other anchor. It cannot
transitively join primary utterances. Ambiguous/unsupported secondary members
remain explicit independent review crops in their original secondary rows;
they are not silently dropped or declared irrelevant/duplicates.

V3 retains all **80** primary units and all **357** original members: 106
secondary members attach and 108 remain in review-only secondary proposals.
Nevertheless, 178 active recognition units produce **26/78**, 493 edits and
29 multi-region label assignments. Against CTD, 12 edit counts improve but
34 regress, six assignments are lost, twelve gained and three strings change
at equal edit count. It is rejected. Preserving original source membership
does not make an active utterance partition nonduplicating or semantically
correct; feeding unresolved overlaps into recognition is itself harmful.
This result does not authorize deleting those source candidates in production.

Load was 12.029 s and summed page OCR/diagnostics 118.236 s; neither is a live
latency statistic. The subprocess completed with exit 0. Private evidence:

- `artifacts/private-detector-complement-ctd-tiled-bbox-v2-20261017-r4.json`
- `artifacts/private-recorded-source-union-v1-20261017-r4.json`
- `artifacts/private-recorded-source-support-v2-20261017-r4.json`
- `artifacts/private-recorded-source-primary-anchored-v3-20261017-r5.json`

The first anchor-boundary test failed before the new option and passed after
implementation. Expanding the original membership/order-independence check
then caught a real v3 input-order dependence; sorting output source buckets
fixed it. The model worker had already loaded the pre-sort implementation.
Both frozen parent reports have monotonically sorted IDs on every page, so
this fix does not change that executed recipe's output order or crops. The
post-fix grouping suite has 20 passing cases. Final verification on the source
state after this correction: **1,472 Python passed / 1 skipped**, 49.78 s;
**61 TypeScript passed**; typecheck and extension build passed. This is software
regression evidence, not real-manga accuracy, personal Edge E2E or API latency.

Of the 80 primary-associated units, 58 bboxes change because of secondary
support/padding, but only nine OCR strings change; none changes when its bbox
is unchanged. Thus duplicate/unresolved secondary contributions are a major
explanation for the much larger aggregate error, but crop changes are not
ruled out. This is an ablation diagnosis, not independent ownership gold.

The next useful question is whether existing learned balloon proposals
provide independently correct ownership/abstention relations. It is not another
IoU sweep, automatically deduplicating text, or broadening the crop until a
provided string matches. No 78/78, translation-quality, integrated-lettering or
release claim follows from these experiments.

### Numeric learned-container follow-through

A model-free, image-free replay of those same frozen CTD/PP reports and the
existing ogkalu report completed. A unit gets a predicted owner only if **all**
its original member vertices lie inside exactly one accepted class-0 box and
no competing box has positive polygon intersection with any member. No owner
is selected by score, enlarged rectangle, transcript, Japanese label or gold
reading. The saved ≥0.3 detector threshold is unchanged.

This strict predicate returns a unique **predicted** owner for 24/80 CTD units
and 26/140 tiled PP units; 56 and 114 abstain respectively. On each plane, no
predicted container is shared by two accepted units. These are coverage and
abstention counts, **not** precision, recall or correctness against ownership
gold. They provide no evidence for automatically merging additional units.
This replay changes no source boundary, utterance, role, crop, memory or art.
Numeric private provenance is in
`artifacts/private-recorded-balloon-owner-coverage-20261017-r5.json`.
