# Pixels-first source review — 2026-10-17

## Purpose and boundary

Separate source-label/crop problems from real recognition failures before
another grouping or recognizer change. The existing context proposal has
already been implemented within evidence/cutoff/consent limits; repeating
model-default changes cannot recover characters missing before translation.
See [context implementation](context-memory-cloud-20261017.md) and
[the model-claim delta](context-proposal-delta-20261017.md).

`scripts/export_gold_review.py --blind` now produces a pixels-first draft
without supplied Japanese or Vietnamese candidate strings. Original geometry,
audit exclusions and dataset fingerprint remain. Reviewed fields and human
attestation remain empty/false. A regression proves the candidate strings are
absent without changing source bytes. The existing candidate-assisted mode is
retained and explicitly labeled. See [review protocol](translation-gold-protocol.md).

The blinded research agent reads original pages and enlarged crops in RAM,
without supplied transcriptions or recorded OCR predictions. Its result is
**independent AI review proposals**, not independent human gold, accepted
translation references, training examples or a runtime OCR verifier. A wider
page completion is recorded separately from literal crop coverage. The source
dataset is not edited, and this repeatedly used set remains development data.

## Frozen priority checkpoint

The first checkpoint contains all **27** rows on three priority pages. Its
SHA-256 was frozen before post-read comparison:
`410d5717d96f7189af91f8f80bff3b53e1456784a9d09989ba5aba0ffd7dada6`.

- **21** proposals marked clear; **6** retain explicit uncertainty/clipping.
- **9** differ from supplied labels under the existing NFKC/whitespace metric,
  including **7** marked clear by the AI reader. These are disagreements to
  review, not nine confirmed label corrections.
- Observations include missing expressive marks, questionable lexical labels,
  crop-edge truncation and more than one balloon inside a single supplied box.
- Main-agent inspection of the three original pages corroborates several
  visible issues, but took place after predictions/labels and is not a second
  blind or human review.

Private raw readings and post-freeze comparisons stay under ignored
`artifacts/`; no source image, crop, mask or screenshot is written. The
comparison does not change historical labels, score, runtime selection,
speaker identity, memory trust or erasure permissions. A production transcript
can agree with an incorrect label, or disagree because it preserves a visible
pause: exact match alone cannot settle the source reading.

## Verification and current quality status

The completed blinded pass now covers **78/78 eligible rows on 8/8 pages**:
**60 clear, 17 uncertain, 1 unreadable**. It includes proposed Vietnamese
meaning notes, not accepted references. All source IDs and bboxes were checked
against the blind draft and original labels without changing either. The final
private JSON was frozen before comparison with SHA-256:
`9edb3902a218991b17cf9286c744be2ae30d8d229a85d9380476332cb694f447`.
The original priority checkpoint is unchanged; final refinements made while
still blinded are documented in the new final report, not backdated into it.

Among the **60** clear AI proposals, **25** differ from supplied labels under
the existing comparison normalization. These include lexical and coverage
issues as well as expressive-mark/Unicode encoding differences; they are not
25 human-confirmed corrections. Six production predictions agree with the
supplied label but disagree with the clear AI proposal; six show the reverse.
Thus reference agreement must not be treated as pixel verification. No revised
exact/CER score is declared from the AI proposals.

An additional retained-geometry audit distinguishes empty alignment from actual
absence. **16** supplied rows receive no assigned production prediction;
**14** nevertheless have a positive-area intersection with a retained region,
and **2** have none. Overlap is not glyph coverage or ownership. Inspection of
the retained outputs specifically confirms that MN109-06:b01 has recognized
lexical text and MN109-08:b04 occurs inside an overmerged recognized region,
despite their empty aligned strings. Calling every empty alignment a dropped
line would be incorrect. These cases still require grouping/ownership and
expression fixes; they are not excused or counted twice to raise the score.

Additional private evidence:

- `artifacts/private-pixels-first-japanese-reading-20261017-r12.md` and `.json`:
  complete frozen blinded proposals.
- `artifacts/private-pixels-first-comparison-all-20261017-r12.json`:
  post-freeze label/prediction comparison, source geometry unchanged.
- `artifacts/private-pixels-first-alignment-audit-20261017-r12.json`:
  numeric overlap/assignment distinction, no new inference or regrading.

Full Python regression: **1,505 passed, 1 skipped**, 54.65 seconds. A pytest
cache-write permission warning did not fail tests; isolated test data stayed
under ignored artifacts. **62 TypeScript tests**, typecheck and extension build
passed. These are software regression checks, not semantic or OCR gains.

Production OCR remains **35/78 exact, 269/939 edits** against the unchanged,
unreviewed supplied labels. No recognizer/grouping default is promoted here.
The earlier presentation-v21 improvement remains separate. No new detector or
recognizer run, project paid API request, credential access, download, personal Edge operation,
installer or release package was involved in this checkpoint.

The next quality-bearing step is validating the disputed source readings and
ownership, then testing a narrow grouping/recognition change on those actual
failure classes. The AI pass is complete, human validation is not. Uncertainty
remains explicit; do not replace labels with AI proposals or remove punctuation
to claim 78/78. Missing Vietnamese/background gold does not block Japanese OCR
experiments, but AI meaning notes do not satisfy translation acceptance.
