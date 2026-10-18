# Pair-scale grouping and bounded parent inference frames

2026-10-17, r13. Desktop development experiment, **not a native default or a
release**. Private images/crops remained in RAM; text/numeric reports remain
in ignored `artifacts/`. No paid requests, downloads, gold edits or personal
Edge installation were performed.

## Reproduced source defect

On the investigated development page, four detected columns became one OCR
region although the source contains two separate utterances. The minimal
bridge joined two columns using the wider column's transverse scale. Its
gap exceeded the narrower column's scale. This was a grouping defect, not a
detector omission or a translation-model defect.

The existing red-capable command is:

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/probe_grouping_replay.py --folder '<private-dataset>' --page MN109-08 --box 100 209 163 198 --expect-regions 2
```

The frozen/default recipe returns one region and exits 2. Adding
`--experimental-pair-scale` returns two regions and exits 0. The selection is
a diagnostic of an already reviewed failure, never an input to production
rules or an altered benchmark matcher.

## Three hypotheses tested, not aggregate-score promotion

1. Use the smaller transverse member scale for adjacency. This separates the
   intended utterances, but alone also splits another page into overlapping
   source envelopes. Its recognizer hallucinates text from artwork.
2. Split only within each existing parent cluster, retaining that parent if
   proposed source or actual padded inference envelopes overlap. This preserves prior
   notch/border vetoes and fixes the unwanted second-page split. However, the
   shorter right crop loses the source's final question mark.
3. Keep each child's transverse bounds, but preserve the original parent's
   **actual inference crop** longitudinal frame. This restores the question
   mark without recombining the utterances or enlarging erasure geometry.

Both changed raw strings and the source page were inspected; a better CER
alone was not treated as sufficient evidence.

## Implemented experiment boundary

`group_regions(..., experimental_pair_scale=True)` retains its explicit
experimental status. `partition_ocr_boxes(..., source_parents=parents)` now
implements the demonstrated frame preservation, rather than leaving it only
in a disposable probe. The existing native call without `source_parents`
remains unchanged.

- Recompute parent inference partitions from current source pixels; do not
  consume arbitrary `ocrCropBox` provider hints or skip previous partitions.
- Require the complete, exact, unique detector member polygons and raw scores
  on both views, with a unique original parent for every child. Reject missing,
  fabricated, duplicated or cross-parent provenance.
- Apply only to split, uniformly oriented, disjoint transverse strips inside
  the original inference frame. Longitudinal fragments must not become
  overlapping full-length strips.
- Keep reader exclusions/confirmed roles and proven balloons out of this
  experiment. Unsupported cases retain ordinary inference planning.
- Do not mutate source bbox/polygon/member evidence, scope keys, reader
  history, speaker, masks or cleanup permissions. The resulting fragments
  remain reviewable labels, not verified integrated lettering or plot memory.
- Record numeric lineage with `erasure_permitted=false`. The separate recipe
  identity is `pair-scale-v1-disjoint-parent-frame-experiment`; source and
  presentation compatibility versions are not silently relabelled.

Authored tests at the existing grouping/partition boundary cover source
preservation, overlapping children, horizontal/vertical orientation, scale,
ordering, reader ownership, malformed provenance, longitudinal fragments and
the original pixel-based parent partition. These protect software behavior;
they are not additional manga-quality data.

A further authored red/green regression covers narrow columns whose source
envelopes are disjoint but three-pixel crop margins overlap. Such a proposal
now retains its parent. Final eight-page geometry/member/crop replay is
identical to the fresh two-crop experiment; it introduces no extra split.

## Executed eight-page paired evaluation

Unchanged fingerprint and supplied development labels: eight eligible pages,
78 Japanese labels, 939 normalized characters. Labels remain pending independent
human review; no eligible Vietnamese or complete clean-background gold exists.

Only the unchanged full-page PP detector plane was used. No tile additions,
reference-conditioned routing or new detector inference were introduced.
Unchanged source membership **and source bbox and inference crop** were required
before reusing recognized text.

| Recipe | Regions | Exact / 78 | Edits / 939 | Decision |
| --- | ---: | ---: | ---: | --- |
| Production source control | 132 | 35 | 269 | Unchanged default |
| Min transverse scale alone | 134 | 35 | 240 | Reject: extra art text, lost question mark |
| Plus disjoint-child veto | 133 | 35 | 251 | Reject: still loses question mark |
| Plus bounded parent inference frame | 133 | 36 | 250 | Useful experimental result; not yet native-promoted |

The last row was first measured in the disposable probe, then reproduced
through the actual new `partition_ocr_boxes` implementation: **two fresh
manga-ocr crops**, 131 strictly unchanged region texts reused, seven pages
unchanged. Paired normalized diagnostics show one improved label, no regressed
label, one gained assignment, no lost assignment and no changed-equal-edit
label. CER is **28.65% → 26.62%**. The newly separate left utterance remains
outside the unchanged containment assignment; do not relax that matcher to
claim another exact result or call alignment recall detector recall.

Private evidence chain:

- `private-pair-scale-fresh-20261017-r13.json`: initial fresh min-scale probe.
- `private-pair-scale-disjoint-replay-20261017-r13.json`: guarded replay.
- `private-pair-scale-parent-longitudinal-fresh-20261017-r13.json`: fresh
  recognition using the initial disposable frame calculation.
- `private-pair-scale-code-frame-replay-20261017-r13.json`: strict crop/member
  replay through the new implementation.
- `private-pair-scale-code-frame-fresh-20261017-r13.json`: final implemented
  plan with freshly recognized changed crops, explicit crop/lineage evidence.
- `private-pair-scale-final-replay-20261017-r13.json`: after the padded-envelope
  safety correction, identical inference inputs and strictly reused text.

The fresh two-crop time excludes detection, unchanged OCR, context, translation,
cleanup and rendering. It is not page latency, a p95 measurement or evidence
of near-instant live reading. Cold model load is separate.
The implemented fresh run measured **1,827.65 ms** for the two changed crops
and **12,460.95 ms** for cold recognizer load; neither is a full-page benchmark.

## Promotion and remaining gates

`PaddleDetector.detect`, source cache identities, accepted translations,
reader bindings and migrations remain unchanged. No candidate fragment is
rebound to an old reader choice by ordinal ID or guessed geometry. Native
promotion still needs a complete versioned source/coverage compatibility path,
paired scope/lettering evidence and preservation of accepted caches/history;
this result must not be advertised as an installed fix.

There is still no 78/78 result, held-out translation certification or exact
clean-art benchmark. This narrow improvement does not justify changing a
translation model, importing wiki character facts or running paid summaries.
See [the context proposal delta](context-proposal-delta-20261017-r13.md).

## Verification

- Red frame regression: unexpected `source_parents` argument before the fix;
  passes through the real public partition interface after implementation.
- Original diagnostic: default remains red; explicit experiment returns the
  expected two groups and bounded inference crops.
- Focused grouping/partition regressions: **96 passed**.
- Final full Python: **1,531 passed, 1 skipped**, 51.73 seconds.
- TypeScript: **62 passed**; typecheck and extension build passed.

The suite runtime is not OCR/API latency. No renderer/native default changed,
so this checkpoint does not claim a fresh installed-extension or visual
end-to-end acceptance. Goal remains active and not release-ready.
