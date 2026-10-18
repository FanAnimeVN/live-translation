# Paddle manga OCR — native Transformers adapter review

Reviewed 2026-10-14. Scope: public primary-source/configuration review of `jzhang533/PaddleOCR-VL-For-Manga` revision `1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8` through **Transformers 5.0.0**, without model-repository Python or `trust_remote_code`. Also read the local comparator `scripts/benchmark_paddle_vl.py`; did not edit it. No weights, private images/labels, model inference, cloud translation, or environment changes were used for this review.

## Verdict

**A native-only comparator is source-supported, but successful checkpoint loading and numerical/output parity remain verification gates.** Transformers 5.0.0 contains the explicit config, model, image processor, and processor classes, including migrations for this older flat configuration and checkpoint namespaces. It is not safe to assume that the old repository's `AutoProcessor` metadata works unchanged: its custom image processor name, legacy size keys, and absent named image token need explicit adaptation. This is not production-default, commercial-clearance, CPU-speed, or OCR-quality approval. [Native configuration](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/models/paddleocr_vl/configuration_paddleocr_vl.py), [native model](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/models/paddleocr_vl/modeling_paddleocr_vl.py), [released preprocessor metadata](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/preprocessor_config.json).

The reviewed release tag resolves to Transformers commit `08810b1e278938278c50153ee1edfd7a20a759da`; native source links below use that immutable commit. The manga repository/configuration revision is separately pinned. [Transformers release](https://github.com/huggingface/transformers/releases/tag/v5.0.0), [manga configuration](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/config.json).

## Explicit processor and tokenizer contract

Instantiate `PaddleOCRVLConfig`, `PaddleOCRVLForConditionalGeneration`, `PaddleOCRVLImageProcessor`, and `PaddleOCRVLProcessor` directly from the official package. Load the config/weights from verified local files with `local_files_only=True` and `use_safetensors=True`; bypass repository `auto_map` entries. Clearing those entries is defense-in-depth, not a substitute for choosing native classes. Do not fetch or import the repository's `configuration_paddleocr_vl.py`, `modeling_paddleocr_vl.py`, `image_processing.py`, or processor Python during inference. The released metadata maps those custom modules. [Released configuration](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/config.json), [preprocessor mapping](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/preprocessor_config.json).

Use the generic `TokenizersBackend` (the 5.0.0 compatibility alias is `PreTrainedTokenizerFast`) with the exact local `tokenizer.json`. Supply the released named special tokens and additional five specials, `model_max_length=131072`, and **`image_token="<|IMAGE_PLACEHOLDER|>"`**. This serialized tokenizer has a space-to-`▁` normalizer, no pre-tokenizer, an identity postprocessor, and replace/byte-fallback/fuse decoding. Generic direct construction preserves that pipeline. Its omitted BOS/EOS/prefix-space options default false, matching the release; explicitly passing BOS/EOS flags causes postprocessor reconstruction, so verify equivalence if doing so. Native Llama defaults instead construct a Metaspace pipeline with prefix-space behavior; do not rely on those defaults as proof of equivalence. [Generic backend](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/tokenization_utils_tokenizers.py), [native Llama tokenizer](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/models/llama/tokenization_llama.py), [serialized tokenizer](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/tokenizer.json), [tokenizer metadata](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/tokenizer_config.json).

The native tokenizer base accepts model-specific named `_token` kwargs and converts old `additional_special_tokens` into its extra-special representation. Its default model inputs are `input_ids` and `attention_mask`, not segment IDs. The native processor reads `tokenizer.image_token` and expands **only that placeholder** into `prod(image_grid_thw)/merge_size²` image tokens. Setting it to the whole start/placeholder/end wrapper would incorrectly repeat wrappers. [Tokenizer base](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/tokenization_utils_base.py), [native processor](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/models/paddleocr_vl/processing_paddleocr_vl.py).

| Token/role | Released ID |
|---|---:|
| `<unk>` / pad | 0 |
| `<s>` / BOS | 1 |
| `</s>` / generation EOS | 2 |
| `<\|begin_of_sentence\|>` / CLS | 100273 |
| `<\|end_of_sentence\|>` / SEP, not generation EOS | 100272 |
| `<\|IMAGE_PLACEHOLDER\|>` | 100295 |
| `<\|IMAGE_START\|>` | 101305 |
| `<\|IMAGE_END\|>` | 101306 |
| `<\|video_pad\|>` / released video token | 101307 |

IDs come from the pinned tokenizer/config, not IDs inferred from the native defaults. The public JSON has 100295 base entries and 1039 added records, including 20 existing-ID overlaps: **101314 distinct IDs, maximum 101313**. Keep the model's **103424 padded vocabulary**; do not resize its embedding/output matrices to that smaller real vocabulary. [Special-token map](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/special_tokens_map.json), [serialized vocabulary](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/tokenizer.json), [model vocabulary](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/config.json).

Use the exact pinned Jinja file. Rendering a single user image plus text `OCR:` with a generation prompt must produce this string; the second line ends with one literal space:

```text
<|begin_of_sentence|>User: <|IMAGE_START|><|IMAGE_PLACEHOLDER|><|IMAGE_END|>OCR:
Assistant: 
```

Native template rendering supplies named tokenizer special tokens, so its placeholder-only `image_token` would override the Jinja wrapper default. Override **template rendering only** with the full wrapper, then process RAM-only RGB PIL pixels and the rendered text separately:

```python
prompt = processor.apply_chat_template(
    [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": "OCR:"}]}],
    tokenize=False, add_generation_prompt=True,
    image_token="<|IMAGE_START|><|IMAGE_PLACEHOLDER|><|IMAGE_END|>",
)
inputs = processor(images=[rgb_pil], text=[prompt], return_tensors="pt",
                   add_special_tokens=False)
```

This separation prevents duplicate BOS/CLS insertion and avoids the processor's optional image-URL fetching route. [Pinned template](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/chat_template.jinja), [native template rendering](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/processing_utils.py).

## Pixels and patches

Pass released values explicitly: all RGB/resize/rescale/normalize flags true; bicubic `resample=3`; scale `1/255`; mean/std `[0.5,0.5,0.5]`; minimum/maximum area **147384 / 2822400**; patch **14**, merge **2**, temporal image patch **1**. The old `size={min_pixels,max_pixels}` is invalid natively. Native `size` uses `shortest_edge`/`longest_edge`, misleadingly representing area bounds here; supplying explicit min/max lets its constructor build the correct native size. The vision config's old temporal value **2 must not replace image preprocessing's 1**. [Released image settings](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/preprocessor_config.json), [native image processor](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/models/paddleocr_vl/image_processing_paddleocr_vl.py).

Static comparison finds the same resize/patch ordering: dimensions grow below factor 28, aspect ratio over 200 is rejected, dimensions round to multiples of 28, and area violations use floor/ceil scaling. Pixels become normalized channels-first patches; reshape/transpose `(0,3,5,2,1,4,6)` yields `[grid_t*grid_h*grid_w,3,14,14]`, with image grid `[1,H/14,W/14]` and placeholder count `grid_h*grid_w/4`. This is source-level agreement, **not measured tensor parity** across PIL/NumPy versions. The slow native PIL/NumPy processor does not require torchvision. [Legacy image implementation](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/image_processing.py), [native resize/patch implementation](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/models/paddleocr_vl/image_processing_paddleocr_vl.py).

## Flat configuration and checkpoint loading

Native config collects flat text keys into `text_config`; the released dimensions remain vocabulary 103424, width 1024, FFN 3072, layers 18, heads 16, KV heads 2, head dimension 128, max positions 131072, epsilon `1e-5`, SiLU, and no projection bias. Vision config remains width 1152, FFN 4304, layers 27, heads 16, patch 14, image reference 384, GELU-tanh, epsilon `1e-6`, spatial merge 2. Legacy RoPE migrates to `text_config.rope_parameters`, retaining theta **500000** and `mrope_section=[16,24,24]`; validation may warn about extra legacy keys without deleting them. [Released flat config](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/config.json), [native config migration](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/models/paddleocr_vl/configuration_paddleocr_vl.py), [RoPE migration](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/modeling_rope_utils.py).

The local preflight emitted `Unrecognized keys in rope_parameters for rope_type=default: {'mrope_section'}`. Generic validation expects only standard default-RoPE keys and logs unknown extras; it does not remove them. Native Paddle attention explicitly indexes this retained section and passes it to its multimodal rotary function. **Do not delete it to silence the warning**; assert the section and theta instead. The warning reflects incomplete generic model-specific validation, not proof of a failed config conversion. Full forward/output parity is still untested. [Generic validation](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/modeling_rope_utils.py#L723), [native section consumption](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/models/paddleocr_vl/modeling_paddleocr_vl.py#L335).

For the conditional-generation class, official conversion is:

| Legacy namespace | Native namespace |
|---|---|
| `visual.*` | `model.visual.*` |
| `mlp_AR.*` | `model.projector.*` |
| old `model.*`, excluding already-native visual/projector/language prefixes | `model.language_model.*` |
| `lm_head.*` | unchanged |

Top-level released `tie_word_embeddings=False` must remain false. Although flat migration leaves the nested text config's tie default true, the generation class's head/embedding tie mapping consults its own top config and is disabled. Do not force the two checkpoint matrices to share storage. [Native checkpoint mapping](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/models/paddleocr_vl/modeling_paddleocr_vl.py), [tie-map gating](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/modeling_utils.py).

Request `output_loading_info=True`; reject missing, unexpected, mismatched, and error entries. Never accept randomized core layers or use `ignore_mismatched_sizes=True` to pass this gate. Caveat: reported loading info is **already filtered** by native exceptions for `packing_position_embedding`, `vision_model.head`, and applicable old `rotary_emb.inv_freq` buffers. Empty returned sets are not an exhaustive raw tensor-key inventory. A verified actual checkpoint load and, if needed, a recorded raw-to-native key/shape audit remain outstanding. No weight bytes/header were inspected here. [Loader exception handling](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/modeling_utils.py).

## CPU, dtype, generation, and dependencies

The release declares BF16. Use explicit `dtype=torch.float32`, `attn_implementation="eager"`, `eval()`, and `torch.inference_mode()` for the baseline; verify all floating parameters and input pixels are FP32 and devices CPU. Native ordinary load supports this, but explicit dtype is important because v5 loading defaults to automatic dtype. Do not enable FlashAttention, quantization, downloaded kernels, or `kernel_config` for this comparator. Upstream metadata reports 958588736 BF16 parameters: FP32 parameter storage alone is approximately **3.83 GB / 3.57 GiB**, excluding load transients, activations, cache, and framework memory. This is arithmetic, not measured peak RAM. [Native model](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/models/paddleocr_vl/modeling_paddleocr_vl.py), [official loader](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/modeling_utils.py), [upstream weight metadata](https://huggingface.co/api/models/jzhang533/PaddleOCR-VL-For-Manga?blobs=true).

Baseline generation: batch one, greedy/no sampling, one beam, bounded new tokens, pad 0, EOS 2, **`use_cache=False`** as released. The local comparator caps at 300 and counts capped sequences without EOS as truncations. Decode only tokens after input length with `skip_special_tokens=True`, `clean_up_tokenization_spaces=False`; do not normalize quotes/ellipses/spacing to improve scores. Native code supports caching and omits repeat vision processing on later cached steps. `use_cache=True` is an explicit experimental variant, not established equivalent output or speed; compare token sequences and latency/RSS on the same crops before using it. [Released generation config](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/generation_config.json), [native generation preparation](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/models/paddleocr_vl/modeling_paddleocr_vl.py).

Official 5.0.0 metadata requires Python **>=3.10**, `huggingface-hub>=1.3.0,<2.0`, `tokenizers>=0.22.0,<=0.23.0`, `safetensors>=0.4.3`, filelock, NumPy>=1.17, packaging>=20, PyYAML>=5.1, regex except 2019.12.17, typer-slim, and tqdm>=4.27. Relevant extras specify torch>=2.2 (and accelerate>=1.1), Pillow>=10.0.1,<=15.0, Jinja2>=3.1 and jmespath>=1.0.1. Accelerate is not necessarily needed for a plain CPU load; torchvision is optional and unnecessary for the selected slow processor. No Paddle/PaddleOCR, sentencepiece conversion, or FlashAttention dependency is needed for the serialized-JSON path. A `--no-deps` runtime overlay still requires checking every actual installed dependency; pinning Transformers/Hub alone does not prove compatibility. [Official PyPI metadata](https://pypi.org/pypi/transformers/5.0.0/json), [package import/version checks](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/utils/import_utils.py).

## Local comparator assessment and remaining gates

The read-only script snapshot implements the important adaptations: official native classes; config auto-map removal; JSON generic tokenizer; placeholder-only named token; wrapper override plus exact prompt assertion; exact pixel bounds; local safetensors FP32/eager load with strict loading-info rejection; separate pinned runtime; no repository Python in its model allowlist; bounded greedy generation; and explicit cache opt-in. Its `processor_upstream_parity=False` is appropriately honest. These are implementation observations, not results of running this review's comparator.

Separately, inspected the main task's [processor-only preflight report](../artifacts/paddle-vl-native-preflight-20261014.json): **13 authored controls passed**, serialized tokenizer core unchanged, exact legacy prompt, expected grids/patch shapes and wrapper/placeholder counts, **0 socket attempts**, and `weights_loaded=false`. This is actual processor execution evidence, not OCR inference, accuracy, latency, or legacy-versus-native pixel equality. Reported physical RAM was 16309932032 bytes (~15.2 GiB), with only ~1.7 GiB available before and ~1.4 GiB after this processor run. The updated comparator checks Windows available physical RAM and rejects a FP32 load below **7 GiB free**; that is a conservative operational guard, not a measured sufficient peak-memory requirement or OOM guarantee. No weight load has been established.

Before reporting a valid comparison:

1. Verify package requirements/import identities and pinned local assets; keep the production environment unchanged and enforce inference network denial, including metadata lookup.
2. Assert migrated dimensions, RoPE values, token IDs/vocabulary capacity, CPU device, and FP32 parameters/pixels; save actual loading diagnostics and document native ignored leftovers.
3. Extend the passed authored prompt/token/geometry preflight to numerical pixel parity and tiny/portrait/landscape/boundary cases. Serialized tokenizer-core equality and mocked tests do not establish full legacy processor/model equivalence.
4. Run a bounded, rights-eligible private holdout only when separately authorized: raw punctuation-aware OCR metrics, cold/warm latency, peak RSS, truncations, and cache variant results. Preserve private crops in RAM and outputs privately. Do not expand the dataset or promote defaults based on public benchmark scores.

For training/benchmark contamination and rights limitations, see the separate [candidate source audit](ocr-candidate-source-audit-20261014.md). This adapter review does not supersede its unresolved commercial provenance caveats.

## Reproducibility ledger

These public text byte lengths/SHA-256 values were computed in RAM during the source audit. Weight bytes were **not** downloaded; their identity is upstream metadata only. All manga text files use the model revision above.

| File | Bytes | SHA-256 |
|---|---:|---|
| `config.json` | 1987 | `928aaf78567a273cb73ede3671253ec4e38eb60c27a30e945bcd13b4131a0147` |
| `preprocessor_config.json` | 687 | `f417a7f977820dfe6828f3ec2e461c027fdb0662f25cae4e841ec1028e0b988a` |
| `generation_config.json` | 133 | `cf202f984e003e92dceaa27e749b60b4e6e1b566a1df8486b5b41adf1d016cea` |
| `chat_template.jinja` | 1566 | `344fea8b69546526a00996468f86f583fd65441582a36f2fa4abc794aa94094c` |
| `tokenizer.json` | 11187679 | `f90f04fd8e5eb6dfa380f37d10c87392de8438dccb6768a2486b5a96ee76dba6` |
| `tokenizer_config.json` | 185545 | `67c651ba09c22151a1fff31e8773a24f7607aef1541aa2f200b48552ed30e894` |
| `special_tokens_map.json` | 1152 | `215bf3a1b155fafe3497f8790bedf280af92d29c2f0286c2f87a5c78baff8f7c` |
| `added_tokens.json` | 25381 | `f59f889088e0fe21c523e7cf121bb6dca3b0bb148cb7159fbb4572c74dfc5644` |

Official wheel identities, independently checked against first-party PyPI JSON:

| Wheel | Bytes | SHA-256 |
|---|---:|---|
| `transformers-5.0.0-py3-none-any.whl` | 10142091 | `587086f249ce64c817213cf36afdb318d087f790723e9b3d4500b97832afd52d` |
| `huggingface_hub-1.3.0-py3-none-any.whl` | 533092 | `763f450169bb05ea3867990e9d3ba9464eb617b874791301dc81be2c6ffb0bf5` |

Sources: [Transformers package metadata](https://pypi.org/pypi/transformers/5.0.0/json), [Hub package metadata](https://pypi.org/pypi/huggingface-hub/1.3.0/json). The model's `model.safetensors` is 1917255968 bytes with upstream SHA-256 `71fcee0e3618582d4c8acc705242aa79b471b6134e7023bf3820642ba638b602`; actual downloaded-byte verification belongs to explicit provisioning, not this source-only review. [Upstream model metadata](https://huggingface.co/api/models/jzhang533/PaddleOCR-VL-For-Manga?blobs=true).

## Follow-up: exact 12 surplus tensors and the image-only route

Source-only follow-up on 2026-10-14: **a narrow, exact key/shape/dtype exception is justified for these 12 tensors on this pinned image-OCR route; blanket name/regex ignores are not.** Independently traced the complete legacy packing/pooling branches and native call path without executing repository Python, loading weight values, or reading private crops. Also read the main task's [metadata-only checkpoint audit](../artifacts/paddle-vl-native-checkpoint-audit-20261014.json): 620 raw versus 608 native tensors, no missing keys, shape mismatches, or mapping collisions, exactly the 12 mapped surplus keys below, and a single raw dtype `BF16`. Its `raw_to_native_shape_gate=false` correctly records the then-unresolved surplus policy; earlier statements above are historical, not a claim that this later audit or actual weight loading had already passed.

### Why packing is not read here

Legacy conditional-generation `forward` constructs image features when `inputs_embeds is None` and `pixel_values is not None`. It casts and unsqueezes the processor's 4-D patch array to 5-D, constructs a non-None list of image-grid tuples, position IDs and cumulative lengths, and explicitly calls `self.visual` with **`interpolate_pos_encoding=True`**. The vision wrapper forwards these values unchanged. In `SiglipVisionEmbeddings.forward`, the only supported input branch is 5-D and requires position IDs. Within it, interpolation is selected when `interpolate_pos_encoding` is truthy **and** `image_grid_thw is not None`; this path reads ordinary `position_embedding.weight` and bilinearly interpolates it for each grid. The sole read of `packing_position_embedding` is the mutually exclusive fallback when either condition fails; non-5-D inputs raise. Thus packing weights are unreachable on the specified successful route—not generally unused for all legacy vision calls. [Legacy OCR call](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/modeling_paddleocr_vl.py#L2350), [wrapper forwarding](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/modeling_paddleocr_vl.py#L1948), [complete embeddings branch](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/modeling_paddleocr_vl.py#L1137).

### Why the 11 pooling tensors are not read here

The legacy transformer creates its pooling head unless `vision_use_head` explicitly disables it. However, every head invocation is inside **`return_pooler_output is True`**: with sample indices it either pads/batches the selected features or pools each list item; without sample indices it pools the full hidden state when `use_head` is true. OCR explicitly passes **`return_pooler_output=False`**, skipping that entire branch. The false path merely slices the post-layernorm encoder state by `cu_seqlens`, returns this list as `last_hidden_state` with `pooler_output=None`, and the OCR caller consumes that list through `mlp_AR` before scattering projected features into image-token positions. `sample_indices` being present does not activate pooling outside the true branch. [All pooling branches](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/modeling_paddleocr_vl.py#L1706), [OCR flags and consumer](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/modeling_paddleocr_vl.py#L2380).

Native 5.0.0 structurally implements the selected route: its embeddings always interpolate the ordinary position table, its vision transformer has no packing table or pooling head and returns post-layernorm `last_hidden_state`, and `get_image_features` projects that state. The native field called `pooler_output` is then assigned **projector features**, not legacy attention-pooling output; the language model consumes those projected image features. Keep ordinary position embeddings, encoder/post-layernorm, and projector tensors strict. [Native embeddings](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/models/paddleocr_vl/modeling_paddleocr_vl.py#L547), [vision output](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/models/paddleocr_vl/modeling_paddleocr_vl.py#L886), [native projector consumer](https://github.com/huggingface/transformers/blob/08810b1e278938278c50153ee1edfd7a20a759da/src/transformers/models/paddleocr_vl/modeling_paddleocr_vl.py#L1206).

### Exact proposed metadata exception

These are **mapped names**, after official `visual.*` → `model.visual.*` conversion; remove the initial `model.` to obtain each raw checkpoint name. Shapes were independently derived from the pinned constructors and vision config (`hidden_size=1152`, `intermediate_size=4304`), not independently re-read from weight headers in this continuation. The existing audit supplies the exact name set and aggregate BF16 dtype, but does not list each surplus shape. Require a per-key header check against this table before declaring the narrowed raw shape gate passed. The pooling constructor uses standard same-width biased `MultiheadAttention`, LayerNorm and the two biased MLP linears. [Legacy packing constructor](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/modeling_paddleocr_vl.py#L1057), [legacy head constructor](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/modeling_paddleocr_vl.py#L1864), [pinned vision dimensions](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga/blob/1e8aa5f1dd90cc86fe9137c9c0b26ebde613cfe8/config.json), [official PyTorch projection construction](https://github.com/pytorch/pytorch/blob/5c4886908584029761b579af026dcfb627c84070/torch/nn/modules/activation.py#L1163).

| Exact mapped surplus key | Expected shape | Required on-disk dtype |
|---|---|---|
| `model.visual.vision_model.embeddings.packing_position_embedding.weight` | `[32768,1152]` | BF16 |
| `model.visual.vision_model.head.attention.in_proj_bias` | `[3456]` | BF16 |
| `model.visual.vision_model.head.attention.in_proj_weight` | `[3456,1152]` | BF16 |
| `model.visual.vision_model.head.attention.out_proj.bias` | `[1152]` | BF16 |
| `model.visual.vision_model.head.attention.out_proj.weight` | `[1152,1152]` | BF16 |
| `model.visual.vision_model.head.layernorm.bias` | `[1152]` | BF16 |
| `model.visual.vision_model.head.layernorm.weight` | `[1152]` | BF16 |
| `model.visual.vision_model.head.mlp.fc1.bias` | `[4304]` | BF16 |
| `model.visual.vision_model.head.mlp.fc1.weight` | `[4304,1152]` | BF16 |
| `model.visual.vision_model.head.mlp.fc2.bias` | `[1152]` | BF16 |
| `model.visual.vision_model.head.mlp.fc2.weight` | `[1152,4304]` | BF16 |
| `model.visual.vision_model.head.probe` | `[1,1,1152]` | BF16 |

The source-derived totals are 37748736 packing plus 15238352 pooling parameters = **52987088**, exactly the audit's `958588736 - 905601648` difference. This is a useful inventory cross-check, not a substitute for checking all 12 individual shapes. Native FP32 parameter storage would correspond to the retained 905601648 parameters (~3.62 GB / 3.37 GiB), not the full legacy count; actual loading can still incur transient storage for raw surplus tensors, so do not weaken the existing RAM guard from this arithmetic alone.

Acceptance should require the pinned file hash/revision and native version, exactly this surplus set with these shapes/BF16 dtype, zero missing/mismatched/colliding core keys, and independently strict actual loader diagnostics. Reject any new key, unexpected dtype/shape, duplicated mapping, or missing ordinary position/encoder/projector weight. Native's broad built-in ignore patterns alone cannot enforce this inventory. This exception does not authorize changing the checkpoint, training/pooling use, legacy packing fallback, video/general-batch routes, hooks/custom code, or production defaults. Unreachable surplus values establish a scoped loading-policy rationale; they do **not** establish numerical forward parity, a successful FP32 weight load, OCR accuracy, or latency.
