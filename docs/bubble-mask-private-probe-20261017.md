# Actual instance-mask ownership ablations — 2026-10-17

Two complete offline CPU experiments, not a release/default or cloud feature.
No personal Edge install, paid inference, private image upload, gold correction,
training or raster persistence. This follows the rejected all-source unions;
it tests a genuinely different learned container boundary, not another box
threshold or the existing ogkalu detector renamed as a new model.

## Acquired and inspected, not just proposed

The separate comparator uses the published YOLO11n balloon ONNX export at
`6839b4ea9d95be14f5bbd21ac675d92a7da95ed0`, **11,845,329 bytes**, SHA-256
`593cae61f4c9ffc773fee34d55c28069390d19415c24dc04600f983311618ea3`.
Explicit setup downloaded and locally verified it; inference never downloads.
[Publishing commit and contract](https://huggingface.co/mednasserallah/manga109-segmentation-bubble-onnx/commit/6839b4ea9d95be14f5bbd21ac675d92a7da95ed0).
The producer/export/data/base-weight permission gaps remain as documented in
the [primary-source review](bubble-ownership-primary-20261017.md). The file is
in ignored comparator storage, not installer/product assets. Manga109-based
training means this small development pack is not evidence of title-held-out
segmentation generalization.

Before runtime load, the actual graph was decoded using the declarative
protobuf descriptor from the official ONNX 1.22.0 CPython-3.12 Windows wheel
(17,213,290 bytes, SHA-256
`72ccebab3bac07215c204ce8848d42e78eaaa666badbf72d25cd359b9f269e3a`).
The wheel is neither installed nor imported: AST/literal parsing extracts the
serialized schema for the already installed protobuf decoder. No downloaded
Python, pickle, Ultralytics or custom native model code is executed.
[Official wheel metadata](https://pypi.org/pypi/onnx/1.22.0/json).

Observed graph: IR 8, standard opset 17, no external tensors, custom domains,
model functions or training graphs. Exact float32 contract: `images
[1,3,1024,1024]` → `output0 [1,37,21504]`, `output1 [1,32,256,256]`.
ONNX Runtime 1.23.2 CPUExecutionProvider runs with two intra-op/one inter-op
threads. This is graph identity/compatibility, not proof of downstream rights,
accuracy or the 4 GiB peak-memory target; process peak RSS was not measured.

## Fixed preprocessing and private experiment

The independent adapter centers RGB input on a 1024-square 114-grey letterbox,
using OpenCV linear resize and actual rounded dimensions for inverse mapping.
Scored proposals at ≥0.25 undergo deterministic IoU >0.7 NMS, retaining original
candidate index, score, box, coefficients and suppression decisions. Each mask
is reconstructed from its own coefficients/prototypes and cropped to its box
**before** upsampling. Only bounded source-space ROI bitmaps stay in RAM: at
most 64 instances/24 million total mask pixels. Raster masks/contours are never
written or given to cleanup. None of these thresholds was fitted to gold.

Both experiments use the frozen eight pages/78 supplied labels and CTD parent
with all 143 exact member polygons in 80 original regions. CTD text detection
is retained, not rerun; only container inference and recognition are fresh.
The first historical report's generic `fresh_detection:true` meant container
inference, not a new text detector. The script now distinguishes these fields
explicitly; that historical evidence is not rewritten.

### V1: regroup by unique container

A member is owned only with ≥98% raster coverage from one mask and no positive
coverage from competitors. Partly uncertain original units remain intact and
block associations involving their already-owned members. Complete units may
be split/grouped by owner, but every source member remains recoverable and no
scope/speaker/erasure/memory authority is granted.

36 predicted instances give 82/143 members a unique predicted owner; this is
**coverage, not independently scored ownership accuracy**. Regrouping produces
75 units and fresh manga-ocr gives **41/78**, 196/939 edits, CER **20.87%**.
Against CTD 44/78 and 157 edits: **zero** improved labels, five regressions,
three containment assignments lost. **Rejected.**

Original MN109-05/MN109-08 pages with predicted contours were inspected through
RAM-only previews. A connected multi-lobed balloon can contain multiple text
blocks, while frameless dialogue remains outside learned containers. A
container identity is not an utterance, speaker, reading-order or crop decision.
The failed grouping is not evidence that such uncovered text is irrelevant.

V1 container+decode time was 0.435–0.535 seconds/page, summed 3.893 s over eight
pages; grouping 0.033 s; summed OCR/diagnostics 71.142 s. Detector load was
0.866 s and recognizer load 15.176 s. These are stage observations, not full
wall time, live translation latency or a population p95. No cloud translation
was part of either run.

### V2: isolate OCR input, retain every original unit

The second ablation does **not** coalesce/split original boxes, IDs or polygons.
It changes only temporary recognizer crops: pixels outside a uniquely owned
container are white. Every member's entire raster polygon must be supported,
not merely 98%; one unsupported pixel, a mixed/unknown owner or a crop crossing
source geometry vetoes the transform. The original image/display never changes.
Each prepared crop binds the original exact pixel hash/size; stale/reordered
inputs fail rather than receive another region's preprocessing.

Of 80 crops: 19 changed; 11 already needed no background change; four failed
complete-coverage checks; 46 had unknown/multiple ownership. Fresh OCR gives
**44/78**, 156 edits, CER **16.61%**, with unchanged assignments and 80 regions.
The supplied-label diagnostic improves one edit count and regresses none.

**Still not promoted.** Source inspection of that sole changed label,
MN109-06:b07, reveals a heart-shaped expression mark in both original and
isolated crops. The new recognizer omits it, whereas the older output retains
it; the supplied reference also differs at this expression. Thus the numeric
CER gain does not establish fidelity and may reward expression loss. The
assistant inspection was post-prediction/non-blind, not independent accepted
Japanese gold. A private pending-review record retains exact source/report
provenance; no label is corrected and it is not training-eligible. Do not strip
symbols or choose output by reference distance to hide this conflict.

V2 summed container/decode was 5.243 s, grouping/preparation 0.098 s and
OCR/diagnostics 57.251 s; loads 0.604 s detector / 12.038 s recognizer. Different
resource/cache conditions mean these two small runs are not a controlled speed
comparison. The unchanged 2 GiB launch gate passed; it was not lowered.

## Code and verification

New isolated script: `scripts/benchmark_bubble_masks.py`. Tests exercise real
letterboxing, output validation, single-candidate mask decoding, source grouping, crop
isolation and current-crop binding, substituting only the external model or
recognizer boundary. Red/green cases caught missing implementation, decoded
mask arithmetic overflow and a CLI ordering bug that could provision before
rejecting mixed offline/setup flags. Mixed provisioning/inference is now
rejected before any network/file operation.

This checkpoint does not include a dedicated multi-candidate NMS suppression
regression or an authored full-CLI integration test. The two actual private
CLI runs are execution evidence, not a substitute for those test boundaries.

Final checks on this source state: **1,485 Python passed / 1 skipped** (50.00 s),
**61 TypeScript passed**, typecheck and extension build passed. These protect
software behavior, not Japanese/Vietnamese/lettering quality. No package or
installed-browser update was made. The source plane remains protected; the
production baseline is still **35/78** and no new model/default is promoted.

Private ignored evidence:

- `artifacts/private-bubble-mask-ctd-grouping-v1-20261017-r6.json`
- `artifacts/private-bubble-mask-original-ocr-isolation-v2-20261017-r6.json`
- `artifacts/private-bubble-mask-expression-review-pending-20261017-r6.json`

Reproduction after explicit separate provisioning:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_bubble_masks.py --fetch-model --setup-inspector --inspect
.\.venv\Scripts\python.exe scripts/benchmark_bubble_masks.py --folder '<private folder>' --primary artifacts/private-pages-ctd-retained-lines-t2-20261017-r3.json --threads 2 --output artifacts/<new-grouping-report>.json
.\.venv\Scripts\python.exe scripts/benchmark_bubble_masks.py --folder '<private folder>' --primary artifacts/private-pages-ctd-retained-lines-t2-20261017-r3.json --isolate-ocr-crops --threads 2 --output artifacts/<new-isolation-report>.json
```

Next quality-bearing work must preserve the distinction between **recognition
crops, source records, containers, semantic utterances and lettering regions**.
Resolve the actual expression/reference conflict and ownership/reading-order
failures on pixels; neither a good-looking mask nor lower aggregate CER is a
reason to merge utterances, silently drop text or allow erasure. Independent
Japanese/Vietnamese/clean-art review, held-out quality and live-reading gates
remain unfulfilled. The goal remains active, not release-ready.
