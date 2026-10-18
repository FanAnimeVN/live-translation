# Live translation

Standalone manga translation extension and Windows companion. Do not modify other projects.

Keep images in RAM. Never commit private datasets, API keys or users' story memories.
Offline mode must never call a cloud API or perform metadata lookup.
Every remembered event has a chapter/page cutoff and evidence. Unknown speakers remain unknown.
Preserve directed pronoun rules confirmed by users. Do not add future facts to earlier chapters.
Retained sibling vocatives already carry their title: nee-chan, not chị nee-chan/chị gái nee-chan;
onii-chan, not anh onii-chan/anh trai onii-chan. Do not remove legitimate later Vietnamese pronouns,
localize narrative kinship mechanically, or override an explicit reader-locked exception.
This no-stack rule also covers an exact standalone sibling call with missing OCR punctuation;
do not broaden it to narrative phrases or change the source quotes to conceal OCR errors.
Model downloads use pinned revisions and checksums; inference must not download executable custom code.
Build and test before packaging. Report measured latency, not an unverified promise of instant translation.

## Reader-first acceptance rules

Current MVP milestone: desktop Windows + Edge/Chrome only. Defer mobile-specific
work until desktop live reading is stable; retain existing responsive regressions
without claiming mobile readiness or weakening desktop quality/restoration gates.

Priority: correct meaning -> lettering integrated into the original artwork -> continuous reading -> extra features.
Target a 16 GB RAM machine without a discrete GPU. Acceptance targets are not achieved results:
warm first bubble p95 < 5 s; cached display p95 < 200 ms; a standard page of <= 12 bubbles
p95 < 15 s local / < 8 s cloud; serious translation errors <= 2% on held-out ordinary dialogue.
Report difficult cases separately. Never apply stale results to another page, future context to an earlier
chapter, or overwrite reader-locked names/pronouns.
Original-view conceal must be synchronous: no translation or erasure may remain visible while RAF
is delayed. Remove the lettering subtree from paint, not just its individual glyphs. New/late text and
cleanup surfaces start hidden; reveal only after current geometry and clipping are positioned.
Verify exact source restoration, not just a toolbar state/class.

Enable evidence-backed, inexpensive local reading improvements by default. Local text cleanup must not
spend API credits or send images to the cloud, and must remain reversible and bounded per region/job.
Preserve explicit saved opt-outs. Default-on is not permission to redraw uncertain artwork: keep original
art and a reversible annotation when safe text separation cannot be established.
Material extra API/credit, latency, RAM/battery or destructive visual costs require a separate opt-in,
clear cost/time/quality explanation and confirmation before the first charge or affected operation.
Make genuine quality upgrades discoverable, but never silently enable paid generation or slow neural
reconstruction. Saving settings alone must not trigger translation, a request, or a charge.

Validate quality on the user's private ground-truth dataset before expanding to a larger dataset or
further tuning cost/latency. Audit labels, coverage, duplicates and rights; keep benchmark outputs private.
OCR text labels are not clean-background or complete translation ground truth. Synthetic tests protect
regressions, not claims of real-manga perfection. Inspect and report real failures before changing defaults
or packaging a release; do not weaken a quality gate merely to obtain a passing speed result.

Never strip Japanese quotes, ellipses or expressive spacing globally to conceal OCR errors. A quote can
span bubbles. Keep source evidence, ask for review and validate any retry/preprocessing on real crops;
do not promote a transform from one successful synthetic example. Keep model/output guards narrow,
preserve confirmed reader exceptions and reject only failed IDs during the bounded repair.
Tiny dots-only OCR on edge-connected artwork is review, not permission to delete punctuation or art.
Preserve existing reader source-key bindings when routing policies/cache versions change.
Reader speaker confirmations bind the captured-source key and chapter/page cutoff, never ordinal
region IDs. Do not invent anchors for legacy choices from the latest cached geometry; retain them
for explicit re-confirmation. Native reader edits require the current page revision/cutoff and a
unique source anchor. Keep confirmed bindings/history beyond transient page-cache expiry.
Schema migrations must roll back tables, copied records and version together on failure.

Text detection is not semantic importance classification. Do not silently drop small/dense/balloonless
text: it may be narration, a clue, a letter or a sign. Separate dialogue/thought/narration, relevant scene
text, SFX and supplementary/decorative text; unknown is a valid role. Only evidence-backed irrelevant
regions or reader exclusions can be skipped automatically. Deferred secondary text must remain in the
original image and be recoverable by reader action; do not rewrite it or put it into story memory as plot.
Benchmark role/action labels separately from OCR labels before claiming automatic scene-text filtering.

Detector comparisons must retain upstream location classes and raw scores; text_free is not an SFX or
irrelevance class. Fewer regions or a small CER gain cannot excuse missing text, overmerges or damaged art.
Learned text/bubble boxes are not glyph masks. A grouping candidate must preserve source members and
reader exclusions, and cannot promote inherited visual distrust into plot memory or erasure authority.
