# Implementation checkpoint — approved desktop roadmap

Priority remains correct meaning → integrated lettering → continuous reading.
This checkpoint starts the approved roadmap; it does not mark all seven stages
complete or change the production OCR/translation defaults.

## Implemented in this slice

- Portable `cloud-first` profile, without local GGUF translation/summary or
  llama.cpp requirements; full offline bundle remains explicit and compatible.
- Installer completeness checks understand the new profile but still reject
  incomplete/corrupt OCR or detector assets. Reader origins and dataRoot remain.
- Fresh owned pytest temporary trees for packaging, retaining the full test gate.
- Primary external comparator is manga-image-translator; Comic Translate remains
  secondary/permissive, Kites optional UX only. No GPL implementation enters the
  product bundle.
- `scripts/comparator_preflight.py` reads pinned Git objects as data, records
  code hashes, model mappings and I/O call locations, and does not import or run
  upstream. Pin independently resolved with `git ls-remote`: 
  `d6de6ab62a7be6afc0d07a3184149cdefbcd32f2`.
- `scripts/export_gold_review.py` generates a private Japanese/Vietnamese draft
  with unreviewed defaults, raw source candidates, grouping/role/meaning/style
  review fields and the original dataset fingerprint. No predictions are used.
- `scripts/diagnose_stage_failures.py` classifies observable detector
  miss/partial, grouping cross-label/fragmentation, OCR mismatch/empty, and
  exact single/multi-region assembly. It keeps the page benchmark's
  fingerprint and containment rules and never treats unmatched text as
  irrelevant.

## Real source/data observations

The comparator is stored under ignored `artifacts/comparators`, not distribution.
Static preflight found 32 I/O/checkpoint review call locations in the inspected
files. These are leads, not a complete I/O security proof. Stock upstream has
image/text logging and model-download paths, so `execution_allowed` stays false.
Its LaMa mapping uses a mutable Hugging Face `main` URL despite a content hash;
resolve the revision and audit weight/font licenses before provisioning.

The private draft contains 78 eligible labels and preserves two audit issues.
Fingerprint remains
`445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`.
The original dataset was not modified. `independent_human_review=false`, no
reviewer is invented, and the set remains development, not held-out. Background
gold remains unknown. Do not use this draft as accepted translation gold.

The stage diagnostic on production v20 reports 29 exact single-region rows and
6 exact ordered multi-region assemblies (35/78 total), 10 grouping mismatches,
17 OCR mismatches, 14 partial detector overlaps and 2 detector misses. CER is
28.65% on the supplied labels. A threshold .4 candidate and forced-long-edge
1600 candidate lower CER but lose exact rows, so neither is promoted.

The next OCR probe tested four RAM-only preprocessing variants on all 78 crop
boxes. Base and autocontrast both reached 48/78; unsharp reached 44/78 and a
binary threshold reached 38/78. The post-inference oracle across those variants
was only 49/78, so no preprocessing transform was enabled in production. The
full evidence and the reason a 78/78 claim is not currently supportable are in
[ocr-ceiling-20261016.md](ocr-ceiling-20261016.md).

The next annotation seam is now implemented as
`scripts/import_manga109_xml.py`. It accepts a caller-supplied, permissioned
Manga109 XML volume directory plus an explicit local-page map, checks XML
geometry against the fingerprinted private images, rejects DTD/entity input and
writes only bounded text/boxes into a new private review artifact. It does not
copy images, claim independent review, create Vietnamese/background gold, route
runtime OCR or grant erasure/memory authority. The adapter has three regression
tests and is intentionally unable to satisfy the training manifest until a
reviewer fills the Japanese/geometry/role/split fields.

`scripts/build_ocr_training_manifest.py` now provides the next safe seam for
recognizer adaptation. It refuses the current unreviewed draft and requires a
matching fingerprint, rights confirmation, independent Japanese review, source
geometry, reviewer attribution and explicit train/held-out splits. It emits no
image bytes and cannot be used to train on held-out rows.

```powershell
.\.venv\Scripts\python.exe scripts/comparator_preflight.py --output artifacts/manga-image-translator-preflight-20261016.json
.\.venv\Scripts\python.exe scripts/export_gold_review.py --folder 'C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001' --output artifacts/private-independent-gold-draft-20261016.json
```

Evidence commands refuse to overwrite recorded output. Use a new filename for a
new run. The private draft contains copyrighted source text: keep it local and
uncommitted. No raster is written by either command.

## Remaining stage gates

| Stage | Not yet accepted |
|---|---|
| 0 — Working group demo | Actual failing personal Edge connection; clean-Windows installs; two real-page inference sessions |
| 1 — Trustworthy small gold | Independent human Japanese/Vietnamese, grouping/role/protected-art review |
| 2 — Whole-pipeline comparison | Audited RAM-only adapter, isolated dependencies, verified assets/fonts, paired inference and resource measurements |
| 3 — Meaning/culture/memory | Production utterance/presentation integration and independent model/context evaluation |
| 4 — Integrated lettering | ≥95% ordinary-balloon acceptance on real data; difficult artwork separately |
| 5 — Continuous reading | Accepted quality pipeline, split cache retention, measured p95/RAM targets |
| 6 — Beta | ≥100 pages/1,000 crops, title-held-out review, five readers, clean install/update/rollback acceptance |

Preserve current source anchors, reader locks, cutoff, cache provenance and exact
original restoration. No automatic default promotion, paid call, dataset expansion,
training, registry repair or broad personal-browser access is implied by these
completed preparatory steps. Existing cloud reservations require reconciliation
or a separately approved budget before another paid inference run.
