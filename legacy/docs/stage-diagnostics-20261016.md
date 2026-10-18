# Stage-level OCR diagnostics — 2026-10-16

`diagnose_stage_failures.py` now separates the observable failure stage in a
page report instead of treating every edit as one undifferentiated CER. It
uses the same conservative prediction-containment rule as the existing page
benchmark, preserves the report/dataset fingerprint check, and never treats
unmatched regions as irrelevant text.

This is diagnostic evidence only. The supplied Japanese transcription has not
been independently reviewed, and the dataset has no valid Vietnamese gold or
clean-background gold.

## Current private development report

Dataset fingerprint:
`445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`

Baseline report: `private-pages-production-v20-20261016.json`

| Observable stage | Count |
|---|---:|
| Exact single-region | 29 |
| Exact ordered multi-region assembly | 6 |
| Grouping mismatch/fragmentation | 10 |
| OCR mismatch on assigned region(s) | 17 |
| Detector partial overlap | 14 |
| Detector miss | 2 |
| Gold rows | 78 |
| Diagnostic CER | 28.65% |

The two exact categories sum to the historical 35/78 exact result. A
multi-region result is not called a failure when its ordered concatenation is
exact; this avoids confusing normal vertical-column assembly with overmerge.
`grouping mismatch/fragmentation` is still an observable classification, not a
causal proof: a wrong crop can also make the recognizer output incomplete.

## Candidate comparison

| Configuration | Exact rows | Grouping mismatch | OCR mismatch | Partial/miss | CER |
|---|---:|---:|---:|---:|---:|
| Production v20 | 35 | 10 | 17 | 16 | 28.65% |
| PP box threshold .4 | 34 | 15 | 14 | 15 | 27.16% |
| Forced long edge 1600 | 33 | 8 | 21 | 16 | 25.24% |

The lower CER candidates still lose exact rows or change coverage, so neither
is promoted. This evidence redirects the next algorithm loop to the 14 partial
and 2 missed detector assignments plus the 10 non-exact multi-region groups;
it does not justify changing production defaults or filtering unmatched text.

Private JSON outputs are kept under `artifacts/` and are not release assets.
