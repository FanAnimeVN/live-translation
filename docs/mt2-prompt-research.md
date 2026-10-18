# Hy-MT2-1.8B prompt and CPU deployment notes

Checked: **2026-10-13**. Scope: Japanese → Vietnamese, first-party Tencent GitHub/Hugging Face documentation and source. This is source research, not a model-quality or latency benchmark. No inference, model download or cloud translation request was performed.

## 1. Official prompt variants

The following English instruction strings are Tencent's published examples, with `target_lang` set to **Vietnamese**. Line breaks reproduce the table's `<br>` boundaries; placeholders are input data, not literal text to send. Use full language names (`Japanese`, `Vietnamese`) when an instruction names a language; the card does not recommend language codes in prompts. [Tencent 1.8B prompt table](https://huggingface.co/tencent/Hy-MT2-1.8B#hy-mt2-translation-task-instruction-examples-chinese-english-comparison)

### Plain

```text
Translate the following text into Vietnamese. Note that you should only output the translated result without any additional explanation:
{source_text}
```

### Context

```text
[Background Information]
{background_text}
Please translate the following text into Vietnamese, taking the provided background information into consideration.
[Source Text]
{source_text}
```

The card labels this row **Structured Data 2**, although its content is a context translation template. This variant contains no explicit JSON-output instruction or output-only instruction. [Tencent prompt table](https://huggingface.co/tencent/Hy-MT2-1.8B#hy-mt2-translation-task-instruction-examples-chinese-english-comparison)

### Terminology

```text
Reference the following translations:
{source_term_1} translates to {target_term_1}
{source_term_2} translates to {target_term_2}
{source_term_3} translates to {target_term_3}
Translate the following text into Vietnamese. Note that you must ONLY output the translated result without any additional explanation:
{source_text}
```

The original table uses `{text}` on both sides of each mapping; the placeholder names above distinguish the source and target values. Capitalization (`must ONLY`) and instruction wording are preserved. These are separate published variants; merging glossary, context, role rules and JSON instructions is an application adaptation. [Tencent prompt table](https://huggingface.co/tencent/Hy-MT2-1.8B#hy-mt2-translation-task-instruction-examples-chinese-english-comparison)

## 2. What is documented about JSON batching

**Structured translation is documented.** Tencent's Structured Data 1 template requires preservation of structure, hierarchy and indentation, translation of visible user-facing values, and preservation of keys/code/placeholders. Calling translation of JSON values wholly unsupported would be inaccurate. [Tencent structured prompt](https://github.com/Tencent-Hunyuan/Hy-MT2#hy-mt2-translation-task-instruction-examples-chinese-english-comparison)

The official evaluator explicitly parses JSON and recursively checks object keys, value types and array lengths. It does **not** compare the meaning of string values. The benchmark separately uses an LLM judge for background disambiguation. [JSON validator source](https://github.com/Tencent-Hunyuan/Hy-MT2/blob/main/IFMTBench/eval/rule_validators.py), [benchmark criteria](https://github.com/Tencent-Hunyuan/Hy-MT2/tree/main/IFMTBench#constraint-types)

**Research limit:** the consulted sources do not establish a guarantee that arbitrary unrelated manga bubbles in one ID→string object preserve all grammatical roles, directed pronouns, modality and terminology. They do not prescribe the extension's combined context/role/glossary/JSON prompt or JSON-schema constrained decoding. A format pass cannot establish those semantic properties.

## 3. Chat template

The official example sends one user message and calls `apply_chat_template(..., add_generation_prompt=True)`. Tencent specifies no default system prompt. [Inference example](https://huggingface.co/tencent/Hy-MT2-1.8B#inference-and-deployment), [README](https://github.com/Tencent-Hunyuan/Hy-MT2#inference-and-deployment)

For one user message, the published Jinja template renders the following sequence, with no extra newline inserted around the content:

```text
<｜hy_begin▁of▁sentence｜><｜hy_User｜>{prompt}<｜hy_Assistant｜>
```

An optional leading system message follows the beginning token and is terminated by `<｜hy_place▁holder▁no▁3｜>`. Historical assistant messages end with `<｜hy_place▁holder▁no▁2｜>`. With `add_generation_prompt=False`, the template instead appends `<｜hy_place▁holder▁no▁8｜>`. These are Hy tokens, not ChatML. [Exact `chat_template.jinja`](https://huggingface.co/tencent/Hy-MT2-1.8B/blob/main/chat_template.jinja)

**Inference:** check what the installed GGUF/runtime actually renders before blaming a template mismatch. The application supplies a user message and enables `--jinja`; that aligns with the documented interface but does not by itself verify the embedded template. [Current request](../companion/manga_live/providers.py#L115), [server arguments](../companion/manga_live/providers.py#L74)

## 4. Deployment and sampling facts

The current GitHub README states `max_context: 8192` and recommends the following for **1.8B and 7B**. The 30B recommendation is different. [Official deployment settings](https://github.com/Tencent-Hunyuan/Hy-MT2#inference-and-deployment)

| Setting | README recommendation | 1.8B `generation_config.json` | Current local request |
| --- | --- | --- | --- |
| Temperature | 0.7 | 0.7 | 0.2 |
| `top_p` | 0.6 | 0.8 | 0.6 |
| `top_k` | 20 | 20 | 20 |
| Repetition penalty | 1.05 | 1.05 | `repeat_penalty: 1.05` sent |
| Output limit | 4096 | Not set in this file | `min(1400, 50 + 5 × Japanese character count)` for the group |

The persisted generation configuration also sets `do_sample: true`. **README versus file discrepancy:** `top_p` is 0.6 versus 0.8. An explicit benchmark configuration is necessary; do not call both the same default. The current table describes request values, not proof that every runtime parameter was applied. [Official generation configuration](https://huggingface.co/tencent/Hy-MT2-1.8B/blob/main/generation_config.json), [current sampler request](../companion/manga_live/providers.py#L115), [current output budget](../companion/manga_live/providers.py#L192)

The raw model configuration has `max_position_embeddings: 262144`; this differs from the README's deployment context guidance and does not by itself validate using that larger context in this extension. [Model configuration](https://huggingface.co/tencent/Hy-MT2-1.8B/blob/main/config.json)

The first-party GGUF card lists **Q4_K_M ≈1.13 GB**, **Q6_K ≈1.47 GB**, **Q8_0 ≈1.91 GB**. Its CPU completion example uses `--jinja -ngl 0`. Weight-file size is not total runtime RAM. The same README contains a broad STQ-kernel warning and some examples naming the 30B model; the page alone does not establish a missing-kernel defect in an already-running Q6_K deployment. [Tencent GGUF card](https://huggingface.co/tencent/Hy-MT2-1.8B-GGUF#llama_cpp)

Tencent also publishes 2-bit and 1.25-bit variants. The 1.25-bit card advertises 440 MB storage and 1.5× speed improvement; this is a publisher claim, not measured performance on this Windows CPU. No source inspected establishes its Japanese→Vietnamese manga quality relative to Q6_K. [First-party 1.25-bit card](https://huggingface.co/tencent/Hy-MT2-1.8B-1.25Bit-GGUF), [2-bit card](https://huggingface.co/tencent/Hy-MT2-1.8B-2Bit-GGUF)

The local manifest selects Tencent's Q6_K artifact with Q4_K_M as the lightweight option and pins a revision/checksum. This research did not load or hash installed model files. [Manifest](../models.lock.json#L23), [selection code](../companion/manga_live/providers.py#L157)

## 5. Languages and license

Japanese (`ja`) and Vietnamese (`vi`) are explicitly listed. The model introduction describes translation among 33 languages; the displayed table also lists Traditional Chinese and Tibetan/Kazakh/Mongolian/Uyghur/Cantonese. Do not infer a pair-specific quality score from a language-support list or Tencent's aggregate comparisons. [Official supported-language table](https://huggingface.co/tencent/Hy-MT2-1.8B#supported-languages)

The current Hy-MT2 code/model license is **Apache-2.0**, including the first-party 1.8B GGUF LICENSE. This statement concerns these artifacts, not every dependency, third-party quantization or dataset. [Tencent repository license](https://github.com/Tencent-Hunyuan/Hy-MT2/blob/main/LICENSE.txt), [Tencent GGUF license](https://huggingface.co/tencent/Hy-MT2-1.8B-GGUF/blob/main/LICENSE.txt)

## 6. Implications to test, not established causes

- **Prompt composition:** `compact_prompt` combines background, rules and JSON translation. Comparing it with the exact plain/context/terminology variants on the same source can isolate instruction load and source-boundary effects. The published examples do not establish which variant is best for manga. [Current prompt](../companion/manga_live/prompts.py#L42)
- **Semantic versus structural success:** the local compact schema fixes keys and string types, while the semantic guards target causative-passive, negation, requests versus completed events, who waits, directed pronouns, name recipients and counters. A structurally accepted answer can still fail those checks. This is evidence for separate grading, not proof that JSON caused the failures. [Compact schema](../companion/manga_live/prompts.py#L63), [known-error guards](../scripts/semantic_regression.py#L51)
- **Sampling:** temperature 0.2 is an application choice, below Tencent's 0.7 recommendation. A controlled sampler comparison is justified; the documentation does not prove that raising temperature fixes semantics. Keep source, context, model, output format and seed handling fixed while changing this axis.
- **Per-bubble baseline:** one plain or context source per request lets the caller assign its own ID and removes JSON production from that condition. This diagnoses formatting/task-composition effects. It changes model-call count, so compare whole-group completion time and accuracy, not only first output.
- **Quantization and CPU:** sources support CPU deployment, but do not attribute these grammatical errors to CPU execution or quantify Q4_K_M versus Q6_K Japanese→Vietnamese quality. Treat quantization as a separate controlled comparison after prompt/template checks.

Any comparison should record exact prompt, sampler settings, quantization/revision, rendered chat template, calls per group, semantic errors and measured group latency. Exact-template baselines and application-policy variants should be named separately in results.

## 7. First-party 7B GGUF metadata for a possible pilot

**Verified metadata on 2026-10-13; no weights downloaded and no 7B inference performed.** Repository: `tencent/Hy-MT2-7B-GGUF`. The public Hugging Face API resolved `main` to commit **`ab8472660ac61fac25f1af43fac2599d52a8a775`** (`lastModified: 2026-05-26T09:06:21Z`). A second request specifying that exact revision returned the same commit and artifact metadata. [Repository metadata API](https://huggingface.co/api/models/tencent/Hy-MT2-7B-GGUF?blobs=true), [revision-pinned metadata API](https://huggingface.co/api/models/tencent/Hy-MT2-7B-GGUF/revision/ab8472660ac61fac25f1af43fac2599d52a8a775?blobs=true)

| Quantization | Exact filename | Bytes | LFS SHA256 |
| --- | --- | --- | --- |
| Q4_K_M | `Hy-MT2-7B-Q4_K_M.gguf` | `4624648896` | `9f96256500f3fc1ab4d64336b58f52a949a95ad7516b0c229476eef782f9f77b` |
| Q6_K | `HY-MT2-7B-Q6_K.gguf` | `6164482720` | `88ef0aba59952a4cfe4be36cb5baf797dbb370bc60e9dcbd7297036021e52831` |

**Filename case differs:** Q4 uses `Hy-`, Q6 uses `HY-`. The hashes above are `siblings[].lfs.sha256`, not the repository commit or Git pointer `blobId`. For each row, `siblings[].size` equaled `siblings[].lfs.size`. These are publisher-provided checksums; an eventual local download still needs its own hash verification. [Pinned API response](https://huggingface.co/api/models/tencent/Hy-MT2-7B-GGUF/revision/ab8472660ac61fac25f1af43fac2599d52a8a775?blobs=true)

**License:** the pinned API reports `apache-2.0`; `LICENSE.txt` at the same revision explicitly licenses `Hy-MT2-7B-GGUF` under Apache License 2.0. Only the small text license and README were fetched to check these declarations. [Pinned license](https://huggingface.co/tencent/Hy-MT2-7B-GGUF/blob/ab8472660ac61fac25f1af43fac2599d52a8a775/LICENSE.txt)

**Documented CPU deployment:** Tencent's pinned README includes a llama.cpp completion example using `--jinja -ngl 0` and a CPU benchmark command with `-ngl 0`. It repeats the 1.8B/7B sampler recommendation from section 4 and the broad STQ-kernel warning. This confirms a documented CPU path; compatibility with the extension's installed runtime has not been tested. [Pinned README](https://huggingface.co/tencent/Hy-MT2-7B-GGUF/blob/ab8472660ac61fac25f1af43fac2599d52a8a775/README.md), [rendered CPU instructions](https://huggingface.co/tencent/Hy-MT2-7B-GGUF#llama_cpp)

**Limits:** these facts identify reproducible pilot artifacts. They do not predict 7B latency, total RAM use, Japanese→Vietnamese semantic accuracy, or Q4 versus Q6 quality. The byte counts are weight-file sizes. A potential quality mode needs measured comparison with the same authored cases, prompts, context policy and recorded sampler settings.
