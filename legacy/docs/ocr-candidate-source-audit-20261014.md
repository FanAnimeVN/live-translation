# Manga OCR candidates — source and provenance audit

Reviewed 2026-10-14 using public first-party cards, pinned source/configuration text, Hub APIs and released Transformers source. No weights, private dataset, inference, cloud translation or remote Python execution was used. Performance below is publisher-reported; this audit measured no OCR accuracy, latency or peak RAM.

## Decision

**Hayai Nova is the smaller practical CPU comparator after its two Python files are reviewed and vendored, with the Google vision configuration supplied locally.** Use an isolated comparator process/environment and verified local assets; never enable dynamic model-repository code downloads at inference. Its compatibility with the installed Transformers 4.57.6 is plausible from the imports and native SigLIP2 support, but needs a local load test. Paddle's manga model has a native alternative in Transformers 5, requiring a separate environment and explicit adaptation of its older processor/tokenizer metadata. Neither candidate is cleared here for a production default or commercial redistribution.

## Immutable identities

These weight sizes/hashes and parameter counts are **upstream API metadata**, not independently checked weight bytes. Serialized size is not peak memory. [Hayai API](https://huggingface.co/api/models/JustANormalTinkerer/hayai-ocr-v2.5-nova?blobs=true), [Paddle manga API](https://huggingface.co/api/models/jzhang533/PaddleOCR-VL-For-Manga?blobs=true).

| Candidate | Pinned revision | `model.safetensors` bytes / parameters | Upstream SHA-256 |
|---|---|---|---|
| Hayai v2.5 Nova | `2803d0dc005fa4396ab1e7c5a472d2c450a247f7` | 627,709,088 / 156,915,968 F32 | `ac63cd177c5b68bd91e18dd4408e0400461c7cf19f484b0da1643e232d1ffc3a` |
| PaddleOCR-VL-For-Manga | `1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8` | 1,917,255,968 / 958,588,736 BF16 | `71fcee0e3618582d4c8acc705242aa79b471b6134e7023bf3820642ba638b602` |

## Architecture, loading and CPU limits

### Hayai Nova

Source confirms SigLIP2 NaFlex vision plus a custom 12-layer causal decoder: width 512, FFN 2,048, eight query/two KV heads, spatial RoPE and a 2× projector merging four patches into one decoder token. `HayaiModel.generate(pixel_values, pixel_attention_mask, spatial_shapes, tokenizer, max_new_tokens=...)` performs autoregressive greedy decoding and returns strings; this is not the standard Transformers generation contract. The model recognizes crops and needs a separate page detector. [Pinned source](https://huggingface.co/JustANormalTinkerer/hayai-ocr-v2.5-nova/blob/2803d0dc005fa4396ab1e7c5a472d2c450a247f7/modeling_hayai.py), [configuration](https://huggingface.co/JustANormalTinkerer/hayai-ocr-v2.5-nova/blob/2803d0dc005fa4396ab1e7c5a472d2c450a247f7/config.json).

Published `AutoModel` loading uses `auto_map` and `trust_remote_code=True`. A safe comparator should import reviewed local `HayaiConfig`/`HayaiModel` directly. The constructor calls `Siglip2VisionConfig.from_pretrained("google/siglip2-base-patch16-naflex")` unless given a vision config; an outer `local_files_only=True` alone does not establish an offline constructor. Pin Google revision `b53b807d3a2d5e2b3911292f2d69e5341cdc064c`, supply its configuration locally and use a standard NaFlex image processor plus Hayai's own fast tokenizer. Google's separate 1.5-GB model weights are unnecessary. [Google configuration](https://huggingface.co/google/siglip2-base-patch16-naflex/blob/b53b807d3a2d5e2b3911292f2d69e5341cdc064c/config.json), [image processor](https://huggingface.co/google/siglip2-base-patch16-naflex/blob/b53b807d3a2d5e2b3911292f2d69e5341cdc064c/preprocessor_config.json).

Nova records `transformers_version: 5.0.0`; this records its save environment, not a demonstrated minimum. Installed 4.57.6 has native SigLIP2 mappings, while Nova itself remains custom. Source has CPU FP32/BF16 handling and a CPU attention fallback; native BF16 capability matters. Its lazy inference engine retains fused weight copies/caches, so 628 MB of weights must not be advertised as its full RAM cost. Begin FP32, batch one, a bounded patch/token budget, and measure cold/warm load, RSS and crop latency. Beam/repetition options should not be assumed implemented merely because the custom signature accepts them. [Installed-version native mapping](https://github.com/huggingface/transformers/blob/v4.57.6/src/transformers/models/auto/configuration_auto.py), [Nova source](https://huggingface.co/JustANormalTinkerer/hayai-ocr-v2.5-nova/blob/2803d0dc005fa4396ab1e7c5a472d2c450a247f7/modeling_hayai.py).

Avoid installing the full `hayai-ocr` helper just to compare: its dependency list includes torchvision, torchao, fugashi and dictionary packages. Its LiteRT artifact route names **v2**, not proven Nova parity. [Pinned helper dependencies](https://github.com/NopeNopeGuy/hayai-ocr/blob/54c2771e11424f2c732cf32be22d616220ad8c4c/pyproject.toml), [helper README](https://github.com/NopeNopeGuy/hayai-ocr/blob/54c2771e11424f2c732cf32be22d616220ad8c4c/README.md).

### PaddleOCR-VL-For-Manga

Pinned code combines a 27-layer, width-1,152 SigLIP-style dynamic vision encoder, spatial projector and an 18-layer, width-1,024 ERNIE 4.5 causal decoder. It uses an image/chat prompt, conventionally `OCR:`, then standard `generate` and decoding of tokens beyond the input prompt. Original metadata maps custom config/model/image/processor classes; its config records Transformers 4.57.1. Installed 4.57.6 lacks the native `paddleocr_vl` mapping, so the original loader would require reviewed vendored code or prohibited dynamic trust. [Pinned configuration](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/config.json), [model code](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/modeling_paddleocr_vl.py), [official inference documentation](https://huggingface.co/docs/transformers/en/model_doc/paddleocr_vl).

Transformers **5.0.0 already includes native** `PaddleOCRVLForConditionalGeneration` and `PaddleOCRVLProcessor`, with legacy flat-config parsing and checkpoint-key mappings for `visual`, `mlp_AR` and the language model. A separate pinned 5.x environment can therefore avoid repository Python, subject to checkpoint load verification. Do not assume the old manga repository's `AutoProcessor(..., trust_remote_code=False)` works unchanged: its preprocessor names `SiglipImageProcessor` and `size={min_pixels,max_pixels}`, whereas native v5.0 uses a Paddle processor and `shortest_edge`/`longest_edge`; native processing reads `tokenizer.image_token`, absent from the old tokenizer config. Build these native classes explicitly with reviewed equivalent parameters/token metadata and the pinned chat template; verify no missing model weights. [Native v5.0 config](https://github.com/huggingface/transformers/blob/v5.0.0/src/transformers/models/paddleocr_vl/configuration_paddleocr_vl.py), [native model mappings](https://github.com/huggingface/transformers/blob/v5.0.0/src/transformers/models/paddleocr_vl/modeling_paddleocr_vl.py), [native processor](https://github.com/huggingface/transformers/blob/v5.0.0/src/transformers/models/paddleocr_vl/processing_paddleocr_vl.py), [native image processor](https://github.com/huggingface/transformers/blob/v5.0.0/src/transformers/models/paddleocr_vl/image_processing_paddleocr_vl.py), [old preprocessor](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/preprocessor_config.json), [old tokenizer config](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/tokenizer_config.json).

CPU use is plausible through eager/SDPA, without optional CUDA Flash Attention. FP32 weights alone are approximately 3.83 GB, before activations/cache/framework memory. Its old generation configuration disables KV cache; record any explicit override. Published examples and GPU timings establish no Windows CPU/page acceptance result. Small bubble crops are upscaled by the old processor's minimum area of 147,384 pixels; preserve that contract during comparisons. [Generation configuration](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/generation_config.json), [preprocessor](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/preprocessor_config.json).

## Benchmarks and rights

Hayai's advertised 3.65% CER at 384 patches and 3.10% at 512 are author results on JMangaBench_Mixed; relative latency was measured on a T4 GPU. Paddle's 70% sentence accuracy versus base-model 27% is its author's result on a 10% random crop split of Manga109-s, not a documented held-out-title test. [Hayai card](https://huggingface.co/JustANormalTinkerer/hayai-ocr-v2.5-nova/blob/2803d0dc005fa4396ab1e7c5a472d2c450a247f7/README.md), [Paddle card](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/README.md).

JMangaBench_Mixed contains 1,286 real Manga109-s crops and 2,000 synthetic samples. Both candidates declare Manga109-s training, so shared source books are a concrete concern; **exact train/test crop overlap is unverified**. Its normalized/text-only metrics remove whitespace/punctuation and are unsuitable evidence that expressive punctuation is preserved. Keep raw output metrics and a frozen private, rights-eligible holdout; do not expand the benchmark merely to repeat public scores. Benchmark code/assets also have GPL and font notices if reused. [Pinned benchmark README](https://github.com/muscgab/JMangaBench_Mixed/blob/9b8396a6191597c4ed58e05d35bf9f116a1e2d81/README.md).

Both model cards declare Apache-2.0. Hayai's owning helper has an Apache LICENSE; Paddle's model source has Apache headers. Paddle's separate training repository has no detected standalone LICENSE and its README licenses the **model**, so do not infer blanket permission to redistribute all training scripts. [Hayai helper license](https://github.com/NopeNopeGuy/hayai-ocr/blob/54c2771e11424f2c732cf32be22d616220ad8c4c/LICENSE), [Paddle training repository](https://github.com/jzhang533/PaddleOCR-VL-For-Manga/tree/f2ae8850b12f62590a453d0e0dd6f056db99f79f).

Manga109-s permits commercial experiment outputs, including trained models, with clear acknowledgment. It forbids dataset redistribution and selling or treating manga-image copies/modifications as products; published page demonstrations have additional volume limits and attribution conditions. This permission does not cover unrelated manga, fonts or corpora. [Dataset owner's terms](https://huggingface.co/datasets/hal-utokyo/Manga109-s#Manga109-s%20Dataset).

Hayai's private pretraining corpus cannot be independently audited. Its linked 60,498-row and 1,824-row fine-tune cards/API metadata expose no license or complete rights ledger; the model card also lists `alpindale/light-novels`, whose publisher metadata declares a different OpenRAIL license. These are unresolved provenance/permission questions, not proof of infringement or automatic restrictions on the weights. Request the publisher's data/font rights and applicable weight/code notices before commercial packaging. Paddle's synthetic-data claim likewise supplies no complete per-source rights ledger. [Hayai alignment metadata](https://huggingface.co/api/datasets/JustANormalTinkerer/hayai-finetuning-dataset-with-korean), [final fine-tune metadata](https://huggingface.co/api/datasets/JustANormalTinkerer/hayai-finetuning-dataset-final-final), [light-novel metadata](https://huggingface.co/api/datasets/alpindale/light-novels), [Paddle training declaration](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/README.md).

## Files to audit before executing a candidate

Review the full Python, imports, constructor side effects, optional kernels, processor/tokenizer/template and generation limits. Download only approved pinned data files; independently hash all downloaded bytes. Enforce offline flags/local paths and fail closed on missing assets. Author-proposed text normalization is a metric choice, not production cleanup.

Text checksums below were calculated in RAM from the returned UTF-8 file content; byte lengths match the Hub file metadata. Each row uses its model revision above; Google uses `b53b807d3a2d5e2b3911292f2d69e5341cdc064c`. Tokenizer data files must also be reviewed and locked before loading.

| Repository / file | Bytes | SHA-256 of fetched text |
|---|---:|---|
| Hayai `config.json` | 367 | `880c99360c77733032fe06e94de8123dca21610cab782c6df43e4e26c9d37c41` |
| Hayai `configuration_hayai.py` | 401 | `47abd38cf1bae7aef27d01f5b8b4aa0960a7bc625a8afad79c4762ff5e5ed970` |
| Hayai `modeling_hayai.py` | 45,551 | `3409131b4a35fc1bc1f0d7c40f906f79d10f57476f40fe05939c5a1a0ba9d527` |
| Hayai `tokenizer_config.json` | 244 | `6fb6c69afaedf1275872d3e62e276fd4467bd00da7a84cbbb5566a2cd28f58f6` |
| Google `config.json` | 329 | `c0b8c2e7f0527b0bea1b1d9abe0381c0f294352df92439c54590b8420e539118` |
| Google `preprocessor_config.json` | 393 | `1125703e5446d5b6ff4d5893a33bac128cdd21dc12e3dad2469a648fb0ae3bf7` |
| Paddle `config.json` | 1,987 | `928aaf78567a273cb73ede3671253ec4e38eb60c27a30e945bcd13b4131a0147` |
| Paddle `configuration_paddleocr_vl.py` | 8,104 | `753dd93654c3a9c8c85a3eaee1e3092dd12591b0f2dce0305e1abfb7a41ff160` |
| Paddle `modeling_paddleocr_vl.py` | 112,163 | `351269f534882b2df200192adc3af6117910e9a7446caf0d6706366b1ed45d9f` |
| Paddle `image_processing.py` | 24,485 | `242b36a14461d81fba2913a2e736d9f7a26422c6f2cdf484a5e5a17037f78147` |
| Paddle `processing_paddleocr_vl.py` | 12,253 | `e29cb1e5f275f2bd3ce051bd5c9983a33894e693b2823a0e13d4c07c8c4f9e13` |
| Paddle `preprocessor_config.json` | 687 | `f417a7f977820dfe6828f3ec2e461c027fdb0662f25cae4e841ec1028e0b988a` |
| Paddle `processor_config.json` | 137 | `1568858960a9760c54431dae693a6152e601ff55cdf6d2eab97a4a99958faea0` |
| Paddle `generation_config.json` | 133 | `cf202f984e003e92dceaa27e749b60b4e6e1b566a1df8486b5b41adf1d016cea` |
| Paddle `chat_template.jinja` | 1,566 | `344fea8b69546526a00996468f86f583fd65441582a36f2fa4abc794aa94094c` |

Before either private comparison, sanity-check authored blank/repeated-character/horizontal/vertical crops; retain original punctuation and labels; measure actual Windows CPU load/RSS/latency. Compare the same frozen crops against manga-ocr with transformation, errors and truncation reported. Production integration, model defaults, packaging and rights clearance remain separate work.
