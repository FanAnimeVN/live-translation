# Source-preserving utterance assembly — 2026-10-15

The live pipeline currently receives OCR regions as independent source records.
That is correct for provenance but can make a Japanese vertical sentence appear
as several Vietnamese cards. `companion/manga_live/utterance_assembly.py` adds a
separate, conservative seam for a translation/presentation candidate:

- every source record and source key remains in the `sources` plane;
- a candidate needs one unique, tight geometry guide, compatible orientation,
  aligned starts and bounded spacing;
- reader choices, confirmed speaker bindings, balloons, SFX and visual-review
  marks veto a merge; a punctuation crop with `ocr_crop_partition` remains its
  own recoverable source record. Ellipsis-only marks whose ink is connected to
  artwork are routed as deferred secondary text: the original stays visible
  and selectable, while no expanded lettering box is painted over the grouped
  utterance;
- grouped IDs are content-derived presentation IDs, not replacements for
  source anchors;
- grouped units are explicitly `review=true`, `memory=false` and
  `erasure_permitted=false`; no plot memory or cleanup authority is granted.

The module is not enabled as a production default yet. The private 8-page
comparison used the existing production OCR plane plus the independently
recorded block geometry (no fresh OCR): 9 assemblies, 120 presentation units
versus 132 source regions, alignment 62/78, exact 35/78 and diagnostic CER
28.65%—the same aggregate text result as the current partition report. This
shows source preservation and fewer presentation units, not translation or
clean-background quality. A source-preserving candidate must still pass the
renderer and independent Japanese/Vietnamese/clean-background review before it
can become the default.

The grouped cloud pilot for MN109-08 sent only two OCR text blocks to the
explicitly authorized OpenRouter route (`deepseek/deepseek-v4.1-flash`): one
request, provider-reported cost 0.0005376 USD, measured translation time about
2.48 s. It is a text contract/wording observation, not a quality certificate.

## Boundary recheck — still a candidate

`utterance-assembly-boundaries-v2` fixes eleven reproduced cases before any
runtime promotion. Reader exclusions and confirmed identities veto a bridge
even when the excluded note has a different writing orientation. Present but
incomplete legacy scopes cannot become source anchors. An unexplained review
flag is not treated as a verified crop partition. Numeric reading order alone
is insufficient: source order must also agree with supported vertical RTL or
horizontal top-to-bottom geometry; otherwise the original units are kept.
Distinct assemblies now have distinct, member-derived scope identities, stable
when an unrelated source changes. These are presentation identities, never
new captured-source bindings or erasure authority.

New regression command was red with 11 failures before the fix and green with
37 passes afterwards:

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/python/test_utterance_assembly.py -q -p no:cacheprovider --basetemp <new-workspace-temp>
```

The new `scripts/probe_utterance_assembly.py` replayed the complete eligible
private set using recorded production partition OCR and block-guide evidence.
All 132 exact source records and anchors remain recoverable, 9 assemblies / 120
presentation units; diagnostic alignment 62/78, exact 35/78 and CER 28.65% are
unchanged. The script separately verifies source completeness, unique assembly
scope identities and no memory/erasure elevation, and retains raw upstream
guide classes and scores. It does not call a model, upload images, persist
rasters or report replay timing as inference latency. Text-only evidence is
`artifacts/private-utterance-boundaries-v2-20261015.json` (private, not shipped).

These fixes do **not** solve local-model generation, validate Japanese labels,
certify Vietnamese meaning, or improve production lettering yet. No runtime
default, reader setting, personal Native Messaging registration or paid route
was changed. The manga-quality gate remains unmet.
