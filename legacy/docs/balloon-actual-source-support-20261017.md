# Actual source support: bounded lettering upgrade

Implemented in desktop development source on 2026-10-17. Native **Paddle**
fresh detection now uses `balloon-mask-v21-actual-source-support`. OpenCV and
cloud proposals do not inherit this recovery. This is not an installed
companion update, new OCR result, paid-model comparison or release acceptance.

## Evidence and the narrow correction

The detector's unpadded polygon support is not its additional three-pixel
inference margin. Two source regions failed the existing padded-footprint
outline check although their actual detector support passed it. The recovery
uses floor minima / ceil maxima from each retained polygon, not a guessed
subtraction from a padded union.

The same **8px / 10%** outline-overhang bound and full-union foreign-ink proof
remain. Background flatness, enclosure, interior erosion, unknown-ink/halo
protection and inscribed textBox checks remain. Writable masks still come from
selected ink inside the protected interior, not the detector rectangles.
No single-column exception, larger halo or learned-box erasure is introduced.

The four originally investigated closed-balloon fallbacks on MN109-03 are
**not fixed**. In particular, r008 still has unsupported pale pixels beyond
the existing proven outline halo. This work does not increase that halo or
lower its contrast gate to force acceptance. The useful wins are elsewhere.

`group_regions` retains its frozen v20 default for comparators; the existing
explicit flag spelling remains for historical replay compatibility. Native
`PaddleDetector.detect` explicitly selects the validated presentation. Its
inference inputs, thresholds, grouping, source rectangles, IDs and order are
unchanged. Diagnostic `sourceMembers` are not added to production prompts.

## Eight-page paired replay, then native-default verification

Private source fingerprint is unchanged. The audited source contains eight
eligible development pages / 78 unreviewed Japanese labels / 939 normalized
characters. It is not held-out; there is no independently accepted Vietnamese
or complete clean-background gold.

Only the unchanged **full-page PP plane** was replayed, not its extra tile
proposals. Exact source geometry, members, OCR partition/crops and current
scope/source-key/memory-trust decisions were checked before recorded text was
reused. The final replay also passed retained upstream model outputs through
the actual native `PaddleDetector.detect` method and matched the candidate.
No fresh detector/recognizer/model inference was performed by this replay.

| Measure | Frozen v20 | Native v21 geometry replay |
| --- | ---: | ---: |
| Regions | 132 | 132 |
| Regions eligible for integrated lettering | 10 | 12 |
| Diagnostic Japanese exact | 35/78 | 35/78 |
| Edits / characters | 269/939 | 269/939 |
| Changed JA / lost assignments | — | 0 / 0 |

New integrated geometry: MN109-04:r011 (rectangular narration) and
MN109-07:r006 (connected multi-lobed speech balloon). Existing integrated
surfaces are unchanged. These are two additional geometry acceptances, not a
95% integrated-lettering claim or proof of faithful Vietnamese translation.

Control-first replay timings include cold imports and cannot establish a
speedup. No live first-bubble/page/cache p95 was measured. The change makes no
network requests and adds no API credits; CPU cost remains bounded local work.

## Cache and reader compatibility

`LAYOUT_VERSION` retains the v20 source grouping/crop identity. New
`PRESENTATION_VERSION` is independent: a presentation-only change is not a
reason to evict accepted source/OCR/translation caches or charge again.

New OCR-coverage and page results carry their actual `presentationVersion`.
Accepted old pages and completed OCR coverage keep their existing geometry
and version on reuse. Old records without this field are labelled v20, not
silently described as v21. No polygons are reconstructed from nearest cached
geometry; no reader anchors, locks, exclusions, history or schema are migrated.
Only fresh native detection receives the improvement. A genuine source-layout
or text/context dependency change still invalidates its existing dependencies.

Status separately reports the selected detector's presentation capability;
the runtime-details UI prefers that field and remains compatible with older
companions. A capability label does not imply every cached page has been
redrawn. Saving settings/status does not refresh images or send a paid request.

## Rendered desktop checks

Browser plugin not available; used existing Playwright and isolated headless
Edge, local ephemeral `/qa` routes. Native transport, OCR text and Vietnamese
were QA-authored; actual native geometry, bundled font and production renderer
were exercised. Private images, masks, crops and screenshots stayed in RAM.

Desktop pixel tests used 1280x1480; real scroll used 1280x900. The retained
390x844 regression uses a **reading-card fallback**, not integrated lettering
or mobile readiness. Two desktop screenshots were visually inspected.

| Check | MN109-04:r011 | MN109-07:r006 |
| --- | ---: | ---: |
| Source-dark samples in selected glyph ROIs | 3,650 -> 0 | 1,968 -> 0 |
| Changed pixels in selected protected ROIs | 0 | 0 |
| Changes outside bounded rendered erasure halo | 0 | 0 |
| Transparent text; no border/shadow/overflow | Pass | Pass |
| Actual scroll alignment / exact original restore | Pass | Pass |
| Page identity/nonblank/framework/console checks | Pass | Pass |
| External requests | 0 | 0 |

The glyph ROIs can overlap: counts are samples, not unique complete glyph
gold. The pixel helper permits a bounded rendered erasure halo; it does not
prove every pixel outside the literal vector mask is unchanged. Selected
protected ROIs are not exhaustive clean-background gold. The multi-lobed
balloon retains blank space above its safe inscribed text rectangle; no
unproved area was made writable to center it higher.

Settings QA at `http://127.0.0.1:65303/options.html` also passed: v21 appears
in runtime details, library/cutoff/summary-consent interactions and retained
390px responsiveness work, no console errors. It uses mocked native replies,
not the user's profile or a new cloud-summary quality evaluation.

## Verification and reproducibility

- Executed red/green tests: native fresh detection originally fell back;
  accepted-page provenance was missing; native/TS status did not carry/validate
  the independent presentation identity. These now pass.
- Additional compatibility checks: no repeated OCR/translation after a
  presentation upgrade; resume completed OCR after a provider failure; legacy
  accepted surfaces remain readable; confirmed captured-source speaker bindings
  remain intact; genuine source-layout changes retain their invalidation.
- A diagnostic tracer was also repaired red/green: its global call hook had
  returned `None` instead of installing per-frame tracing. Actual grouping and
  lettering decisions are now observed without recording raster arrays. This
  diagnostic repair does not make MN109-03's rejected regions accepted.
- Full Python: **1,504 passed / 1 skipped**, 54.87 seconds. Skip is the retained
  Windows symlink case. This is suite runtime, not application latency.
- TypeScript: **62 passed**; typecheck and build passed.

```powershell
.venv\Scripts\python.exe scripts/probe_balloon_source_support.py --folder '<private-source>' --reference artifacts/private-pages-production-v20-20261016.json --detector-replay artifacts/private-pages-tiled-recall-v1-20261017.json --verify-native --output artifacts/<new-private-report>.json
.venv\Scripts\python.exe -m pytest tests/python -q --basetemp=artifacts/<new-test-directory> -o cache_dir=artifacts/<new-cache-directory>
npm.cmd run check
node scripts/options-qa.mjs
```

Private numeric/text evidence is ignored in artifacts:
`private-balloon-actual-source-support-20261017-r10.json` (explicit candidate),
`private-balloon-actual-source-support-native-20261017-r11.json` (native-default
verification), and `private-lettering-v21-native-20261017-r11.json` (bounded
numeric UI/pixel checks, no screenshot/text payload).

No private labels were edited, no new paid calls were made, and no installer
was packaged/deployed. Development reservations remain $0.49962719 / $0.50,
not an actual billing total. Production OCR remains **35/78**; independent
Japanese/Vietnamese review, hard cases, clean-art gold and held-out acceptance
are still required. Goal remains active and not release-ready.
