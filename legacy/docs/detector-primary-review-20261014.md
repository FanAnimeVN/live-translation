# Manga detector and segmentation: primary-source review

Reviewed 2026-10-14. The primary-source review below did not run inference or inspect private images. A subsequent, separate local comparator experiment is recorded at the end. Neither phase is redistribution clearance; the model is not a production default or installer asset.

## Recommendation and present evidence

Try upstream comic-text-detector (CTD) ONNX in one private, offline experiment. Its separate line and text-mask outputs directly address crop/grouping and lettering questions. CPU support is established in source; improved recall, mask safety, speed, RAM use and downstream OCR remain unmeasured here. A CPU route does not establish a lightweight improvement over PP-OCRv5_mobile_det.

Current private evidence: 8 eligible pages / 78 crop labels; direct manga-ocr CER 9.37%, 48/78 exact; full-page alignment found predictions for 53/78 labels and emitted 113 regions; strict layout v8 accepts one flat balloon. These describe different pipeline stages. Alignment coverage is not a complete detector recall/precision benchmark; transcription issues also qualify the OCR figures. More detected regions alone would not prove an improvement.

## What the owning sources establish

| Candidate | Outputs and local feasibility | Constraint for this task |
|---|---|---|
| dmMaze CTD | YOLO block boxes, DB-style lines, segmentation mask; existing ONNX/OpenCV CPU route | Evaluate raw outputs separately from its grouping/refinement heuristics |
| manga-image-translator CTD integration | Textline quadrilaterals plus refined text mask; explicitly loads ONNX on CPU | Uses a later line merger rather than the original YOLO grouping |
| manga-image-translator default | ResNet34 detector, line polygons and mask, PyTorch CPU route | 294 MB checkpoint and no ONNX loading path in reviewed implementation |
| CRAFT, sole additional candidate | CPU PyTorch inference, character-region/affinity maps and boxes/polygons | General scene-text comparator; lower priority for manga and erasure |

CTD's original inference returns raw mask, refined mask and grouped blocks. Preserve pre-grouping lines/boxes for evaluation rather than importing its complete annotation script, which writes images to disk. [Pinned CTD inference](https://github.com/dmMaze/comic-text-detector/blob/440b978563c71b758e31aaa315d100faba1efa2f/inference.py).

Its grouping assigns lines by box overlap, can reject scattered lines with low mask density, splits Japanese/vertical blocks by spacing, merges remaining lines, and orders blocks geometrically. Its `eng`/`ja`/`unknown` classes are language labels, not dialogue/narration/SFX/importance labels. [Pinned grouping code](https://github.com/dmMaze/comic-text-detector/blob/440b978563c71b758e31aaa315d100faba1efa2f/utils/textblock.py).

The translator CTD implementation discards YOLO grouping, emits `Quadrilateral` lines and calls mask refinement with `refine_mode=None`. It defaults to 1024 input, a 0.3 segmentation representer threshold and a hard-coded 0.6 line score cutoff. Its `_infer` accepts generic detection settings but does not use those arguments to set these values. It also handles OpenCV versions swapping mask/line output order. Record actual preprocessing and thresholds, not merely a shared config name. [Pinned translator CTD](https://github.com/zyddnys/manga-image-translator/blob/95227a2bb0fd306cd4f0c104d57284026f991b3a/manga_translator/detection/ctd.py).

The separate merger uses geometry, graph components, spacing/font-size heuristics and vertical right-to-left ordering. This is a grouping candidate, not a semantic role classifier or proof of balloon ownership. [Reviewed merger](https://github.com/zyddnys/manga-image-translator/blob/main/manga_translator/textline_merge/__init__.py).

Mask refinement combines image color/Otsu candidates and connected components against the predicted mask; its inpaint mode additionally dilates. Inference: a useful text-mask estimate still needs independent checks for glyph residue, antialiased edges and intrusion into art/balloon boundaries. It does not supply the original art hidden under ink. [Reviewed refinement](https://github.com/zyddnys/manga-image-translator/blob/main/manga_translator/detection/ctd_utils/textmask.py).

The default detector imports ResNet34, loads `detect-20241225.ckpt` with `torch.load`, and returns lines plus raw mask. [Pinned default implementation](https://github.com/zyddnys/manga-image-translator/blob/95227a2bb0fd306cd4f0c104d57284026f991b3a/manga_translator/detection/default.py). The upstream release lists CTD ONNX at 90.3 MB, CTD PT at 76.2 MB and that default checkpoint at 294 MB. These are displayed artifact sizes, not peak RAM or latency. [Owning release assets](https://github.com/zyddnys/manga-image-translator/releases/expanded_assets/beta-0.3).

CRAFT explicitly supports `--cuda false`; its score maps represent character regions/links, and postprocessing produces boxes/polygons. These maps are not validated glyph erasure masks. [Official inference](https://github.com/clovaai/CRAFT-pytorch/blob/master/test.py), [architecture](https://github.com/clovaai/CRAFT-pytorch/blob/master/craft.py). The official README describes general multilingual weights; the translator's own configuration cautions against CRAFT for manga. This supports deferring it, not a measured claim that it loses on these pages. [Official README](https://github.com/clovaai/CRAFT-pytorch), [translator configuration](https://github.com/zyddnys/manga-image-translator/blob/main/manga_translator/config.py).

## Licensing and loading boundaries

Both CTD and manga-image-translator repositories publish GPL v3 code licenses. Copied/modified covered code and distributed binaries carry license/notices and corresponding-source obligations; a helper process is not automatic clearance for the surrounding product. The reviewed owning README, release and model mappings do not provide a distinct explicit asset-level weight license. Record that uncertainty before bundling or redistributing checkpoints. [CTD license](https://github.com/dmMaze/comic-text-detector/blob/master/LICENSE), [translator license](https://github.com/zyddnys/manga-image-translator/blob/main/LICENSE).

CTD describes approximately 13,000 training images with weak supervision and says it lacks rights to share training images/fonts. This limits reproducibility/provenance claims; it does not itself establish a separate noncommercial inference restriction. [Owning training description](https://github.com/dmMaze/comic-text-detector).

CRAFT code is MIT. Its README links pretrained weights but does not separately spell out the external files' license scope. Do not silently treat code permission as a completed weight/dependency audit. [Official license](https://github.com/clovaai/CRAFT-pytorch/blob/master/LICENSE), [weight links](https://github.com/clovaai/CRAFT-pytorch#test-instruction-using-pretrained-model).

CTD CPU artifact identity in the pinned translator mapping: release `beta-0.3`, `comictextdetector.pt.onnx`, SHA-256 `1a86ace74961413cbd650002e7bb4dcec4980ffa21b2f19b86933372071d718f`. This hash is upstream-declared; bytes were not independently downloaded/verified here. [Pinned mapping](https://github.com/zyddnys/manga-image-translator/blob/95227a2bb0fd306cd4f0c104d57284026f991b3a/manga_translator/detection/ctd.py).

Prefer the existing ONNX artifact over loading arbitrary PT/CKPT pickles. CTD's PT loader calls `torch.load`; PyTorch warns that untrusted serialized input is unsafe, including with restricted loading. [CTD loader](https://github.com/dmMaze/comic-text-detector/blob/master/basemodel.py), [PyTorch contract](https://docs.pytorch.org/docs/2.14/generated/torch.load.html). A checksum binds bytes; it does not prove permission, trusted origin or safe content.

The translator's wrapper auto-downloads missing mapped files and checks cached file existence rather than rehashing every existing file. CTD maps both PT and ONNX, so use a narrow local-file adapter with explicit validation and offline failure instead of inheriting that acquisition behavior. Pin reviewed code, dependencies and artifact hash; never fetch executable custom code during inference. [Wrapper](https://github.com/zyddnys/manga-image-translator/blob/main/manga_translator/utils/inference.py).

ONNX Runtime has a CPU execution provider, but this particular artifact is established upstream through OpenCV DNN. ORT compatibility, named outputs, input/channel handling and parity require a separate check; no conversion/quantization gain is demonstrated. [ORT contract](https://onnxruntime.ai/docs/api/python/api_summary.html), [CTD DNN implementation](https://github.com/dmMaze/comic-text-detector/blob/master/basemodel.py).

## Bounded next experiment, not a default change

1. Freeze the 8 pages, eligibility and existing labels. Have a human audit disputed transcriptions against the originals; keep an amendment record. Report both original-label metrics and audited/unresolved subsets. Never replace gold with OCR predictions.
2. Compare current PP detection against one pinned CTD ONNX run, retaining raw lines and masks in RAM. Hold OCR/crop settings constant; compare identical grouping first, then make one separate grouping ablation. Record missed labels, duplicates, false detections, cross-balloon merges, order errors and one-to-many coverage. Do not suppress small/balloonless text by detector confidence or inferred importance.
3. On a fixed small subset spanning flat balloons, dense/vertical text and art contact, human-mark glyphs and protected boundaries privately. Measure raw/refined mask residue and damage separately. OCR labels cannot validate erasure or Vietnamese lettering; uncertain regions retain original art plus reversible annotation. Keep strict layout v8 safety thresholds.
4. On the target CPU, measure one cold start and three warm passes per page: detector, grouping, mask refinement, unchanged OCR and total time; record peak RSS and actual thread count. Report per-page values and descriptive tail figures, with the small/repeated-sample limitation. Stop at this experiment; expand only if coverage/grouping improves without unsafe erasure and measured cost is acceptable. No cloud call, key handling, larger dataset or packaging is part of this research.

Expected result: evidence to choose a detector and identify remaining mask/grouping failures. No source or current measurement supports 100% OCR, complete semantic filtering, perfect original-art reconstruction, or the product latency targets.

## Subsequent local experiment — measured, not an upstream claim

One official release ONNX artifact was fetched explicitly into gitignored `artifacts/comparator-models/` and verified: 94,669,756 bytes, SHA-256 `1a86ace74961413cbd650002e7bb4dcec4980ffa21b2f19b86933372071d718f`. No pickle/checkpoint or executable custom code was downloaded, and no upstream GPL Python implementation was copied/imported. Unclear weight redistribution remains unresolved.

`scripts/benchmark_ctd.py` runs OpenCV DNN on CPU, 4 threads, 1024-square RGB/255 input with right/bottom black padding. Validated outputs are blocks `[1,64512,7]`, lines `[1,2,1024,1024]`, raw mask `[1,1,1024,1024]`. Line decoding uses the existing Apache PaddleX DB decoder (.3 threshold, .6 score, 1.5 unclip); blocks use objectness × class, .4 score and .35 NMS. This is **not bit-for-bit upstream CTD postprocessing parity**. Raw masks stay in RAM and never authorize erasure.

Same 8 eligible private pages / 78 original labels, unchanged manga-ocr and app grouping/layout v9:

| Route | Regions | Labels with assigned prediction | Alignment CER / exact | Flat balloons | Warm detector/page |
|---|---:|---:|---|---:|---|
| Production PP-OCRv5 mobile | 113 | 53 | 36.63% / 39.74% | 8 | 1.05–1.39 s |
| CTD lines + PaddleX decoder | 74 | 56 | 26.62% / 50.00% | 15 | 8.41–9.23 s |
| CTD blocks | 63 | 58 | 29.39% / 46.15% | 22 | 7.92–8.43 s |

These are containment-based alignment diagnostics, not full detector recall/precision or a passing quality gate. Labels remain disputed; the lines route missed the cover entirely. Flat-balloon acceptance is not original-art/erasure fidelity. One pass does not establish p95, peak RAM or a controlled repeat benchmark.

Conclusion: retain PP as the production baseline while studying missing/cross-region text. CTD is promising for some geometry but much slower on this CPU, incomplete and not cleared for weight distribution. Do not integrate/bundle it from these figures. No cloud call or larger dataset was used in this experiment.

Private evidence: `artifacts/private-pages-20261014-v9.json`, `artifacts/private-pages-20261014-ctd-lines.json`, `artifacts/private-pages-20261014-ctd-blocks.json`. The subsequent production v10 ownership fix has its own rerun; do not mix its region counts into this comparison.
