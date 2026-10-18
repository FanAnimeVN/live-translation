# OCR quality ceiling checkpoint — 2026-10-16

This is a private development diagnostic for the fingerprinted Manga109 set
`445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`.
It is not independently reviewed gold: eight eligible pages contain 78 supplied
Japanese labels, with no accepted Vietnamese or clean-background reference.

## What the current evidence permits

| Route | Coverage | Exact against supplied labels | CER | Decision |
|---|---:|---:|---:|---|
| PP-OCRv5 + manga-ocr whole page | 62/78 | 35/78 | 28.65% | production control |
| CTD line comparator | 63/78 | 44/78 | 16.72% | review-only comparator |
| PP→CTD missing-only replay | 74/78 | 45/78 | 18.85% | review-only, ownership unproven |
| manga-ocr on supplied crop boxes | 78/78 | 48/78 | 9.37% | recognizer control |
| Cheap preprocessing oracle (base/autocontrast/unsharp/threshold) | 78/78 | 49/78 | 8.84% | diagnostic lower bound only |
| Gemini cloud crop pilot | 78/78 | 39/78 | 13.31% | no promotion |
| Haiku cloud crop pilot | 36/78 attempted | 19/36 | 12.86% | incomplete; no promotion |

The preprocessing probe changed no runtime defaults. Autocontrast tied the
baseline; unsharp and thresholding regressed. The 49/78 oracle is calculated
after reading labels and therefore cannot be used as a reader selector. It only
shows that inexpensive image filters are not the missing path to 78/78.

An oracle that chooses the best available recorded recognizer/crop route reaches
about 56/78 on this development set. That is an upper bound for the existing
evidence, not a production score. The remaining errors are a mixture of missed
or fragmented detector regions, stylized/scene text, punctuation and a number of
labels that have not been independently checked against the pixels.

## New geometry probes

Two geometry-only probes were run against the same frozen crops:

- Rotating tall crops by 90 degrees changed 56 of 57 candidates, but produced
  only 1 exact row and increased edits on those rows from 61 to 671. It is
  rejected; vertical Japanese must not be rotated blindly for this recognizer.
- Projection-based line/column splitting produced 29 candidates. It reduced
  exact rows on those candidates from 19 to 9 and increased edits from 28 to
  72. It is also rejected; a projection run is not a reliable glyph/line
  boundary on these scans.

These results narrow the next useful seam: use a detector with explicit line
ownership and preserve its source members, rather than inventing boundaries
inside a supplied crop. The private review queue in
`artifacts/private-ocr-review-queue-20261016.json` records the three existing
recognizer alternatives without promoting any one of them. Of 78 rows, 9 are
unanimous non-matches, 14 have three-way disagreement, 19 have partial
disagreement, and 36 agree with the supplied label. The 9 unanimous rows are
not proof that all three models are wrong: several supplied labels visibly
contain OCR/annotation inconsistencies, so a Japanese reviewer must verify
pixels, box ownership and reading order before adaptation.

## Consequence

No tested one-line change has taken this pipeline to 78/78. The recorded
predictions cannot reach that score even with post-hoc selection. That is not
a proof that a new recognizer, grouping method or source-grounded review cannot
do better. Gold-based answer selection and stripping expressive punctuation are
not valid shortcuts. The next evidence cycle is:

1. Independently review Japanese text, boxes, reading order and roles; mark
   uncertain labels instead of forcing an exact string.
2. Add clean-background and Vietnamese references before tuning translation or
   erasure. Keep development and title-held-out splits separate.
3. Evaluate a stronger recognizer or bounded independent verification before
   committing to training. If adaptation is needed, use permissioned data with
   vertical/stylized/balloonless and SFX strata, then validate on held-out pages.
4. Improve detector ownership and grouping separately. A secondary detector may
   add only an explicitly reviewable source record until ownership is proven.
5. Use cloud page/crop OCR only with a separate user opt-in and reconciled cost;
   a successful authored crop does not establish full-page recall.

No Edge test, paid request, default model switch, or production promotion was
made by this checkpoint.

The next adaptation seam is `scripts/build_ocr_training_manifest.py`. It refuses
the current draft before writing anything, and requires independent Japanese
review, rights confirmation, exact source identity/geometry and explicit train
versus title-held-out splits. This is preparation for a later permissioned
recognizer adaptation; it is not a claim that training has already improved OCR.
