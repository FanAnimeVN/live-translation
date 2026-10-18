# Private benchmark recheck — 2026-10-15

Input was read from the user-provided folder
`C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001` without copying
or packaging its images. SHA-256 fingerprint:
`445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`.

## Audit

- 10 pages / 81 labels total.
- 8 eligible pages / 78 eligible Japanese crop labels.
- `SL-01` has a declared-vs-actual image-size mismatch.
- `MN109-10` duplicates `MN109-01`.
- 0 eligible Vietnamese reference translations and no clean-background/glyph-mask gold.
- Japanese transcriptions remain user-supplied and independently unverified.

Because the audit contains issues and lacks Vietnamese/clean-background gold,
the perfect gate and translation-quality certification are intentionally not
available.

## Crop oracle OCR (ground-truth boxes)

`manga-ocr/0.1.14-local-v3`, CPU, 4 threads, warm crop loop:

- 48/78 exact (`61.54%`).
- Normalized CER `9.3717%`.
- p50 `524.08 ms` per crop; p95 `742.03 ms`.
- Model load `35.49 s`.

This is an OCR crop result, not a full-page or Japanese→Vietnamese score.

## Full-page production pipeline

The production detector/OCR/cleanup path was run on all 8 eligible pages with
images held in RAM. It produced 132 regions, assigned 62/78 annotations,
35/78 exact aligned strings, diagnostic aligned CER `28.6475%`, and 42
one-to-one IoU≥0.50 assignments. Warm page OCR was approximately 5.25–13.82 s
in this CPU run; the first detector page included a 20.94 s model-load cost.
Cleanup p50 after the first page was approximately 83.51 ms. There were 52
transient patches and 4 deferred regions.

The full-page gap is evidence for continued grouping/detection work. It is not
permission to promote an experimental detector, drop secondary text, or claim
perfect manga reading.

## Detector resize comparator (not promoted)

The same full-page run with PP-OCRv5 `limit_side_len=1280` produced 115
regions, assigned 61/78 annotations, 33/78 exact aligned strings, diagnostic
CER `25.8786%`, and 41 one-to-one IoU≥0.50 assignments. It lowered CER but
lost coverage and exact matches versus the current default (132 regions,
62/78 assigned, 35/78 exact), so the resize is not adopted as the default.

