# Can OCR go directly to 78/78?

Checked 2026-10-17 using public primary sources and existing project records.
No inference, model download, private-data upload, credential access or paid call
was performed.

## Conclusion

**Inference:** a stronger model or ensemble is a valid experiment, but neither
supports a promise of automatic 78/78. The existing recorded candidates cannot
produce 78/78 even with answer-aware selection: the diagnostic oracle is about
56/78. A new image-grounded pass could supply missing correct candidates; its
gain on this private set is unknown. Human-verified corrections could produce
an assisted result, which must be reported separately from automatic OCR.

**Existing project evidence, not a new measurement:** the full-page production
route is 35/78 exact and manga-ocr on supplied boxes is 48/78. Supplied Japanese
labels remain unreviewed. These are development diagnostics, not a held-out
accuracy claim. See [ceiling checkpoint](ocr-ceiling-20261016.md) and
[current 78/78 evidence](ocr-78-path-20261016.md).

## What the primary sources establish

- **Author guidance:** manga-ocr supports multiline crops, but longer text is
  more error-prone; smaller crops may help a failed portion. The author warns
  that it attempts text even on blank input and can invent plausible Japanese.
  Its examples are explicitly selected demonstrations, not an accuracy bound.
  [manga-ocr usage tips](https://github.com/kha-white/manga-ocr#usage-tips).
- **Source behavior:** upstream postprocessing removes whitespace, replaces
  ellipses and repeated dot-like characters, and converts ASCII/digits to full
  width. This is output normalization, not image-based error correction. Keep
  raw evidence and the project's punctuation-preserving evaluation; do not
  copy these transformations into a global repair rule.
  [manga-ocr implementation](https://github.com/kha-white/manga-ocr/blob/master/manga_ocr/ocr.py).
- **Another manga recognizer, author-reported:** Baberu is a bubble-crop
  recognizer requiring upstream detection. Its card documents dakuten/handakuten,
  rare-kanji, small-kana and long-crop failures. Its Japanese training labels
  were distilled from manga-ocr. Its advertised lenient CER removes whitespace
  and decorative symbols and unifies dot runs; that is not this project's exact
  transcription metric. Public benchmark performance does not establish private
  78/78, and Japanese teacher/student agreement is not independent verification.
  [Baberu model card](https://huggingface.co/genshiai-daichi/baberu-ocr).
- **Pipeline precedent:** mokuro explicitly separates comic-text-detector from
  manga-ocr recognition. Better recognition alone does not establish full-page
  coverage. [mokuro](https://github.com/kha-white/mokuro).

## Smallest useful next experiment

**Proposed experiment, not a demonstrated improvement:** use two stages on a
frozen, reviewed Japanese pack. First retain detector source members, exclusions
and crop ownership while running the primary recognizer. Then send only missing
or uncertain IDs to one bounded, independently image-grounded verifier; have it
read the original pixels before seeing the first transcript. Permit at most one
justified recrop/line-owned retry per failed ID. Preserve both readings and mark
unresolved disagreement for review. A majority vote or fluent text autocorrect
cannot establish which characters are visible; agreement also needs calibration
against reviewed pixels. Do not infer speakers, erase art or write story memory
from unresolved OCR. Any cloud verifier needs the applicable upload/cost consent.

Measure crop exact match/CER and full-page missing/partial/overmerged text
separately, including punctuation and difficult text; report new errors,
unresolved/assisted counts, latency and RAM. Freeze selection rules before
scoring, with no label-aware runtime selection. Consider fine-tuning only if
reviewed residual errors show a persistent learnable pattern and permissioned
training data can be separated from unseen-title evaluation. It is conditional,
not a prerequisite or a guarantee of perfection.

**Gold scope:** OCR needs reviewed Japanese transcription, geometry, ownership,
reading order and coverage, including uncertain labels and explicit punctuation
rules. Vietnamese meaning references are for translation acceptance;
clean-background/glyph-mask references are for cleanup acceptance. Their absence
does not block OCR experiments or explain OCR recognition errors. Reviewing the
already-tuned 78 rows does not turn them into a held-out set.
