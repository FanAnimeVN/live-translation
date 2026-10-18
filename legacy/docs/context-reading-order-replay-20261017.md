# Recent context: chronological, compact, source-preserving

Implemented in desktop development source on 2026-10-17. No paid inference,
wiki/character lookup, image read/write, browser installation or packaging.
This is a context retrieval fix, not a new OCR/translation accuracy result.

## Reproduced defects and correction

`Memory.context` selected the two most recent read pages in descending SQL
order, flattened them, then took the last 18 rows. The older page could thus
displace recent replies, and the surviving pages reached translation in reverse
order. Even after fixing that order, the forward byte-budget pass favored
older utterances when the allowance ran out.

A second actual-code defect charged entire OCR/render region records against
the dialogue allowance. Polygon/member and lettering metadata could displace
even short, useful dialogue, despite not being printed in the model prompt.

The retriever now:

- Filters eligible read pages strictly before the requested cutoff as before.
- Applies the existing semantic/review scope filter before projection.
- Restores chronological page order; preserves each page's recorded row order.
- Keeps up to 18 recent utterances, with only ID, exact JA/VI, speaker/listener
  and role fields plus the stored page's chapter/page. It does not infer new
  identities, source keys or relationships. Reused ordinal region IDs do not
  supply the cutoff; arbitrary cutoff fields inside a region cannot override
  its page record.
- Gives newest complete utterances first access to the existing byte allowance,
  then presents retained utterances oldest-to-newest. It never clips source
  strings or strips quotes, expression marks, negation or spacing to fit.
- Leaves all full page/source records, bindings, durable evidence and reader
  locks untouched. Geometry is not promoted into plot evidence.

The dependency fingerprint already covers the selected context. Existing page
cache validation recomputes it per actual translation-group query; no blanket
OCR-cache wipe, manual story-memory deletion or schema migration is introduced.
Settings changes still do not start a request. A corrected dependency can make
an old translation ineligible on the next explicitly authorized translation;
this change is not permission to regenerate it in the background.

## Red/green and recorded-source replay

Four public `Memory.context` regressions failed before their respective fixes:
cross-chapter reading order/last-18 selection, metadata starvation, newest-first
byte priority and authoritative per-page cutoffs for reused IDs. Tests retain
literal expected dialogue/order and check the original page via `Memory.page`.
The small replay interface likewise failed before implementation, then passed.

`scripts/benchmark_context_sources.py` runs real `Memory.context` against text
and region metadata already recorded by the private eight-page OCR experiments.
Each source page is tested independently in an in-memory SQLite database with
an explicitly simulated cache cutoff. Unrelated dataset pages are **not**
declared one story/chapter, and no persistent reading progress is fabricated.
The replay does not inspect reference labels or choose OCR output by gold.

| Recorded source | Source / memory-eligible regions | Legacy retained | Corrected retained | Maximum serialized corrected list |
| --- | ---: | ---: | ---: | ---: |
| Production scope report, eight pages | 132 / 127 | 39 | 117 | 1,335 bytes |
| Retained CTD control, eight pages | 80 / 70 | 18 | 70 | 1,000 bytes |

These totals are **retained dialogue entries**, not exact OCR labels,
important-event recall, or semantic accuracy. The per-page replay isolates
metadata/budget behavior; two-page chronology is separately reproduced by the
integration tests. All retained JA/VI/role strings and full source records were
unchanged; reading order and current-page exclusion passed on both reports.
Ten eligible production entries still fall outside the count/byte selection;
the bounded retriever does not claim complete memory of every event.

Private, ignored numeric/provenance reports:

- `artifacts/private-context-source-replay-production-20261017-r7.json`
- `artifacts/private-context-source-replay-ctd-20261017-r7.json`

Reproduce with a new destination, without a key or model:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_context_sources.py --source artifacts/private-pages-default-fresh-20261014-v4-scope.json --output artifacts/<new-production-context-report>.json
.\.venv\Scripts\python.exe scripts/benchmark_context_sources.py --source artifacts/private-pages-ctd-retained-lines-t2-20261017-r3.json --output artifacts/<new-ctd-context-report>.json
```

Final verification: **1,490 Python passed / 1 skipped** in 49.27 seconds;
**61 TypeScript passed**, typecheck and build passed. These are regression-suite
results, not provider or live reading latency. Production OCR remains **35/78**.
Independent Japanese/Vietnamese/clean-art review and end-to-end release gates
remain unmet. Paid development reservations remain $0.49962719/$0.50, not an
actual billed-spend statement; no new request was made.

See [multi-model context implementation](context-memory-cloud-20261017.md),
[current official model revalidation](context-model-claims-revalidation-20261017.md)
and [actual mask ablations](bubble-mask-private-probe-20261017.md).
