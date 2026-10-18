# Missing-region fallback — 2026-10-16

## Candidate rule

`scripts/probe_missing_region_fusion.py` replays two recorded detector/OCR
reports. A secondary result may be used only when:

1. the primary label has no assigned region; and
2. the secondary label has exactly one assigned region.

An existing primary prediction is never replaced. The rule does not inspect
reference text, edit counts or Vietnamese output to make the choice. Secondary
rows remain review-only until an independent source/role review confirms them;
they never receive automatic balloon ownership, erasure, memory or speaker
authority.

## Fresh private replay

On the same fingerprint and eight-page/78-label development set:

| Route | Assigned | Exact | CER |
|---|---:|---:|---:|
| PP baseline | 62/78 | 35/78 | 28,65% |
| CTD line whole-page | 63/78 | 44/78 | 16,72% |
| Missing-only CTD fallback | **74/78** | **45/78** | **18,85%** |

The fallback adds 12 secondary rows. It improves coverage and exact count over
baseline, but its CER is worse than selecting CTD for all pages and it remains
far from 78/78. This is expected: the rule protects existing source text and
does not repair recognizer errors or overmerged regions. It is not a production
default and has no live latency measurement yet.

Next candidate: run this fallback only as a bounded second pass for regions that
are actually unassigned/uncertain, preserve both source records, and reveal the
secondary text as review until source ownership is proven. Pair it with an OCR
disagreement/quality signal; do not use gold or CER to select a reader result.

