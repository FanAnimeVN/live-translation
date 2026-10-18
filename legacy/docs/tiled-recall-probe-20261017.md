# Tiled detector recall experiment — 2026-10-17

Decision: **do not promote**. The frozen experiment recovered one assigned
label but did not increase exact-match accuracy. It is an offline comparator,
not a new reader setting or default. No cloud request, personal Edge action,
source-image write or private-gold modification occurred.

## Experiment and provenance

Private development fingerprint:
`445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`.
Eight eligible pages / 78 supplied Japanese labels / 939 normalized characters.
These labels remain unreviewed and this is not a held-out set.

`scripts/probe_tiled_detection.py` runs the same installed PP-OCRv5 detector
on the whole page and four overlapping 60%-width/height tiles, each resized
with an explicit 960-pixel long edge. The policy was fixed before scoring:
whole-page detections have precedence; IoU >= .5 or minimum-area containment
>= .85 is a duplicate; other containment > .15 remains overlap-review evidence;
boxes within two pixels of an internal tile edge are not accepted. All raw
polygons, unmodified scores, tile offsets and decision reasons are retained.
Rejected proposals are not classified as irrelevant or erased.

Detection and OCR ran in separate processes to avoid simultaneously retaining
Paddle and PyTorch while the machine had about 0.9 GiB available RAM. The
recognition phase reuses the recorded detection only after dataset fingerprint,
source dimensions, source-pixel hash, recipe and layout-version checks. It
refuses more than 64 regions instead of truncating. Added proposals remain
review-only, cannot enter plot memory and cannot authorize cleanup. No
translation or story-memory update was run.

Installed detector and OCR weights matched the pinned manifest hashes during
the experiment, and all model files were verified after the run. Detector
revision: `0d63e78e2b680928f6b1747d76a08db6e645efb7`; manga-ocr revision:
`aa6573bd10b0d446cbf622e29c3e084914df9741`. The script now preflights every
model file before its phase; it never downloads a model during inference.

## Paired development result

| Measure | Production control | Tiled candidate |
|---|---:|---:|
| Exact against supplied labels | 35/78 | 35/78 |
| Assigned labels (containment diagnostic) | 62/78 | 63/78 |
| Character edits | 269/939 | 265/939 |
| Diagnostic CER | 28.65% | 28.22% |
| Recognized regions | 132 | 140 |
| Grouping-fragmented diagnostic rows | 10 | 11 |

Two labels have fewer edits, zero have more edits, and one changed its text
without changing its edit count. That last change matters: unchanged CER is
not proof of preserved meaning or characters. Raw decisions were 205 baseline
lines, 217 duplicate tile lines, 34 tile-edge cuts, six overlap-review records
and nine accepted new proposals. These are detector proposals, not nine proven
new text units. Unmatched regions increased from 47 to 53; the dataset does not
have complete text/role labels, so this is not a false-positive rate.

Selected observations from original pixels and paired transcripts:

- MN109-04/b02 became assigned, but reads only the final part of the visible
  phrase. Assignment recovered is not complete transcription recovered.
- MN109-05/b08 now reads a character sequence more faithful to the visible
  annotation; the supplied label itself appears to disagree on another
  character. This is a review proposal, not an independently verified gold fix.
- MN109-05/b06 gained a small extra character while retaining the same edit
  count. The added small-source contribution needs review, not automatic merge.
- Some new proposals on MN109-06 and MN109-08 lie over textured artwork;
  others include visible SFX omitted from the supplied labels. Neither small
  size nor unmatched status is enough to declare a proposal irrelevant.
- MN109-08's large left-hand source crop already contains both supplied b03
  and b04 texts. Its failure to fit the diagnostic assignment rule does not
  establish that all their text was absent from the detector/OCR. Do not change
  the benchmark rule simply to count that union as two exact strings.

## Timing and conclusion

Detection was about 5.2–5.6 seconds on the seven later pages; the first page
took 32.2 seconds including cold startup. OCR in the separate process took
about 5.7–12.0 seconds on later pages; its first page took 15.7 seconds including
startup. Recorded detection-replay time is only JSON/geometry lookup and must
not be reported as detector inference latency. There are no end-to-end browser,
translation or population-p95 measurements, and peak RAM was not measured.

This is too costly for its measured quality gain and does not approach the
cloud-page target. Do not tune repeated tile thresholds on these eight pages.
The next useful seam remains line/crop ownership and genuinely different
image-grounded recognition for disputed regions, not indiscriminate tiling.
Any future runtime fallback needs independent calibration, reviewable unresolved
sources, reader-exclusion preservation and a separate resource/cost decision.

## Verification and reproduction

New geometry/replay and benchmark tests passed. Temporarily returning only
baseline records made the two new-proposal recovery assertions fail; restoring
fusion made them pass. Full Python: **1343 passed, 1 skipped**. TypeScript:
**60 passed**; typecheck and extension build succeeded. These regressions do
not certify real-manga OCR or integrated lettering quality.

Private JSON artifacts under ignored `artifacts/`:

- `private-tiled-detection-v1-20261017.json`: fresh full/tile detections;
- `private-pages-tiled-recall-v1-20261017.json`: fresh OCR on those source crops;
- `private-tiled-v1-paired-20261017.json`: paired per-label deltas;
- `private-tiled-v1-stages-20261017.json`: diagnostic stage counts.

Do not overwrite them or include them in a release. To reproduce, use new
output paths with these two phases:

```powershell
.\.venv\Scripts\python.exe -B scripts/probe_tiled_detection.py --folder '<private folder>' --threads 4 --output artifacts/<new-detection-report>.json
.\.venv\Scripts\python.exe -B scripts/probe_tiled_detection.py --folder '<private folder>' --threads 4 --recognize-from artifacts/<new-detection-report>.json --output artifacts/<new-ocr-report>.json
```
