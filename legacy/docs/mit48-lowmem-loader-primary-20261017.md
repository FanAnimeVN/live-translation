# OCR48 memory-efficient loader: primary-source review — 2026-10-17

Status: **read-only static investigation, not an executed loader, memory result, or OCR score**. No Torch import, model execution, model download, credential access, or private image access occurred in this investigation. Only this note was written. This concerns the external GPL comparator, not a new product dependency.

## Decision

`torch.load(path, mmap=True, weights_only=True, map_location="cpu")` plus meta construction and `load_state_dict(strict=True, assign=True)` is a supported **candidate loading recipe**. It avoids eagerly copying checkpoint storages and allocating a second initialized set of model parameters. It does not prove sufficient RAM, checkpoint compatibility, numeric equivalence, or acceptable inference latency. The official recipe documents the three mechanisms together, requires Torch >=2.1, and explains that ordinary loading initializes memory that will immediately be overwritten. [Official checkpoint-loading recipe](https://docs.pytorch.org/tutorials/recipes/recipes/module_load_state_dict_tips.html).

Do **not** lower the existing 2 GiB available-RAM launch guard merely because this recipe exists. The parent's ~694 MiB available reading is a resource warning, not a measured safe budget. Prepare the alternate loader and metadata checks; execute only when the existing guard and a monitored subprocess allow it, or after a separately evidenced resource policy is justified.

## Installed implementation examined without importing it

The local `.venv/Lib/site-packages/torch/version.py` reports `2.14.1+cpu`, Git revision `5c4886908584029761b579af026dcfb627c84070`. Reading a version file establishes installed source identity, not a successful Torch import or binary/runtime compatibility test.

| Local file | SHA256 observed |
| --- | --- |
| `torch/version.py` | `0d5cd125dd13835680b112f6e51c7c3187f8a2417de055ae576077a671d3d4b0` |
| `torch/serialization.py` | `889074ff77e0b214c3db0bcee406e2308977182d51cefc1e46a99c902e6cc95c` |
| `torch/nn/modules/module.py` | `800bb3aa4f59b8efd49a46381b465873067f2bbc86c3a1b5172e2c9ba0981bd7` |

Local `serialization.py` lines 1588–1601 explicitly handle `mmap=True`: require a filesystem path, select `shared=False` on Windows, and call `torch.UntypedStorage.from_file`. The Windows restriction at lines 229–246 applies to **changing mmap flags**, not to all mmap loading. Non-ZIP legacy loading with `mmap=True` raises at lines 1623–1628. Local source is authoritative for this environment; the [official load API](https://docs.pytorch.org/docs/2.14/generated/torch.load.html) likewise describes lazy storage access and CPU mapping. Do not use a `BytesIO` buffer, load to GPU, turn off `weights_only`, or change global safe globals as an automatic fallback.

## Windows: resident pages and commit are different

At the installed Git revision, the Windows private-file mapping uses `CreateFileMappingW(..., PAGE_WRITECOPY, ...)` and `MapViewOfFile(..., FILE_MAP_COPY, ...)`. The mapping is not a shared writable model file. Avoid parameter writes nevertheless: copy-on-write can allocate private pages. [Pinned PyTorch MapAllocator, lines 153–207](https://github.com/pytorch/pytorch/blob/5c4886908584029761b579af026dcfb627c84070/aten/src/ATen/MapAllocator.cpp#L153-L207).

Microsoft documents that a copy-on-write view incurs **system and process commit charge for the entire view**, because any page could become private. Thus lazily resident checkpoint pages are not zero-cost commit. This makes a physical-RAM-only inference from checkpoint bytes especially weak on Windows. Monitor available physical memory, process working set/private commitment, system commit headroom, and paging pressure; do not equate any one counter with peak RAM. [Microsoft MapViewOfFile, FILE_MAP_COPY](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-mapviewoffile#parameters).

The ~194.83 MiB checkpoint size from the earlier verified asset metadata is not peak model memory. Python/Torch DLLs, metadata, buffers, activations, attention workspaces and decoder caches remain. Full inference eventually touches many weights. This note contains **no measured saving and no safe new memory threshold**.

## Checkpoint format and safe validation

Modern Torch saves use an uncompressed ZIP container with separately stored tensor storage and metadata; mmap depends on that layout. A `.ckpt` suffix or a 2022 release date does not establish the asset's actual serialization format. Before Torch loading, inspect only a bounded ZIP directory/header after the existing size and SHA256 checks; do not extract files or execute pickle. Preserve exact original bytes. If not compatible, stop the mmap route rather than silently rewrite or unsafe-load the checkpoint. Restricted loading can still fail on unsupported content; failure is not permission to allow arbitrary classes. Torch documents metadata-only `FakeTensorMode` inspection, but that still imports Torch and is not a no-runtime resource bypass. [Official serialization layout and restricted-loading notes](https://docs.pytorch.org/docs/2.14/notes/serialization.html#serialized-file-format-for-torch-save).

The first restricted load should verify a plain string-keyed tensor state mapping, bounded key/tensor counts, expected shapes/layouts/dtypes/devices and only intended CPU tensors. `strict=True` alone checks matching keys/shapes, **not all semantic requirements**. It must not replace these checks or a runtime parity test.

## Assignment parity: tied weights, buffers and dtype

Local `nn/modules/module.py` lines 2406–2414 include parameters and persistent buffers; lines 2489–2496 replace attributes on the `assign` path rather than copying into existing parameters. Its `load_state_dict` docstring says assignment preserves checkpoint tensor properties except the module's `requires_grad`. Thus a float64/float16 checkpoint could change effective compute relative to ordinary float32 copy-loading. Reject unreviewed dtypes; do not call `.half()`, `.bfloat16()` or quantization and call it a loader-only optimization. Optimizer references are irrelevant to this inference-only runner, but must never be created before assignment. [Official Module API](https://docs.pytorch.org/docs/2.14/generated/torch.nn.Module.html#torch.nn.Module.load_state_dict).

The pinned OCR constructor explicitly ties `self.pred.weight = self.embd.weight`. Loading both keys with `assign=True` can produce distinct Parameter objects even when their underlying checkpoint storage is shared. Recommended comparator invariant: verify `embd.weight` and `pred.weight` have matching shape, dtype, stride and storage offset and either the same storage region or exactly equal values; reject disagreement rather than choose a different winner. Then restore the original tie explicitly and assert `model.pred.weight is model.embd.weight`. Re-tying equal weights restores architecture, not a new OCR algorithm. This recommendation is an inference from the constructor and local assignment implementation. [Pinned OCR constructor](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/model_48px.py#L505-L545).

The selected XPOS class registers `scale` with default persistence. ConvNeXt uses BatchNorm running buffers, which also matter at inference. Every needed persistent buffer should therefore materialize from the strict checkpoint. Do not recompute missing values silently. Inspect **all parameters and all buffers, including nonpersistent buffers**, for `is_meta` after assignment. Unregistered tensor attributes also require inspection: `named_buffers()` cannot see them. In the selected audited definitions, XPOS `scale` is the obvious custom registered tensor; no separate positional tensor cache is visible in its constructor. This is not proof a future upstream revision has the same state surface. [Pinned XPOS class](https://github.com/zyddnys/manga-image-translator/blob/d6de6ab62a7be6afc0d07a3184149cdefbcd32f2/manga_translator/ocr/xpos_relative_position.py#L41-L71).

Meta tensors carry shape/type metadata but no values; data-dependent operations such as `.item()` cannot execute on them. Constructor compatibility is consequently not guaranteed merely by the existence of the context manager. Do not use `.to_empty()` to conceal surviving meta tensors: that creates uninitialized data requiring proper initialization. The recipe must exit the meta context before creating any real inference inputs. [Official meta-device documentation](https://docs.pytorch.org/docs/2.14/meta.html).

## Smallest decisive execution sequence when resources permit

The following is a proposed experiment, **not completed evidence**:

1. **No-model preflight now:** preserve source/asset pins, inspect archive headers, test fail-closed logic without importing Torch; no dataset or network required. Keep the old conventional loader available as a named control.
2. **Load-only smoke in a fresh bounded subprocess:** after the unchanged resource guard, load the verified state with mmap/CPU/weights-only; construct the exact selected OCR definitions inside `torch.device("meta")`; strict-assign; validate dtype/shape/tie, no surviving meta tensors or unknown tensor state; call `.eval()`. Record import/load times and memory/commit counters separately. A successful import or load does not prove inference safety.
3. **Sequential loader parity, never two full models resident together:** conventional and efficient subprocesses use identical pinned dictionary, rectification, CPU dtype/thread settings, `.eval()`, inference mode, same synthetic RGB input and production beam/sequence limits. Compare raw token IDs, confidence and color outputs, not merely rounded text. Use exact equality where reproducible; record any floating discrepancy and token change. A reduced-sequence pilot may check execution but cannot establish the production configuration's parity.
4. **Real line pilot and complete private paired benchmark:** use source-owned polygons and retain oversize/empty/low-score outcomes and the full denominator. The loader must not change crop geometry, beam-cache behavior, threshold policy or punctuation. A first-crop success does not establish all-line numeric parity or 78/78 accuracy.

Timeout and memory termination must identify the exact child and preserve terminal/error status; do not restart solely because an observer timed out. Keep all image pixels in RAM, network blocked, no transcript stdout. Capture runtime versions, peak working set/private bytes, system commit before/after and exact attempted configuration. No new product default, reduced quality gate, rewritten gold, resource-policy exception or GPL redistribution follows from this note.

## What is and is not established

Established statically: the installed Python implementation supports the proposed API combination and has a Windows mmap branch; parameter assignment differs from ordinary copying; this OCR has a tied embedding/output parameter and persistent XPOS buffers; Windows COW mappings have commit implications.

Unestablished: that this checkpoint is ZIP-mmap-compatible, its restricted tensor metadata, actual meta-constructor success, peak RAM/commit, CPU instruction compatibility, inference equivalence, latency or recognition accuracy. Those require the bounded execution above. At ~694 MiB free, none should be inferred from the checkpoint size.
