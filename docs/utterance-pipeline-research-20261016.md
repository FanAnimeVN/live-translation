# Utterance grouping, source membership and mask ownership

Source inspection: 2026-10-16. Scope: the narrow grouping → translation →
cleanup → lettering boundary. This supplements
[the accuracy research](manga-accuracy-research-20261016.md) and
[our existing assembly notes](utterance-assembly-20261015.md); it does not
introduce a runtime change, a benchmark result or a default promotion.
No models/datasets were downloaded and no paid API or private images were used.

Revisions inspected:

- Kites: `4acebe6dd3bd253aafaf38b24d849f9b40ba94e0`.
- manga-image-translator (MIT below):
  `d6de6ab62a7be6afc0d07a3184149cdefbcd32f2`, resolved from its public `main`
  during this inspection. Links below pin that revision.

## Finding: reuse the separation, strengthen the ownership contract

Both implementations distinguish a grouped text block from its constituent
line geometry. Neither inspected interface supplies our complete contract of
immutable captured-source keys, chapter/page cutoff, reader exclusions and
independently authorized erasure. Their code supports a useful architectural
comparison; it does not establish semantic correctness or safe artwork
restoration on our private pages.

| Plane | Kites | MIT |
|---|---|---|
| Grouping membership | Working line indices survive graph/MST and post-splitting; the public result flattens mask members | Ordered line polygons and line texts remain inside each `TextBlock` |
| Translation input | Ordered merged text strings | `region.text` for each block |
| Cleanup geometry | Unmerged surviving line polygons; each engine makes its own mask | Detector raster mask refined using surviving blocks' constituent lines |
| Lettering geometry | Merged rectangle, optionally a separate bubble layout box | Separately calculated render destination polygons |

These mappings are evidenced by the detailed source paths below. The proposed
invariants in the last section are project requirements/inferences, not claims
that either upstream repository already implements them.

## 1. Kites: membership exists during assembly, then becomes lossy

`mergeTextBlocks` builds groups over working quadrilaterals, passes each member
to `clusterLinesIntoUtterances` as `{id, polygon, text}`, and maps each returned
line back through `id`. It then orders members, concatenates their strings,
computes a merged rectangle and records the source line count. Only members of
emitted nonempty groups contribute to `maskPolygons`.
[OcrManager, assembly and mask construction](https://github.com/Unheat/Kites/blob/4acebe6dd3bd253aafaf38b24d849f9b40ba94e0/src/offscreen/services/OcrManager.ts#L728-L909).

The returned `OcrResult` contains merged strings/rectangles, `lineCounts`, and
one flattened `rawPolygons` list. It does not return the local group → member
index relation, original per-member strings or durable captured-source IDs.
Thus it preserves useful cleanup geometry, but not enough ownership evidence
to implement our reader edits or source-bound speaker confirmations. Also,
`detectionScores` is forwarded directly from the input while the merged arrays
are rebuilt: do not assume those raw scores align with merged block indices.
[Return construction](https://github.com/Unheat/Kites/blob/4acebe6dd3bd253aafaf38b24d849f9b40ba94e0/src/offscreen/services/OcrManager.ts#L898-L909),
[OcrResult interface](https://github.com/Unheat/Kites/blob/4acebe6dd3bd253aafaf38b24d849f9b40ba94e0/src/offscreen/engines/ocr/BaseOcrEngine.ts#L8-L49).

The splitter is a geometry/punctuation heuristic. Vertical clustering uses
spacing, overlap and stagger; horizontal clustering uses rows and paragraph
gaps. Its terminal set includes ellipsis and closing Japanese quotes. It has
no speaker-evidence input. The caller also omits the optional rotation argument,
so that call uses the splitter's zero-angle default. Treat its “utterance” as
a candidate, especially where a quote spans balloons or adjacent speakers are
close together.
[Splitter](https://github.com/Unheat/Kites/blob/4acebe6dd3bd253aafaf38b24d849f9b40ba94e0/src/offscreen/utils/utteranceSplitter.ts#L51-L303),
[Caller](https://github.com/Unheat/Kites/blob/4acebe6dd3bd253aafaf38b24d849f9b40ba94e0/src/offscreen/services/OcrManager.ts#L758-L771).

There is a particularly relevant ownership edge: orphan punctuation is copied
into a nearby line's string, then its original index is marked claimed and
skipped. Subsequent mask construction uses surviving working quadrilaterals.
The attachment does not itself transfer the punctuation polygon into that
line's membership. **Inference from this path:** recovered punctuation text
does not guarantee corresponding cleanup coverage. This is a targeted case to
test, not a measured assertion that a particular real page leaks punctuation.
Our pipeline should preserve both original records and an explicit attachment
relation instead of rewriting source evidence.
[Punctuation attachment/filter](https://github.com/Unheat/Kites/blob/4acebe6dd3bd253aafaf38b24d849f9b40ba94e0/src/offscreen/services/OcrManager.ts#L415-L460),
[Mask membership](https://github.com/Unheat/Kites/blob/4acebe6dd3bd253aafaf38b24d849f9b40ba94e0/src/offscreen/services/OcrManager.ts#L883-L909).

Kites deliberately supplies polygons to inpaint engines and ignores its
legacy DBNet raster argument. That is an upstream product decision; its line
envelopes are still not glyph masks or proof that enclosed artwork is safe to
remove.
[InpaintManager contract](https://github.com/Unheat/Kites/blob/4acebe6dd3bd253aafaf38b24d849f9b40ba94e0/src/offscreen/services/InpaintManager.ts#L14-L39),
[Engine call](https://github.com/Unheat/Kites/blob/4acebe6dd3bd253aafaf38b24d849f9b40ba94e0/src/offscreen/services/InpaintManager.ts#L234-L258).

Translation and cleanup run concurrently. Cleanup uses the OCR mask-member
list before actual render eligibility is known; later lettering includes only
entries with both text and polygon. A translation exception falls back to OCR
text, while an inpaint exception falls back to the original image. These are
observable fallback paths, not a general proof of “erase only successfully
translated/rendered members.” Bubble layout geometry is acquired and fitted
separately from cleanup.
[Parallel branches](https://github.com/Unheat/Kites/blob/4acebe6dd3bd253aafaf38b24d849f9b40ba94e0/src/offscreen/services/PipelineOrchestrator.ts#L171-L263),
[Render eligibility and layout](https://github.com/Unheat/Kites/blob/4acebe6dd3bd253aafaf38b24d849f9b40ba94e0/src/offscreen/services/PipelineOrchestrator.ts#L288-L353).

## 2. MIT: block text and source-line geometry remain distinct

The merge graph uses geometric compatibility, then splits components through
MST distance statistics. Each group is ordered vertically right-to-left or
horizontally top-to-bottom; dispatch constructs parallel `lines` and `texts`
arrays. This preserves constituent geometry/text rather than replacing them
with one union rectangle. The graph uses runtime indices, not our durable
source identity model, and its merge predicate has no speaker input.
[Grouping implementation](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/textline_merge/__init__.py#L10-L208).

`TextBlock` retains `lines`, `texts`, aggregate `text`, and separate
`translation`. Its union/minimum rectangle is derived from line coordinates.
The useful distinction is therefore line evidence versus aggregate language
input versus layout envelope; none should replace the others in our schema.
[TextBlock constructor](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/utils/textblock.py#L39-L109),
[Derived rectangles](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/utils/textblock.py#L120-L166).

The ordinary path translates the blocks and delays mask refinement to benefit
from region filtering; refinement runs only when `ctx.mask` is absent. The
mask-generation error fallback can use the raw detector mask. Therefore the
filter-before-refinement pattern is useful, but its safety claim must be
qualified for precomputed masks and fallback branches. Numeric/identical-text
filters and the explicit translator-none cleanup mode are upstream policies,
not suitable automatic relevance rules for our reader.
[Pipeline order and fallback](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/manga_translator.py#L542-L590),
[Translation input/none mode](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/manga_translator.py#L1072-L1123),
[Final region filtering](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/manga_translator.py#L1325-L1380).

Refinement expands every surviving block back into `region.lines`, combines
those guides with the raw detector raster, and resizes/binarizes the result.
`complete_mask` assigns connected components by overlap or distance to line
polygons, then applies local refinement and dilation. It skips components with
area ≤ 9. These are pixel-selection heuristics with possible leakage/art damage
and punctuation loss; we must validate real crops and protected art instead of
adopting those thresholds as authority.
[Refinement dispatch](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/mask_refinement/__init__.py#L9-L29),
[Component assignment and dilation](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/mask_refinement/text_mask_utils.py#L96-L195).

The standard renderer calculates separate `dst_points` for translated text
and draws onto the inpainted image; it can expand beyond the source rectangle.
Its optional `render_mask` is filled with destination polygons, so that field
is render occupancy, not a glyph-cleanup mask. Source-line count participates
in layout sizing; preserving member lines remains useful after translation.
[Destination calculation](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/rendering/__init__.py#L89-L231),
[Render dispatch](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/rendering/__init__.py#L235-L262).

## 3. Implementation invariants for this project

These are recommendations derived from the inspected seams and the repository's
reader-first rules; they are not upstream benchmark findings.

1. **Keep immutable sources and explicit relations.** Every candidate carries
   ordered captured-source keys, raw line text/polygon/class/score and join/split
   reasons. Derived concatenation is a language view. Preserve Japanese quotes,
   ellipses and expressive spacing in source evidence. Do not reconstruct
   membership from a final rectangle, line count or output position.
2. **Keep grouping reversible.** An ordinary translation candidate owns only
   its listed eligible members; every excluded/deferred/unknown source remains
   recoverable. Reader exclusions and confirmed speaker conflicts veto bridges.
   Punctuation attachments retain their own member keys and geometry. A
   geometric cluster does not establish a speaker, semantic role or plot fact.
3. **Translate with context; address output by stable IDs.** Context can include
   nearby permitted source units without merging their render/mask ownership.
   Output must map to the expected member IDs/segments, with reader locks and
   chapter/page cutoff enforced. Reject/repair failed IDs only; never infer new
   source anchors from group ordinals or the latest cached geometry.
4. **Separate three geometries.** Source OCR guides establish provenance;
   verified glyph/cleanup evidence limits reversible pixel changes; layout
   envelopes position replacement lettering. Expanding or regrouping lettering
   never expands cleanup permission. Inherited visual distrust/review remains
   distrust after grouping. Unsafe artwork keeps its original and annotation.
5. **Separate computation from publication.** Safe local cleanup may compute
   concurrently, but publication requires the current page revision, eligible
   member set, accepted text, positioned/clipped lettering and authorized mask.
   An empty, missing, failed or newly excluded member keeps its source pixels.
   Fallbacks must not broaden to raw page masks or erase-only output.
6. **Preserve exact restoration.** Keep original pixels in RAM; cleanup and
   lettering are reversible surfaces. Original view must synchronously remove
   their complete paint subtree even when RAF is delayed. A successful upstream
   baked-image pipeline does not verify our restoration requirement.

Required evidence before promotion: source completeness and unique ownership;
split/overmerge/order errors; quotes across bubbles; punctuation-only members;
excluded-member bridges; source-key/cutoff stability; partial/empty translation
responses; stale completion; glyph leakage and protected-art change; positioned
lettering, synchronous conceal and exact pixel restoration. Use real private
failures plus regression fixtures. Measure latency separately; no upstream
speed or quality result is inferred here.

Commercial Manga Scan/Scan Translator internals are not established by these
sources. This note makes no engine, model, corpus, training or quality claim
about that product. The existing licensing review also remains necessary before
copying or shipping GPL code; this note proposes interfaces and tests only.
