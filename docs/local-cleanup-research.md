# Local text cleanup: cost, latency and visual limits

Reviewed 2026-10-13. Research/design note, not a certification of real-manga fidelity or release licensing.

## Decision for the MVP

Use the cheapest sufficient route **per region**, not one image-generation request per page. This routing is our engineering recommendation:

| Region | Route | User-facing behavior |
|---|---|---|
| Verified flat white, tinted or dark balloon | Sample the existing fill; erase only the glyph mask, including antialiased edges; render fitted Vietnamese ink | Default; preserve the balloon boundary/tail, no visible UI card |
| Small, confidently separated text over artwork | Local OpenCV Telea; preserve unmasked pixels; bounded texture continuation only for verified repetitive lines | `artCleanup` on for new/missing settings; preserve saved opt-outs; reversible; warn that details can soften |
| Large mask, face/complex geometry, uncertain text/art boundary or SFX | Keep original artwork and a reversible translation annotation | No silent redraw; do not guess hidden semantic details |
| Neural cleanup such as LaMa | Candidate for a later separately tested quality mode | **Not integrated, downloaded, pinned or benchmarked** |

OpenCV's `inpaint` takes an image and a binary mask. Telea fills the selected region using nearby known pixels; it is a classical algorithm, not a text-prompt image API. A precise mask is therefore a first-class requirement, not something better translation can fix. [OpenCV tutorial](https://docs.opencv.org/4.13.0/df/d3d/tutorial_py_inpainting.html), [API contract](https://docs.opencv.org/4.13.0/d7/d8b/group__photo__inpaint.html).

LaMa is a trained neural inpainting network using fast Fourier convolutions. Its authors demonstrate completion of periodic structures and higher-resolution images, but those results do **not** establish our CPU latency or accuracy on manga rain, screentones and character outlines. Official inference includes a CPU route. [LaMa project](https://advimman.github.io/lama-project/), [official repository](https://github.com/advimman/lama).

## Cost and reading experience

Local glyph filling and Telea make no image-generation API request: **zero additional API token/credit cost is not zero resource cost**. They still consume CPU time, RAM, battery and image encoding/transport time. A future locally executed neural model would have the same API-cost distinction but require model storage, loading and inference resources; do not invent a price or latency before measurement.

Reader-first policy: correct meaning, integrated lettering, uninterrupted reading, then more features. Inexpensive, tested local improvements are enabled without an extra consent step; paid API/credit or materially slower/heavier enhancements require separate opt-in, a clear cost/time/quality explanation and confirmation before use. Default-on never relaxes per-region safety checks. The private real-data benchmark is the next quality gate, not another synthetic speed claim.

Keep cleanup separate from translation and persistent text cache. Changing the cleanup option must not translate cached dialogue again. Limit crop area, patch bytes and concurrent work; prioritize the visible page, cancel stale jobs, and release image buffers/Blob URLs on replacement or stop. These are product design requirements, not speed guarantees. Measure cleanup-only cold/warm p50/p95 **and** end-to-end reading delay on the baseline machine; mobile needs its own battery, memory and thermal tests.

With successful cleanup, lettering can use a transparent background rather than a rectangular card. Source-like ink, whole-word line balancing and Vietnamese diacritics matter as much as erasure. Matching the original font size exactly is secondary to fitting the translated text legibly; never cut meaning to make it fit.

**Inference/limit:** a flattened scan does not uniquely reveal art hidden under text. Neighbor-based or learned restoration estimates a plausible continuation; it cannot guarantee the author's exact missing drawing. Preserve original-view access and do not describe a visually convincing reconstruction as recovered ground truth. This follows from the neighborhood reconstruction and learned completion methods above, not evidence about a competitor's implementation.

## Distribution and safety gate

OpenCV 4.13 and LaMa's source repository publish Apache-2.0 licenses. Distribution must retain the license/required notices and identify modified upstream files; those source licenses are **not** a blanket audit of every pretrained checkpoint, dataset, dependency or manga's rights. Verify the exact artifact's provenance, license and redistribution permission before bundling weights. [OpenCV license](https://github.com/opencv/opencv/blob/4.13.0/LICENSE), [LaMa license](https://github.com/advimman/lama/blob/main/LICENSE).

Pin code revisions, dependency versions and model SHA-256 checksums as required by `AGENTS.md`; no executable custom code is fetched during inference. The original LaMa loader calls `torch.load`; PyTorch explicitly warns against loading untrusted data, including with a restricted loader. Audit/convert the chosen checkpoint safely instead of running an arbitrary downloaded pickle. A checksum detects changed bytes; it does not prove trusted origin or safe contents. [LaMa loader](https://github.com/advimman/lama/blob/main/saicinpainting/training/trainers/__init__.py), [PyTorch warning](https://docs.pytorch.org/docs/2.14/generated/torch.load.html).

Images, masks and cleaned patches remain RAM-only. Offline cleanup must never call a cloud service. No user API key, private manga reference or reader memory was used for this research.
