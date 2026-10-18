# Vietnamese translation gold protocol

The private Manga109 package currently supplies Japanese crop labels, not an independently reviewed Vietnamese translation set. OCR exact-match, prompt guards, or a successful JSON response must therefore never be reported as translation quality.

For independent reference preparation, `scripts/export_gold_review.py` now creates
a private text-only draft under `artifacts`. It preserves raw source candidates,
audit exclusions and dataset fingerprint; reviewed Japanese/Vietnamese fields
start empty and human-review attestation starts false. This is **not** the
completed `reviews.json` below and cannot pass the quality gate. See
[the implementation checkpoint](roadmap-implementation-20261016.md) for commands.

## Pixels-first Japanese review

Use `--blind` when preparing the first transcription pass. This removes both
supplied Japanese and Vietnamese candidate strings, while preserving original
geometry, dataset fingerprint and audit exclusions:

```powershell
.\.venv\Scripts\python.exe scripts\export_gold_review.py --folder '<private source folder>' --blind --output artifacts/<new-private-review-draft>.json
```

The output is still an **unreviewed development draft**. Its `counts.pages` and
`counts.bubbles` describe the declared source; `counts.eligible_pages` and
`counts.eligible_bubbles` describe the rows actually available for review after
audit exclusions. Do not mistake declared coverage for eligible coverage.

Read the original pixels without candidate labels or predictions first. Keep
literal crop contents, clipped/uncertain strokes and any completion from wider
page context separate. A supplied box may clip an utterance or span several
balloons; it does not establish one complete semantic unit. Preserve hearts,
pauses, drawn-out endings and other expressive marks, recording uncertain
Unicode encodings instead of dropping them to improve exact match.

Freeze the private readings and their hash **before** revealing labels or
outputs. Compare disagreements afterward without rewriting the original
dataset or using those readings to select a runtime transcript. An independent
AI reading can propose corrections and Vietnamese meaning notes, but cannot
attest independent human review, supply accepted gold, authorize erasure or
establish held-out accuracy. Report its coverage and uncertainty separately;
do not replace the historical benchmark denominator or score silently.

## Translation-run review

When a translation run is ready for review, keep the following two files outside the repository:

`predictions.json`

```json
{
  "schema": 1,
  "dataset_fingerprint_sha256": "fingerprint printed by benchmark.py",
  "run": {
    "id": "unique-run-id",
    "model": "exact-provider-model-id",
    "prompt_version": "exact-prompt-version",
    "source_ocr_fingerprint_sha256": "sha256 of the exact OCR input snapshot, 64 lowercase hex characters",
    "context_fingerprint_sha256": "sha256 of the exact context snapshot, 64 lowercase hex characters"
  },
  "rows": [
    {"page_id": "MN109-01", "bubble_id": "b01", "vi": "Bản dịch cần rà soát"}
  ]
}
```

`reviews.json` describes this exact run, not a generic translation. A reviewer must label every prediction and mark whether it belongs to ordinary held-out dialogue:

```json
{
  "schema": 1,
  "dataset_fingerprint_sha256": "same fingerprint",
  "prediction_fingerprint_sha256": "canonical hash printed by the command below",
  "rights_confirmed": true,
  "independent_human_review": true,
  "reference_review": {
    "source_japanese_reviewed": true,
    "vietnamese_reference_reviewed": true,
    "independent_of_predictions": true,
    "reviewed_by": ["gold-reviewer-1"]
  },
  "reviewer_count": 1,
  "rows": [
    {
      "page_id": "MN109-01",
      "bubble_id": "b01",
      "split": "heldout",
      "difficulty": "ordinary",
      "reviewed_by": "reader-reviewer-1",
      "serious_error_types": []
    }
  ]
}
```

`serious_error_types` is intentionally human-labeled. Allowed values are `meaning`, `negation`, `speaker`, `pronoun`, `term`, `omission`, and `addition`. A missing label is not treated as success. The gate excludes `hard` and `development` rows from the ordinary held-out threshold, but reports them separately.

These `true` values are examples of a completed **human** review, not template defaults or flags an AI may fill in. Japanese source and Vietnamese reference must actually be reviewed independently of the output being scored. `reviewer_count` must be an integer from 1 to 20 matching the distinct row-level reviewers, not a boolean or an invented team size. Reviewer IDs may be pseudonyms; no personal names are required.

Bind reviews to the exact output and run metadata before review:

```powershell
.\.venv\Scripts\python.exe -B scripts\translation_quality_gate.py --prediction-fingerprint 'C:\private\predictions.json'
```

The hash covers the entire prediction JSON canonically, including output, model/prompt/source/context provenance and row order. Whitespace/key-order formatting does not change it. Changing a translation or run metadata invalidates the old review; do not recalculate the hash to carry old judgments over to a new run. This command only prints a hash; it does not declare a human review, modify a file, call a model or spend credits.

Run:

```powershell
.\.venv\Scripts\python.exe scripts\translation_quality_gate.py `
  --dataset-folder 'C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001' `
  --predictions 'C:\private\predictions.json' `
  --reviews 'C:\private\reviews.json' `
  --output 'artifacts\private-translation-quality.json'
```

The command exits with code 2 until the full eligible set has independently reviewed Vietnamese references, explicit error judgments, rights/review attestation and at least one ordinary held-out row. Missing gold/coverage produces a structured not-ready report; malformed or stale provenance is rejected. Data audit issues still block acceptance. Do not alter the original private labels or exclude failures just to pass; prepare a separately frozen, independently reviewed benchmark and keep its relation to the original source documented.

Exact/CER are lexical diagnostics, not meaning scores. Group metrics expose ordinary/hard and held-out/development separately. A one-row synthetic fixture may verify gate mechanics but cannot certify the extension's <=2% target or representative production quality. The gate records human attestation; it cannot prove that a person actually did the review or that the model has never seen the held-out title.
