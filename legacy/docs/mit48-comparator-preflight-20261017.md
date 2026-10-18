# manga-image-translator OCR48 comparator preflight — 2026-10-17

**Later execution:** actual model loading and three complete private-page
recognition comparisons have now run. The historical blocked/preflight entries
below are preserved; see [measured recognition and decisions](mit48-private-recognition-20261017.md)
for the current state. No OCR48 configuration was promoted.

Status: **static preflight only; candidate for isolated measurement, not product integration or promotion.** No upstream source executed, weights downloaded, credentials accessed, private images read, or OCR accuracy/latency measured in this audit. Public release metadata was read from GitHub's API. The checkout is intentionally not materialized; inspection used `git show` at the pinned commit.

## Decision

A bounded RAM-only **line recognizer comparator is feasible in principle**. OCR48 is genuinely distinct from `kha-white/manga-ocr-base`: its pinned implementation is a custom ConvNeXt backbone plus XPOS autoregressive encoder/decoder and its own alphabet/checkpoint, not the project's `ModelMangaOCR` route. This establishes architectural/checkpoint distinctness, **not independent training data, superior accuracy, or readiness for live CPU operation**. [Pinned OCR48 source](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/model_48px.py), [separate OCR dispatch routes](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/__init__.py).

Do not import the unmodified package into the companion or call its general entry point. The package initializes dotenv/colorama and imports the whole pipeline; its wrapper can download models, move files, log transcripts and write crops. An external definitions-only runner can avoid those side effects without rewriting the model or beam-search methods. This runner would remain a GPL-derived experimental comparator, outside the distributable. [Package initialization](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/__init__.py), [wrapper/download path](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/utils/inference.py), [OCR48 wrapper](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/model_48px.py).

## Immutable source and checkpoint identity

Source commit: `d6de6ab62a7be6afc0d07a3184149cdefbcd32f2`.

| Git object | Blob ID inspected locally |
| --- | --- |
| `manga_translator/ocr/model_48px.py` | `8a410854407f258a1bf5a5027beda09785cdcdd5` |
| `manga_translator/ocr/xpos_relative_position.py` | `cf2d9a7cb219e6590afb23b6fce6261cca134b10` |
| `manga_translator/utils/generic.py` | `f04b8094fd878f9e7abf9dd1b5fb52892033806c` |

The first-party [release API](https://api.github.com/repos/zyddnys/manga-image-translator/releases/tags/beta-0.3) returned release ID **65150069**, tag `beta-0.3`, published `2022-04-23T17:55:18Z`, and `immutable: false`. Therefore the tag/download URL alone is **not** an immutable content pin. Freeze asset ID, byte size and the SHA256 supplied by the pinned source. The API's `digest` field was empty for both assets at audit time; no actual asset bytes were downloaded or verified here. [Release page](https://github.com/zyddnys/manga-image-translator/releases/tag/beta-0.3), [source model mapping](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/model_48px.py).

| Asset | GitHub asset ID | Exact bytes | Pinned source SHA256 |
| --- | ---: | ---: | --- |
| `ocr_ar_48px.ckpt` | 139530835 | 204290192 | `29daa46d080818bb4ab239a518a88338cbccff8f901bef8c9db191a7cb97671d` |
| `alphabet-all-v7.txt` | 139530818 | 186651 | `f5722368146aa0fbcc9f4726866e4efc3203318ebb66c811d8cbbe915576538a` |

API-addressable asset metadata: [checkpoint](https://api.github.com/repos/zyddnys/manga-image-translator/releases/assets/139530835), [alphabet](https://api.github.com/repos/zyddnys/manga-image-translator/releases/assets/139530818). Expected download names are the two above under the `beta-0.3` release. Asset IDs can be deleted/replaced, so the runner must still verify size and SHA256 before loading; never accept a new hash automatically.

## Minimum isolated source/dependency surface

The recognition-only path needs Python standard-library `math`, typing names and `collections.defaultdict`; third-party `torch`, `numpy`, `einops`; and `cv2` for exact upstream polygon rectification. It does **not** need Hugging Face, transformers, translation SDKs, detector weights, inpainting, font files or the full upstream requirements lock. Importing the full package would pull many of those unrelated modules. [OCR48 definitions](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/model_48px.py), [XPOS definitions](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/xpos_relative_position.py), [package import](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/__init__.py).

For a source-hash-checked AST extraction, the inference dependency closure is:

- `model_48px.py`: `ConvNeXtBlock`, `ConvNext_FeatureExtractor`, `transformer_encoder_forward`, `XposMultiheadAttention`, `OCR`. Preserve the complete method bodies. For the existing scalar-beam method as a separately named candidate, also include `Hypothesis`, `next_token_batch`; `generate_square_subsequent_mask` supports the class's training `forward` method but is not called by either beam inference method. `Beam` is not called by those methods.
- `xpos_relative_position.py`: `fixed_pos_embedding`, `rotate_every_two`, `duplicate_interleave`, `apply_rotary_pos_emb`, `XPOS`. Do not call the unused `apply_rotary_pos_emb2d` (it contains `breakpoint()`), `XPOS2D` or test entry points.
- Exact line rectification from `generic.py`: `sort_pnts`, and `Quadrilateral.__init__`, `.structure`, `.get_transformed_region`; the property uses `functools.cached_property`. Selecting just these methods avoids unused shapely/PIL/network helpers. If preserving the whole `Quadrilateral` definition instead, its annotated methods additionally require `BBox` and `Polygon` names and decorators at definition time; do not solve this by importing the whole package.

This is a proposed audited extraction boundary, not a tested compatibility claim. Keep generated source only under ignored comparator artifacts, record selected node names and full source hashes, reject unexpected definitions, and do not let inference fetch/import remote code. Compare exact rectification pixels against the pinned method on synthetic horizontal, vertical, rotated and clipped polygons before any accuracy claim. A single-polygon experiment can use that polygon's own direction; matching the multi-line wrapper requires the direction consensus described below. [Model source](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/model_48px.py), [geometry source](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/utils/generic.py).

## Inputs, orientation and numerical recipe

`OCR(dictionary, 768)` sets **`max_len=768`, not a 768-wide embedding**. Actual `embd_dim=320`, four attention heads, four encoder layers and five decoder layers; the local `n_decoders=4` variable is not what controls the five-layer decoder loop. The backbone reduces height 48 to 1 and width approximately fourfold. The wrapper calls `infer_beam_batch_tensor(..., beams_k=5, max_seq_length=255)`. [Architecture and wrapper](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/model_48px.py).

The intended unit is a **text line polygon**, not an arbitrary entire multi-column balloon. `sort_pnts` itself cautions that orientation inference is reliable for lines, not blocks. A supplied ground-truth bbox spanning multiple vertical columns must not be treated as proof of recognizer-only performance: choosing/splitting columns is a separate ownership/grouping decision. [Geometry](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/utils/generic.py).

Exact quadrilateral path:

1. Sort four points using upstream `sort_pnts`; compute midpoint structure vectors and their norm ratio.
2. Truncate polygon coordinates to int64 as upstream does; clip the enclosing image slice to source dimensions. The slice is `img[y1:y2, x1:x2]`, not inclusive of its upper edge.
3. Horizontal: output height 48 and width `max(round(48 / ratio), 2)`. Vertical: rectify to width 48, height `max(round(48 * ratio), 2)`, then rotate **90 degrees counterclockwise**. This rotation is part of this recognizer's learned input convention, not a generic claim that Japanese glyphs should be rotated for other OCRs.
4. Use `cv2.findHomography(..., cv2.RANSAC, 5.0)` and `cv2.warpPerspective` as written; do not replace with a PIL crop/resize and call it upstream-equivalent.
5. RGB uint8 input; pad each batch to `4 * (max(widths) + 7) // 4` pixels with zeros. Normalize `(float_pixels - 127.5) / 127.5`; permute NHWC to NCHW.

The common wrapper first builds a neighbor graph using `quadrilateral_can_merge_region(..., aspect_ratio_tol=1)`, chooses majority direction per component, sorts horizontal lines top-to-bottom or vertical lines right-to-left, then yields **individual** polygons. It does not concatenate pixels into a union crop there. The recognizer wrapper then sorts by resized width for batching; retain source IDs to invert this permutation. A line-only challenger with externally fixed orientation is a different, explicitly named configuration from this direction-consensus wrapper. [Common OCR](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/common.py), [geometry](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/utils/generic.py).

## Raw output, confidence and source-visible caveats

The beam method returns token IDs, a scalar `prob`, and foreground/background color outputs. The wrapper removes `<S>`, stops at `</S>`, maps `<SP>` to an ASCII space, and otherwise joins alphabet entries verbatim. It applies **no Japanese punctuation/quote stripping** in this path. The dictionary is loaded as `[s[:-1] for s in fp.readlines()]`; preserve exact bytes/line endings and this behavior for the literal comparator. Retain token IDs, raw decoded text, original polygon/source members, selected direction, transform dimensions, confidence and rejected reason, not just accepted output. [OCR48](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/model_48px.py).

Important static observations, **not runtime-confirmed failures**:

- The tensor beam path uses summed token log-probabilities and returns their exponential. The older scalar beam path uses a mean-log-probability statistic. These scores are not interchangeable/calibrated correctness probabilities. The wrapper's default rejection threshold is 0.2, which can introduce length-related coverage differences. A raw-recognizer probe may record low-score text without dropping it, but must report that separately from the literal wrapper's accepted output, never silently claim equivalent pipeline recall.
- After per-sample top-k selection, tensor beam code gathers new token sequences/log scores but does **not** visibly gather cached decoder histories using those same parent-beam indices. This is a source-level history-association concern. Preserve it for a literal pinned comparator; if experimentally corrected, record a different algorithm/version and paired test it. The existing scalar `infer_beam_batch` is also a separate candidate, not a silent replacement for the wrapper's current tensor call.
- No unconditional CUDA operation is visible on the tensor inference route; tensors generally follow `img.device`. This supports feasibility on CPU, not proven compatibility or acceptable latency. There are manual calls/assignments of `TransformerEncoderLayer.forward` and reliance on module internals; test against the actual pinned installed PyTorch version instead of installing the entire unrelated upstream requirements set.
- Tensor final color extraction uses a different shape/path than the older per-character scalar path. Do not grant erasure authority from OCR-predicted colors in a recognition-only experiment.

These issues are reasons to measure raw line accuracy, coverage and implementation variants separately, not reasons to modify source text or labels to make the score pass. [Both beam implementations and wrapper](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/model_48px.py).

## Safe load and side effects

The pinned wrapper calls `torch.load(path)` without explicit `weights_only` or `map_location`; its behavior therefore depends on the installed PyTorch default. Require `torch.load(path, map_location='cpu', weights_only=True)` in the isolated loader, after exact size/SHA256 verification, and validate a plain tensor state dict with expected shapes before `load_state_dict(..., strict=True)`. If restricted loading fails, stop: no fallback to `weights_only=False` or arbitrary safe-global allowlisting. PyTorch documents the restricted loader and warns that unsafe pickle loading can execute code. It also notes that CPU mapping avoids a GPU-memory surge. `weights_only=True` reduces pickle exposure but is not a general memory/denial-of-service sandbox. [PyTorch load reference](https://docs.pytorch.org/docs/2.9/generated/torch.load.html), [upstream load](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/model_48px.py).

Side-effect inventory:

| Route | Visible effect | Comparator restriction |
| --- | --- | --- |
| package `__init__` | dotenv/colorama initialization, pipeline import | Do not import |
| `Model48pxOCR.__init__` | mkdir; moves matching files from current directory | Do not instantiate wrapper |
| `ModelWrapper.load/download` | can download missing model files, write `.part`, verify/move assets | No downloader/imported network path during inference |
| verbose OCR48 | writes per-crop PNGs under `MANGA_OCR_RESULT_DIR` or `result/ocrs/` | Never call |
| ordinary OCR48 wrapper | `logger.info` includes full recognized transcript | Never call; metadata-only diagnostics |
| `convert_pl_model` and test functions | unrestricted load and test image I/O/printing | Exclude/cannot call |
| selected model/XPOS tensor definitions | no visible network/image/logging calls | Audit/freeze exact definitions; subprocess resource bounds |

Sources: [package](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/__init__.py), [wrapper](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/utils/inference.py), [OCR48](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/model_48px.py).

## RAM and executable next step

The checkpoint file is **194.83 MiB**, not a multi-gigabyte artifact. This is not a measured resident-model size: serialization overhead, dtypes, tied embedding/output weights and state-dict storage can differ. Standard loading temporarily holds both an initialized model and loaded state tensors, plus the PyTorch/OpenCV runtime and activations. Do not assert an exact parameter count or peak RAM without inspecting restricted tensor metadata/measuring the process. [API bytes](https://api.github.com/repos/zyddnys/manga-image-translator/releases/assets/139530835), [model construction/load](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/model_48px.py).

For a proposed batch-one, max-rectified-width-2048, beam-five, sequence-255 pilot, the explicit repeated decoder cache alone is `1 * 5 * 6 * 255 * 320 * 4 = 9,792,000` bytes (~9.34 MiB). This excludes backbone features, attention matrices, temporary top-k hypotheses, runtime and parameters; it is **not** a peak estimate. Reject/record oversize lines rather than silently resize/truncate them beyond the pinned crop recipe. Batch one and one page/crop at a time limit growth; they do not prove the wrapper's default batch-16 behavior. [Tensor cache allocation](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/model_48px.py).

The parent measured only ~554 MiB available RAM during this audit. That is insufficient evidence for a safe model+runtime load, even for this ~195 MiB checkpoint. Do not start inference merely because checkpoint bytes fit. Prepare the metadata-only runner and fail-closed preflight now; later perform a single bounded process with no Paddle/manga-ocr simultaneously, process/RSS monitoring, finite timeout and preserved terminal status. No cold/warm p95 or live-read performance claim is available yet.

## License and remaining provenance

The repository's pinned root license is **GPL-3.0**. Extracting its classes is still derived code, not a permissive-license workaround. Keep the comparator separate; no copy into extension/companion distribution and no automatic promotion on accuracy. XPOS carries a Microsoft MIT header, but that does not relicense the surrounding model. This audit did not find a dedicated OCR48 checkpoint model card, explicit separate weight license, complete training-data inventory or independently reported Japanese benchmark in the inspected model/release/training README. Record those as **unknown**, not implicitly Apache/MIT or cleared for redistribution. [Root license](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/LICENSE), [XPOS header](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/xpos_relative_position.py), [OCR training README](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/training/ocr/README.md), [release](https://github.com/zyddnys/manga-image-translator/releases/tag/beta-0.3).

Next useful evidence: validated RAM-only rectification/inference smoke on synthetic pixels; then raw OCR48 line outputs on the **same retained detector polygons** as the control, preserving empty/low-score/oversize IDs and source ownership. Separately record supplied-crop performance with column ownership explicitly documented. Do not use the Japanese gold as an inference hint, select output by gold, infer speakers, erase pixels, promote defaults, or claim this route reaches 78/78 before paired real-image measurement.

## Implementation checkpoint — isolated adapter prepared, no recognition score

`scripts/benchmark_mit48.py` now provides the external-only adapter. It checks
the three complete source SHA256 values before selecting definitions from local
Git objects. No package import, wrapper, demo, downloader or transcript logger
is executed. Selected definitions are compiled in RAM, not copied into the
companion or extension. This boundary is not a general Python sandbox and does
not clear GPL/checkpoint redistribution obligations.

Both exact-size/SHA256-checked model assets are now present under ignored
`artifacts/comparator-models/mit48/`. The official `einops==0.8.1` pure-Python
wheel is pinned separately (64,359 bytes; SHA256
`919387eb55330f5757c6bea9165c5ff5cfe63a642682ea788a6d472576d81737`)
and imported from its checked wheel only in the comparator process. There was
no package install or dependency change to the production environment.
[First-party package metadata](https://pypi.org/pypi/einops/0.8.1/json).

Observed preparation checks:

- Four synthetic horizontal/vertical/rotated/clipped geometry cases matched
  independently specified homography destinations pixel-for-pixel. This is an
  adapter check, not an OCR accuracy score or full direction-consensus parity.
- The actual eight-page tiled-recall proposal artifact contains 140 retained
  app units / 214 original detector members; 36 units have multiple members.
  All 214 real member polygons rectify within the 2,048-pixel line-width bound.
  Private numeric evidence: `artifacts/private-mit48-geometry-20261017.json`.
  No source/crop/mask/preview was written to disk. These are the **unpromoted
  tiled candidate's** proposals, not a newly improved production detector.
- Isolated einops rearrangement matched the equivalent NumPy operation;
  PyTorch was not imported in that smoke check.
- No real model state has been loaded and no recognition has run. Current
  available RAM was about 441 MiB in the last launch preflight, below the
  conservative 2 GiB **free-memory launch guard**. That guard is not a measured
  model peak. Installed PyTorch metadata is `2.14.1`; runtime compatibility with
  the pinned model remains unmeasured.

The recognition runner preserves raw token IDs/text, sum/mean score semantics,
upstream threshold acceptance, end-token termination, source members and failed
IDs. Tensor and scalar modes are separately named. It does not correct the
suspected upstream tensor-beam history issue silently. It has a batch-one width
bound, a separate timeout-bounded child process and per-page process-memory
diagnostics. Partial/aborted runs cannot be declared complete quality scores.
The Japanese references and their boxes are used only for post-inference
alignment; they are not input crop/beam hints.

Reproduce the preparation (already run):

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_mit48.py --preflight --rectification-smoke
.\.venv\Scripts\python.exe scripts/benchmark_mit48.py --geometry-only --folder 'C:\Users\Huy\Downloads\drive-download-20261012T095418Z-1-001' --proposals artifacts/private-pages-tiled-recall-v1-20261017.json --output artifacts/private-mit48-geometry-20261017.json
```

The geometry output command intentionally refuses an existing destination.
For another run, choose a new ignored private JSON filename.

Next, **when the resource gate passes**, run `--folder` and `--proposals` with
a new output path, first `--beam tensor`, then separately `--beam scalar`.
Compare to manga-ocr on the *same 214 line members/140 recorded app units*,
reporting line output, unit order and label alignment separately. This adapter
is not a full upstream detector/OCR/grouping/inpainting benchmark. No default,
reader binding, personal Edge installation or cloud budget was changed.

Verification of this source-only checkpoint: Python **1,361 passed, 1 skipped**;
TypeScript **60 passed**; typecheck passed. The comparator-specific tests include
restricted/strict CPU checkpoint loading with no unsafe fallback, preservation
of quotes/expressive spaces, retained low-score/failed IDs, pre-import memory
gating and geometry-only operation without an OCR model. These software tests
are not recognizer quality measurements. No extension/companion was packaged or
installed in the personal browser in this checkpoint.

## Loader implementation checkpoint — mmap/meta, not a measured RAM saving

The external probe now accepts `--loader copy` (unchanged control/default) or
`--loader mmap-meta` (explicit candidate). The latter uses restricted CPU
`torch.load(..., mmap=True, weights_only=True)`, meta construction and strict
assignment. Before assignment it checks the complete key set, shape, dtype,
stride, layout and CPU materialization against the constructor's state. It
rejects inconsistent embedding/output weights, restores their original
Parameter tie, and checks registered/nonpersistent buffers and tensor
attributes in module containers for surviving meta/non-CPU state. There is no
unsafe load, dtype conversion or conventional-loader retry on failure.

`--load-only --output artifacts/<new-name>.json` is a separate, finite-timeout
child operation. It reads no source images and runs no recognition. Its report
contains load duration, process peak working set, physical memory and Windows
available commit before/after; it explicitly has no OCR score. Neither this
operation nor full inference bypasses the existing 2 GiB free-RAM launch gate.
Before/after counters do not measure minimum system headroom during a run.

Executed evidence in this checkpoint:

- The new success-path boundary test failed first because the loader option did
  not exist. Schema/materialization cases then failed against the incomplete
  implementation and passed after validation was added. Tests use a lightweight
  substitute for the third-party Torch/checkpoint boundary, **not real weights**.
- Comparator tests: **29 passed**. Full Python: **1,372 passed, 1 skipped**;
  TypeScript: **60 passed**; typecheck passed. Four independently specified
  homography smoke cases remain pixel-equal. These are software/geometry checks,
  not recognition quality, numeric parity or a real meta-constructor test.
- Non-executing `pickletools` inspection of the verified checkpoint found
  `embd.weight` and `pred.weight` referencing the same storage key `665`, offset
  `0`, shape `(46272, 320)`, stride `(320, 1)`. This is archive metadata evidence,
  not a restricted Torch-load or numeric-equivalence result.
- The actual `--load-only --loader mmap-meta` command stopped at the parent RAM
  gate before spawning/importing Torch. Preflight readings were approximately
  0.42–0.94 GiB available; no load report, model inference or fresh OCR score was
  produced. No personal browser, dataset label, model default or cloud budget
  changed. No images were written.

Next execution, only when the unchanged resource gate passes: run copy and
mmap/meta load-only smokes **sequentially**, then compare numeric/token outputs
under the same full beam settings before using the candidate for private-page
recognition. A successful load alone would not permit promotion or establish
safe full-inference RAM. Use an owned, supervised child for that measurement;
do not start concurrent model processes or equate page-file free space with
Windows available commit. The production OCR accuracy remains unchanged.
