# CTD line comparator and hybrid router — 2026-10-16

This is a private, offline comparator. The CTD checkpoint is pinned and
checksum-verified by `scripts/benchmark_ctd.py`; it is not included in the
product bundle and no upstream GPL code is imported. The current adapter keeps
the predicted masks in RAM and never grants them erasure authority.

## Fresh CTD line run

On the same private development fingerprint
`445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`:

| Route | Exact | Assigned | Edits / 939 | CER | Regions |
|---|---:|---:|---:|---:|---:|
| Production PP v20 | 35/78 | 62/78 | 269 | 28.65% | 132 |
| CTD line output | 44/78 | 63/78 | 157 | 16.72% | 80 |

Stage diagnostics for CTD are: 35 exact single-region, 9 exact ordered
multi-region assemblies, 4 grouping mismatches, 15 OCR mismatches, 1 partial
detector overlap and 14 detector misses. The lower grouping error is the main
observable gain; the remaining detector misses show that CTD is not a complete
recall solution.

The detector took roughly 4.8–5.4 seconds per warm page with eight OpenCV
threads, before OCR, translation or browser paint. The first page includes
model startup. Full CTD page totals in that run were still roughly 8.2–13.8
seconds after OCR, so this is not within the cloud-page latency target.

An explicit ONNX Runtime CPU backend was also added as a comparator-only
experiment. On the same MN109-03 image it detected 13 regions in about 17.7 s
(including session startup), slower than the OpenCV DNN path; it is therefore
not a speed fix and is not selected by the router. Eight OpenCV threads did
not change CTD quality on the eight-page replay.

## Candidate hybrid

`scripts/probe_hybrid_page_router.py` evaluates a page-level policy without
using gold labels to make the decision. With `baseline.review_count >= 4`, it
selects the CTD page; otherwise it keeps the PP page. On this development set:

| Policy | Exact | Assigned | CER | Selected page p50 | Selected page p95 |
|---|---:|---:|---:|---:|---:|
| PP only | 35/78 | 62/78 | 28.65% | — | — |
| Hybrid threshold 4 (CTD 8 threads) | 48/78 | 70/78 | 13.95% | ~9.3 s | ~31.2 s* |

\* The p95 value includes the cold PP first-page measurement in the stored
report and is not a valid population p95; warm page totals remain above the
8-second target on several selected pages.

The timing is a report-level estimate and does not include the cost of lazily
starting CTD only after a runtime decision. It is therefore an upper-bound
quality probe, not a live latency claim. Thresholds 4–6 produced the same
selection on these eight pages; this is not calibration.

## Decision

Do not change the production detector yet. The candidate needs:

1. a true held-out set with independently reviewed Japanese/role/grouping gold;
2. a warm/cold resource profile after lazy CTD startup;
3. a way to reduce CTD CPU latency or run it only as a bounded prefetch/review
   path;
4. protected-art and integrated-lettering checks on the selected pages.

No cloud request, paid generation, default change, or Edge update was made by
this experiment.
