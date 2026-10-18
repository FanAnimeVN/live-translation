# Edge-connected punctuation renderer fix — 2026-10-15

The private MN109-08 grouped replay exposed one real lettering regression:
the OCR crop `r002` (`．．．`) was kept as a normal translated surface even
though the visual signal classified it as edge-connected punctuation review.
Its expanded lettering box intersected the grouped utterance `u-fc53…`.

The routing policy now defers only this narrow case. The original punctuation
remains in the source image and in the recoverable secondary-text list; an
explicit reader action can translate/review it. It is not erased, added to
plot memory, or silently discarded. Ordinary ellipses on a sufficiently clear
flat crop still translate normally, and reader scope overrides still win.

Evidence (private, gitignored artifacts):

- `private-render-grouped-20261015.json`: previous replay, 1 overlap; source
  restoration itself passed.
- `private-render-grouped-punctuation-deferred-20261015.json`: current-scope
  replay, **0 lettering overlaps**, exact source restoration over two original
  toggle cycles, synchronous hide before RAF, no console/framework/external
  API errors.

This is a renderer/routing regression fix, not an OCR or translation-quality
certificate. The private benchmark still has no independently reviewed
Vietnamese gold or clean-background gold, and the aggregate OCR result remains
diagnostic rather than a claim of manga-perfect quality.
