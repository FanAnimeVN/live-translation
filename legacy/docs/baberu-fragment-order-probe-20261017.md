# Source-fragment ordering: a measured fix, not a route to 78/78

## Scope and decision

The completed CPU experiment uses the same frozen tiled PP proposals on all
eight eligible private development pages: 140 units / 214 retained detector
members / 78 labels / 939 normalized characters. Input fingerprint remains
`445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`.
Detection is replayed, not inferred again. No supplied gold box selects the
recognizer input; labels are used only for post-inference alignment/scoring.
No gold string selects a runtime alternative.

| Fixed proposal recognizer/crop recipe | Exact | Edits | CER | Decision |
|---|---:|---:|---:|---|
| Recorded tiled manga-ocr control | 35/78 | 265 | 28.22% | unpromoted tiled control |
| Fresh Baberu, unchanged whole-region crops | 34/78 | 255 | 27.16% | reject replacement |
| Fresh Baberu, separate axis-aligned members, order v1 | 28/78 | 307 | 32.69% | reject replacement |
| Same raw member OCR, geometry order v2 replay | 28/78 | 297 | 31.63% | retain experiment only |

These are distinct from the production 132-region baseline (35/78, 269 edits,
28.65% CER), CTD 44/78 and review-only hybrid 48/78. None changed defaults.
The whole-region replacement improves eight labelled edit counts but worsens
seven and changes three strings at equal edit count against the tiled control.
Lower average CER therefore does not justify promotion.

## Actual defect and bounded correction

MN109-05/r016 contains an upper-right fragment, lower-right fragment and left
column. The lower-right polygon starts slightly farther right, so v1's pure
x-first sorting reads the lower fragment before the upper. Original source
pixels were inspected; no label was modified.

`reorder_recorded_members` defines the comparator-only rule before rerating:

- Use unpadded source bounds, not the 2px crop halos, for precedence.
- Majority tall members: when x projections overlap at least 60% of the
  narrower member and y intervals are disjoint, upper precedes lower.
- Majority horizontal members: corresponding same-row y overlap and disjoint
  x intervals imply left precedes right.
- Stable topological ordering retains v1 RTL/top-down priority otherwise.
- Raw strings, quote/spacing, source members, scores, IDs, exclusions and boxes
  remain intact. No grouping, speaker, memory or erasure authority is created.

Paired replay changes two labelled strings, reduces edits by ten (8→2 and
13→9), and has zero edit-count regressions or changed equal-edit strings on
this pack. Assignment gains/losses are both zero; this is not proof of true
detection recall. Neither corrected string becomes exact. Other recognition
and coverage errors remain. Even after the ordering fix, member crops lose to
the whole-region Baberu control: one improved label, ten regressions and four
changed equal-edit strings. Do not deploy indiscriminate line splitting.

## Timing and RAM evidence

Both fresh recognizer runs used two CPU threads and the existing pinned Baberu
ONNX assets under the offline guard. No cloud request, model download or image
write occurred. All images/crops remain RAM-only.

- Whole-region: p50 region inference 846.12 ms, p95 957.92 ms; supervisor wall
  time 121.67 s for all eight pages. Sampled owned-process-family peak RSS
  354,291,712 bytes and private bytes 836,083,712; minimum observed system free
  physical 620,343,296 and available commit 5,644,075,008 bytes. Exit 0, no stop
  trigger. Descendants were included, not merely the virtualenv launcher.
- Member v1: p50 unit time 891.38 ms, p95 3,568.22 ms; supervisor wall time
  190.14 s. Child process peak working set 345,718,784 bytes. The first
  supervisor sampled only its launcher, so its ~4.9 MB RSS is **invalid as OCR
  memory evidence**. Do not compare it to the corrected family measurement.
- Ordering v2 is a replay, `fresh_inference=false`; stored member timings and
  `recorded_probe_ocr_ms` are inherited. It establishes no new inference speed.

These times exclude fresh detection, translation and browser transport, and
the empirical region percentile is not an end-to-end live-reading p95. The
old recorded process-memory scope incorrectly mentions a detector; no detector
was loaded. The script now labels that scope correctly for future runs; old
evidence is not rewritten. The separate OCR48 2 GiB free-physical launch gate
remains unchanged; recent available memory (~1.01 GiB) does not satisfy it.

## Verification and reproduction

Red tests reproduced the new column-order boundary, missing replay boundary
and excluded-text reintroduction before their corresponding implementation.
Focused comparator tests: **21 passed**. Full Python: **1,404 passed, 1
skipped**; TypeScript **60 passed**; typecheck passed. These are software
regressions, not independent gold review or manga translation acceptance.

Private reports, ignored and not included in a release:

- `artifacts/private-baberu-whole-tiled-20261017.json`
- `artifacts/private-baberu-members-tiled-20261017.json`
- `artifacts/private-baberu-members-order-v2-validated-20261017.json`
- `artifacts/private-baberu-whole-vs-members-v2-20261017.json`

The replay checks the unchanged dataset fingerprint, complete page/member
coverage, member identities/raw source and unchanged grading references. It
records the parent report checksum and refuses an existing output path.

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_baberu_probe.py --folder '<private folder>' --baseline artifacts/private-pages-tiled-recall-v1-20261017.json --threads 2 --output artifacts/<new-whole-report>.json
.\.venv\Scripts\python.exe scripts/benchmark_baberu_probe.py --folder '<private folder>' --baseline artifacts/private-pages-tiled-recall-v1-20261017.json --line-members --threads 2 --output artifacts/<new-member-report>.json
.\.venv\Scripts\python.exe scripts/benchmark_baberu_probe.py --folder '<private folder>' --reorder-from artifacts/private-baberu-members-tiled-20261017.json --output artifacts/<new-replay-report>.json
```

Run recognizers sequentially under an owned, bounded resource supervisor, not
concurrently. The commands above alone do not supply that supervisor.

## What this changes about the 78/78 strategy

One source-ordering defect is now reproducible and corrected in the comparator,
but there is no new automatic winner. The next quality experiment must be a
genuinely different image-grounded recognizer/verifier on retained proposals,
not further threshold tuning of this losing split. Japanese source/label
conflicts still need independent review; Vietnamese and clean-background gold
are separate gates, not blockers for OCR experimentation. The eight already
tuned pages remain development data. Report manual correction as assisted,
not automatic 78/78.

No personal Edge session, extension bundle, reader binding, production model,
cloud authorization or budget reservation changed in this checkpoint.
