# Local vision-language and OCR models for reading Japanese manga text (state as of 2026-10-21)

Conventions in these notes: every number is as reported by the linked source (nothing here was re-measured by us).
"(search snippet)" means the fact came from a search-result summary of that page, not a full read of it.
"Superseded" marks a model that has a newer release from the same family. Inferences are my reasoning, not sourced facts.

## 1. Which open-weight VLMs (≤ ~14B, released or updated mid-2025 → Oct 2026) read Japanese text from images best?

### Takeaway
On published OCR benchmarks the strongest ≤14B general VLMs are Qwen3.5-9B / Qwen3.5-4B (Mar 2026, Apache-2.0), MiniCPM-o 4.5 (9B), Qwen3-VL-8B/4B (Oct 2025, Apache-2.0) and Gemma 4 12B / E4B (2026, Apache-2.0). None of them reliably reads Japanese manga from a whole page: on the MangaOCR benchmark every base VLM scored about 0 Hmean, and on vertical Japanese text base VLMs reach 60–150 % CER. A May 2026 local test also found Qwen3-VL 4B/8B returning blank output, and Gemma 4 E4B and MiniCPM-V inventing dialogue, on manga spreads. Use a VLM as the understanding/translation stage on top of crop-level OCR, not as the OCR engine itself. The one exception is a manga- or vertical-tuned model (see section 2).

### Cited Findings

**Qwen (Alibaba)**
- Qwen3-VL release dates. 235B-A22B: 2025-09-23. 30B-A3B: 2025-10-04, along with FP8 builds. 4B and 8B (Instruct + Thinking): 2025-10-15. 2B and 32B (Instruct + Thinking): 2025-10-21. Technical report arXiv 2511.21631: 2025-11-27. — [QwenLM/Qwen3-VL README](https://github.com/QwenLM/Qwen3-VL)
- The Qwen3-VL README says OCR covers 32 languages, up from 10. The HF card says "32 languages (up from 19)", so the two sources disagree on the old count. Neither mentions Japanese or vertical text explicitly. — [README](https://github.com/QwenLM/Qwen3-VL); [HF Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)
- Qwen3-VL-8B-Instruct: Apache-2.0, 9B params in safetensors (BF16). Recommended VL sampling: temperature 0.7, top_p 0.8, top_k 20, presence_penalty 1.5. — [HF](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)
- Qwen3-VL-8B scores OCRBench 819 in the MiniCPM-o 4.5 comparison table. Same table: MiniCPM-o 4.5 879, Gemini 2.5 Flash 853, GPT-5 807. — [MiniCPM-o 4.5 paper, arXiv 2604.27393](https://arxiv.org/pdf/2604.27393) (search snippet)
- Qwen3.5 small models (0.8B, 2B, 4B, 9B) were released around 2026-03-02 per secondary sources. The HF card citation says February 2026 for the series. — [Medium](https://medium.com/data-science-in-your-pocket/qwen-3-5-small-model-series-released-7a5ed34fcbb3) (secondary); [HF Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)
- Qwen3.5-9B card details:
  - Natively multimodal ("causal LM with vision encoder"), Apache-2.0, 262,144-token native context.
  - Hybrid layout: 8 × (3 Gated DeltaNet + 1 gated attention).
  - Thinks by default. Turn thinking off with `enable_thinking: False`. The Qwen3 `/think` and `/nothink` switches are not supported.
  - — [HF](https://huggingface.co/Qwen/Qwen3.5-9B)
- Qwen3.5-9B / Qwen3.5-4B scores: OCRBench 89.2 / 85.0, CC-OCR 79.3 / 76.7, OmniDocBench 1.5 87.7 / 86.2, CharXiv-RQ 73.0 / 70.8, MMMU 78.4 / 77.6. Comparator Qwen3-VL-30B-A3B: 83.9 / 77.8 / 86.8. — [HF Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)
- The Qwen3.5-2B card lists two numbers per benchmark, probably one per mode: CC-OCR 72.9 / 75.8 and OCRBench 84.5 / 85.4. The comparator Qwen3-VL-4B is listed at 73.8 and 80.8. — [HF Qwen3.5-2B](https://huggingface.co/Qwen/Qwen3.5-2B) (search snippet)
- Qwen3.5-4B (non-thinking) on VJRODa, a set of real vertical-Japanese document images, scores CER 86.1 / BLEU 47.8. A vertical-specialised 3B OCR model scores CER 22.6 / BLEU 79.9 on the same set. — [Sarashina2.2-OCR card](https://huggingface.co/sbintuitions/sarashina2.2-ocr)
- Qwen3.5 0.8B on clean AI-generated Japanese pages, Apple M4 16 GB:
  - CER 0.049 horizontal and 0.058 vertical.
  - Chinese characters and vocabulary mixed into the output, looking like partial translation.
  - About 10.5–11.3 s per page.
  - — [estyle.co.jp, 2026-04-28](https://estyle.co.jp/media/%E3%82%A8%E3%83%B3%E3%82%B8%E3%83%8B%E3%82%A2%E3%83%96%E3%83%AD%E3%82%B0/2973/)
- A hands-on OCR test found Qwen3.5-9B to be the sweet spot. Smaller sizes tend to drift into summarising instead of transcribing. Run conditions: LM Studio with thinking off, temperature 0, pages rendered at 100 DPI, about 1,000 input and 500 output tokens per page, about 3 s per page on a Radeon 9070XT. — [Martin Alderson, 2026-03-13](https://martinalderson.com/posts/how-to-use-qwen-3-5-to-ocr-documents/)
- Qwen3.6 releases found: Qwen3.6-27B (dense, natively multimodal) and Qwen3.6-35B-A3B (MoE). No Qwen3.6 model under 14B was found. — [HF Qwen3.6-27B](https://huggingface.co/Qwen/Qwen3.6-27B); [HF Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)
- A "QwenLM/Qwen3.8" GitHub repo lists the Qwen3.6-27B release on 2026-04-22 and uses "Qwen3.8-27B" as an example id. The naming is unclear. No small Qwen3.7 or Qwen3.8 VL weights were found. — [GitHub QwenLM/Qwen3.8](https://github.com/QwenLM/Qwen3.8) (search snippet)
- Superseded: Qwen2.5-VL (2025), replaced by Qwen3-VL and Qwen3.5.

**Gemma 4 (Google)**
- Family, per the model card:

  | Model | Params | Vision encoder | Context |
  |---|---|---|---|
  | E2B | 5.1B with embeddings (2.3B effective) | ~150M | 128K |
  | E4B | 8B with embeddings (4.5B effective) | ~150M | 128K |
  | 12B "Unified" | 11.95B dense | none (encoder-free) | 256K |
  | 26B A4B (MoE) | 25.2B (3.8B active) | ~550M | 256K |
  | 31B dense | 30.7B | ~550M | 256K |

  - License Apache 2.0.
  - Visual token budgets: 70 / 140 / 280 / 560 / 1120.
  - Claims 35+ languages out of the box (140+ in pretraining). No Japanese-specific claim.
  - — [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)
- OmniDocBench 1.5 edit distance (lower is better): 31B 0.131, 26B-A4B 0.149, 12B 0.164, E4B 0.181, E2B 0.290, Gemma 3 27B 0.365. MMMU-Pro: E2B 44.2 %, E4B 52.6 %, 12B 69.1 %. No OCRBench number is reported. — [model card](https://ai.google.dev/gemma/docs/core/model_card_4)
- Gemma 4 12B, released 2026-06-03:
  - Apache 2.0, dense and encoder-free: raw 48×48 RGB patches are projected by a single matmul of about 35M params, replacing the 550M encoder.
  - Announced as running on about 16 GB VRAM or unified memory, with day-one support in llama.cpp, MLX, LM Studio, vLLM, Ollama, Unsloth and SGLang.
  - — [Google AI Developers on X](https://x.com/googleaidevs/status/2062204432658386950); [Gemma 4 tech report, arXiv 2607.02770](https://arxiv.org/html/2607.02770v1) (search snippet); [HF google/gemma-4-12B](https://huggingface.co/google/gemma-4-12B)
- Higher budgets suit OCR and small text. Unsloth recommends 560 or 1120 for OCR. — [HF gemma-4-12B](https://huggingface.co/google/gemma-4-12B); [Unsloth Gemma 4 guide](https://unsloth.ai/docs/models/gemma-4) (search snippet)
- Ollama hardcodes the Gemma 4 image budget at 280 tokens, and it can't be overridden through the API. In one user's anecdote, E4B misread a licence plate at 280 tokens and read it correctly at 560 in Transformers. — [ollama/ollama issue #15626](https://github.com/ollama/ollama/issues/15626)
- On manga spreads, `gemma4:e4b` in Ollama produced a lot of text that was largely descriptive or hallucinated, and rewrote dialogue into a different scene. — [nullmirror local VLM OCR benchmark, 2026-05-24](https://nullmirror.com/en/blog/2026-05-24-local-vision-language-ocr-benchmark/)
- The predecessor Gemma 3 12B scored 0.0 MangaOCR Hmean and 4.13/10 on MangaVQA. — [MangaLMM paper](https://arxiv.org/html/2505.20298v2)

**MiniCPM (OpenBMB)**
- MiniCPM-V 4.6:
  - About 1.3B (SigLIP2-400M + Qwen3.5-0.8B; the HF metadata shows "1B"), Apache-2.0.
  - LLaVA-UHD v4 with mixed 4x / 16x visual-token compression. `max_slice_nums` defaults to 9; 36 is recommended for images.
  - Runs via Ollama (`minicpm-v-4.6`) and llama.cpp GGUF.
  - Claims Qwen3.5-2B-level OCRBench, but publishes no number.
  - API announced 2026-05-17.
  - — [HF openbmb/MiniCPM-V-4.6](https://huggingface.co/openbmb/MiniCPM-V-4_6). Release on 2026-05-11 per a secondary source: [NYU Shanghai RITS](https://rits.shanghai.nyu.edu/ai/minicpm-v-4-6-a-1-3b-multimodal-model-built-for-phones/)
- MiniCPM-o 4.5 is a 9B omni model. OCRBench 879 (thinking mode), against Qwen3-VL-8B 819. DocVQA 92.3, against Qwen3-VL 95.3. — [arXiv 2604.27393](https://arxiv.org/pdf/2604.27393) (search snippet)
- Superseded: MiniCPM-V 4.5 (8B, 2025). — [arXiv 2509.18154](https://arxiv.org/pdf/2509.18154)
- `minicpm-v:8b` in Ollama (version not stated by the tester) mostly produced panel descriptions and invented dialogue on manga. — [nullmirror](https://nullmirror.com/en/blog/2026-05-24-local-vision-language-ocr-benchmark/)

**InternVL3.5 (OpenGVLab)**
- Paper published 2025-08-25 (arXiv 2508.18265). Apache-2.0.
- The 8B is 0.3B vision + 8.2B LLM. Sizes: 1B, 2B, 4B (4.7B), 8B, 14B (15.1B), 38B, 20B-A4B, 30B-A3B, 241B-A28B.
- Images are cut into 448 px tiles at 256 tokens per tile. The sample code allows up to 12 tiles plus a thumbnail.
- No InternVL4 is announced on the card.
- — [HF OpenGVLab/InternVL3_5-8B](https://huggingface.co/OpenGVLab/InternVL3_5-8B)
- Japanese document QA, judged by gpt-oss-120b, InternVL3_5-4B vs Qwen3-VL-4B: JDocQA 2.626 vs 3.596, JMMMU 0.437 vs 0.493, Heron-Bench 1.893 vs 2.330. — [Sarashina2.2-Vision-3B card](https://huggingface.co/sbintuitions/sarashina2.2-vision-3b)
- The predecessor InternVL3-8B has a synthetic vertical-text CER of 81.0, against 0.462 for horizontal text (1 column). — [arXiv 2511.15059](https://arxiv.org/html/2511.15059v1)

**GLM (Zhipu / Z.ai)**
- GLM-4.6V-Flash:
  - 9B (10B in safetensors), MIT licence. HF tags list Chinese and English only.
  - Recommended sampling: top_p 0.6, top_k 2, temperature 0.8, repetition_penalty 1.1.
  - Known issues: overthinking and repetition.
  - The GLM-4.6V collection was updated 2025-12-08.
  - — [HF zai-org/GLM-4.6V-Flash](https://huggingface.co/zai-org/GLM-4.6V-Flash)
  - Release date conflict: Vercel lists 2025-09-30. — [Vercel](https://vercel.com/ai-gateway/models/glm-4.6v-flash)
  - OCRBench 84.7, third-party figure. — [CometAPI](https://www.cometapi.com/ja/models/zhipuai/glm-4-7-flash-free/) (search snippet)
- Superseded: GLM-4.1V-9B-Thinking (paper arXiv 2507.01006, July 2025), linked from the 4.6V-Flash card. — [HF](https://huggingface.co/zai-org/GLM-4.6V-Flash)

**Other families on the checklist**
- **Kimi-VL-A3B-Thinking-2506:** 16B total / 3B active, 128K context, MIT. OCRBench 869, read from an unlabeled column. The original Kimi-VL-A3B-Thinking is deprecated in favour of 2506. — [MoonshotAI/Kimi-VL](https://github.com/MoonshotAI/Kimi-VL); [Friendli mirror](https://friendli.ai/models/moonshotai/Kimi-VL-A3B-Thinking-2506) (search snippet)
- **Phi-4-Multimodal (5.6B, early 2025):** MangaOCR Hmean 0.0, MangaVQA 3.39/10. — [MangaLMM paper](https://arxiv.org/html/2505.20298v2)
- **Ministral 3 ("2512" builds):**
  - 3B, 8B and 14B, in Base, Instruct and Reasoning variants.
  - 14B is about 13.5B LM + about 0.4B vision encoder; 8B is about 8.4B + 0.4B.
  - Apache 2.0, up to 256K context via YaRN.
  - No OCR benchmark found.
  - — [NVIDIA Megatron-Bridge docs](https://docs.nvidia.com/nemo/megatron-bridge/latest/models/vlm/ministral3.html); [LM Studio](https://lmstudio.ai/models/ministral); [Friendli](https://friendli.ai/models/mistralai/Ministral-3-8B-Instruct-2512-BF16) (search snippets)
  - Mistral Small 3.1 (24B) is over the size limit. — [llama.cpp multimodal docs](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md)
- **SmolVLM2-2.2B:** OCRBench 72.9, DocVQA 79.98, Apache-2.0. — [Roboflow OCR ranking, 2026-08-03](https://roboflow.com/blog/best-open-source-ocr-models)
- **Moondream 3 Preview:** 9B MoE with 2B active, announced 2025-09-18. — [Moondream blog](https://moondream.ai/blog/moondream-3-preview)
  - A secondary source gives the licence as BSL 1.1. Its successor, Moondream 3.1 (9B-A2B), uses a "Moondream License". — [moondream.ai](https://moondream.ai/models/moondream_3-1_9B_A2B) (search snippet)
- **LFM2.5-VL-1.6B (Liquid AI):** released 2026-01-05 per a secondary source. Licensed under LFM Open License 1.0 (also secondary). SigLIP2 NaFlex 400M encoder. Claims improved OCR. Supports llama.cpp, vLLM and SGLang. — [HF LiquidAI/LFM2.5-VL-1.6B](https://huggingface.co/LiquidAI/LFM2.5-VL-1.6B); [Vultr](https://docs.vultr.com/models/liquid-ai-lfm25-vl/lfm2.5-vl-1.6b) (search snippets)
- **Llama 4:** the smallest vision model in the llama.cpp docs is Llama-4-Scout-17B-16E (109B total). There is no small variant. — [llama.cpp multimodal docs](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md)

**Japanese-made VLMs**
- **Sarashina2.2-Vision-3B (SB Intuitions):**
  - About 3.8B: SigLIP so400m-patch14-384 + Sarashina2.2-3B-Instruct. MIT licence. Transformers 4.57.1, with `trust_remote_code`.
  - Japanese scores (Sarashina vs Qwen3-VL-4B): JDocQA 3.327 vs 3.596, JMMMU 0.486 vs 0.493, Heron-Bench 3.214 vs 2.330, BusinessSlideVQA 3.932 vs 4.105.
  - DocVQA 0.831, against 0.948 for Qwen3-VL-4B.
  - — [HF](https://huggingface.co/sbintuitions/sarashina2.2-vision-3b)
- **Sarashina2-Vision-8B:** MangaOCR 0.0, MangaVQA 4.45. **Heron-NVILA-Lite-15B:** 0.0 and 3.76. — [MangaLMM paper](https://arxiv.org/html/2505.20298v2)
- **Stockmark-2-VL-100B-beta:** 96.5B, too large. — [Sarashina2.2-Vision card](https://huggingface.co/sbintuitions/sarashina2.2-vision-3b)
- **KARAKURI VL 32B Instruct 2507:** VJRODa CER 280. — [Sarashina2.2-OCR card](https://huggingface.co/sbintuitions/sarashina2.2-ocr)
- **LLM-jp:** published the JSSODa synthetic vertical-OCR dataset and the VJRODa evaluation set (LREC 2026) rather than a small VLM. — [llm-jp/eval_vertical_ja](https://github.com/llm-jp/eval_vertical_ja)

**Whole-page manga evidence**
- nullmirror, 2026-05-24. Setup: Mac mini M4 Pro 64 GB, Ollama, two manga spreads with vertical bubbles.
  - `qwen2.5vl:7b` gave the best first-spread result, but the second spread came back mostly blank.
  - `qwen3-vl:4b`, `qwen3-vl:8b` and `qwen3-vl:30b` returned blank output.
  - `gemma4:e4b` and `minicpm-v:8b` hallucinated.
  - Document-OCR quality did not predict manga quality. The authors found no strong local VLM-only solution and recommend an OCR + VLM pipeline.
  - — [nullmirror](https://nullmirror.com/en/blog/2026-05-24-local-vision-language-ocr-benchmark/)
- MangaOCR scores 0.0 Hmean for GPT-4o, Gemini 2.5 Flash, Claude Sonnet 4.5, Phi-4-MM, Pangea-7B, LLaVA-OV-1.5-8B, Sarashina2-Vision-8B, Gemma-3-12B and Heron-NVILA-Lite-15B. Qwen2.5-VL-7B scores 0.9.
  - The task requires a bounding box plus text, matched at IoU > 0.5.
  - Base models output mostly meaningless or repeated tokens, with boxes in nonsensical places.
  - — [MangaLMM paper](https://arxiv.org/html/2505.20298v2)
- A 2026 Japanese OCR survey says VLMs are generally less accurate on vertical writing than on horizontal. It recommends YomiToku or PP-OCRv5 for vertical text. — [note.com/daikidomon, 2026-07-20](https://note.com/daikidomon/n/nf4c45dabc7b4)

### Inferences
- Ranking of ≤14B general VLMs for Japanese text reading, from OCR benchmarks plus Japanese document QA. None of these has been measured on manga crops in public.
  1. Qwen3.5-9B
  2. MiniCPM-o 4.5 and Qwen3-VL-8B (about equal)
  3. Qwen3.5-4B
  4. Gemma 4 12B
  5. Gemma 4 E4B
  6. InternVL3.5-8B
  7. GLM-4.6V-Flash (tagged zh/en)
  8. Everything else (SmolVLM2, Moondream, LFM2.5-VL, Phi-4-MM, Ministral 3)

  The Japanese-made Sarashina2.2-Vision-3B is close to Qwen3-VL-4B on Japanese document QA but weaker on English DocVQA.
- The 0.0 MangaOCR Hmean partly reflects a localisation-format failure (boxes must hit IoU > 0.5), not only failure to read. Even so, combined with vertical CER of 60–150 and the nullmirror failures, the evidence is consistent: a base VLM is not a reliable whole-page OCR engine for manga.
- Our own Gemma 4 E2B hallucination result fits these findings. If it was run through Ollama, the hardcoded 280-token budget probably made it worse. At 280 tokens, an 800×1100 page gets about one token per 56×56 px, which is coarser than most bubble glyphs. Before ruling out the family, retest E4B and 12B at a 1120 budget via Transformers.
- Qwen3.5 has a reported Chinese-leakage risk in Japanese OCR. Add a script check to evaluation: count simplified-only Chinese characters and check the kana ratio.

### Gaps
- No public benchmark puts Qwen3.5, Qwen3-VL, Gemma 4 or MiniCPM-o on manga bubble crops. JMangaBench_Read contains no general VLMs. This has to be measured on our 25-page set.
- Not verified:
  - the release date of Gemma 4 E2B, E4B, 26B and 31B (only the 12B's 2026-06-03 date was confirmed);
  - the Qwen3.5 vision-encoder size and patch geometry;
  - the MiniCPM-o 4.5 and MiniCPM-V 4.5 licence terms;
  - the Ministral 3 official cards (only mirrors were seen).
- No small VLM from Sakana AI, PLaMo (PFN) or Stockmark at ≤14B was found.
- The cause of Qwen3-VL's blank output on manga in Ollama is unknown (runtime, thinking mode or image handling). Retest in Transformers or vLLM.

## 2. Dedicated OCR models: which handle vertical Japanese manga text well, what data are they trained on, and what licence terms follow?

### Takeaway
For speech bubbles, small crop-level manga OCR models clearly beat everything else locally:
- **manga-ocr-base-CPT-flex** (111M, composite 97.47) and **manga-ocr-nar-small** (54M, 97.29). Both are non-commercial (CC BY-NC-SA) and trained on AnimeText plus synthetic data, not Manga109.
- **PaddleOCR-VL-For-Manga** (1B, 95.04; Apache-2.0 weights, trained on Manga109-s).
- **kha-white/manga-ocr** (Apache-2.0, Manga109-s; baseline 90.27).

For long vertical narration and document-like text, Sarashina2.2-OCR (MIT) has the best published real-world vertical score. HunyuanOCR, Chandra, GLM-OCR and PP-OCRv5 also read vertical text, with caveats. DeepSeek-OCR, LightOnOCR and GOT-OCR are poor fits.

Correction to our assumption: only the full Manga109 is academic-only. **Manga109-s (87 books) allows companies to use experiment results, including published pre-trained models, commercially** if the Manga109-s use is credited, per its HF terms page.

### Cited Findings

**Manga-specialised crop OCR**
- **kha-white/manga-ocr:**
  - A Transformers VisionEncoderDecoder that reads crops.
  - Handles vertical and horizontal text, furigana, text over images, many fonts, and multi-line bubbles in one pass.
  - Handwriting is probably not supported. Errors rise on long text.
  - It always outputs text, even on empty crops, which can produce invented sentences.
  - Acknowledges Manga109-s and CC-100, and ships a synthetic-data pipeline.
  - — [manga-ocr README](https://cdn.jsdelivr.net/gh/kha-white/manga-ocr@master/README.md)
  - Base weights `kha-white/manga-ocr-base` are Apache-2.0. — [manga-ocr-base-CPT-flex card](https://huggingface.co/muscgab/manga-ocr-base-CPT-flex)
- **muscgab/manga-ocr-base-CPT-flex:**
  - 111M: ViT-B/16 + 2-layer BERT decoder, autoregressive, 6,817-character vocabulary.
  - Keeps the crop's aspect ratio, up to 196 patches of 16 px.
  - Labels of 1–64 characters; boxes over 32 characters are clearly weaker.
  - Training: 4,471,985 crops (1.80M synthetic printed, 1.67M synthetic handwriting, 1.01M AnimeText-OCR under CC BY-NC-SA 4.0). Manga109-s is not in the training data.
  - Weights CC BY-NC-SA 4.0 (commercial use needs permission); code Apache-2.0.
  - — [HF](https://huggingface.co/muscgab/manga-ocr-base-CPT-flex)
- **muscgab/manga-ocr-nar-small:**
  - 54.2M, non-autoregressive: MonkeyOCRv2-S encoder (28.5M) + 4-layer decoder, up to 65 output positions.
  - Runs on ONNX for CPU, CoreML for macOS 15+, or PyTorch.
  - CPU speed: 58.2 ms per crop, fp32, 8 threads on a Xeon Gold 6148.
  - Onomatopoeia is not a target.
  - CER 1.24 % on printed text vs 4.14 % on non-printed.
  - Weights CC BY-NC-SA 4.0.
  - — [HF](https://huggingface.co/muscgab/manga-ocr-nar-small)
  - A distilled 30M int8 CPU variant scores composite 96.40. — [JMangaBench_Read](https://github.com/muscgab/JMangaBench_Read)
- **genshiai-daichi/baberu-ocr (v1.1 and v1.2, both dated 2026-10):**
  - 115M: DINOv2 + 6-layer decoder. Reads Japanese, Chinese and English.
  - ONNX builds of 122–243 MB. Weights and code Apache-2.0.
  - v1.1 labels were distilled from manga-ocr (Japanese) and PaddleOCR-VL (Chinese/English).
  - v1.2 adds Manga109-s human labels: 74 of 87 titles, about 105k dialogue and 37k sound-effect boxes.
  - The 224×224 input garbles bubbles over about 190 characters. It also confuses dakuten.
  - — [HF](https://huggingface.co/genshiai-daichi/baberu-ocr)
- **jzhang533/PaddleOCR-VL-For-Manga:**
  - About 1B (959M), Apache-2.0, fine-tuned from PaddleOCR-VL.
  - Training: about 0.1M Manga109-s crops (90/10 split) + 1.5M synthetic samples.
  - 70 % full-sentence accuracy, against 27 % for the base model.
  - Trained on crops. Errors: full-width vs half-width characters and CJK radicals.
  - — [HF](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga)
- **Hayai v2.5 Nova (157M):** composite 96.64 (p384). — [JMangaBench_Read](https://github.com/muscgab/JMangaBench_Read). A search summary says it is trained on Manga109-s. The repo id and licence were not verified.
- **gigass03/PaddleOCR-VL-1.6-Manga-Finetuned:** Apache-2.0, tagged with the datasets `hal-utokyo/Manga109-s` and `jzhang533/manga-synthetic`. — [mixpeek listing](https://mixpeek.com/model/gigass03/PaddleOCR-VL-1.6-Manga-Finetuned) (secondary, unverified)

**General document OCR models that can read Japanese**
- **PaddleOCR-VL-1.6:**
  - Released 2026-05-28; tech report 2026-06-03. 0.9B (1.0B in safetensors), Apache-2.0.
  - Upgrades 1.5 in tables, rare and ancient Chinese, seals, spotting and charts.
  - OmniDocBench v1.6: 96.33.
  - Pixel caps in the Transformers example: 2048×28×28 for spotting (images under 1500 px are upscaled 2×), 1280×28×28 for other tasks.
  - vLLM supported; 22 community quantizations.
  - — [HF](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6)
  - Covers 109 languages, including Japanese. — [Roboflow](https://roboflow.com/blog/best-open-source-ocr-models)
- **Base PaddleOCR-VL (0.9B):**
  - Manga109 held-out dialogue: lCER 0.044 and exact match 0.815, against manga-ocr's 0.047 and 0.799. — [Baberu card](https://huggingface.co/genshiai-daichi/baberu-ocr)
  - Japanese rated ◯ and vertical △; it failed on some vertical text. — [LayerX, 2025-12-01](https://tech.layerx.co.jp/entry/2025/12/01/161913)
  - Version 1.5 scored F1 0.895 on a horizontal invoice. It dropped the quantity and price columns but showed almost no hallucination. — [Zenn EpicAI, 2026-03-10](https://zenn.dev/epicai_techblog/articles/a28272a83c24d0)
  - Superseded by 1.6.
- **PP-OCRv5 (classic det+rec):**
  - Official accuracy, as quoted by a third party: Japanese 0.7372 (v4: 0.4623), vertical 0.9314 (v4: 0.5455). — [aimangatranslator blog](https://aimangatranslator.app/blog/manga-ocr-engine-comparison)
  - Vertical rated ◎, but it substituted Chinese characters. — [LayerX](https://tech.layerx.co.jp/entry/2025/12/01/161913)
  - F1 0.947 on the invoice, with traditional and simplified characters mixed in. — [Zenn](https://zenn.dev/epicai_techblog/articles/a28272a83c24d0)
  - Successor PP-OCRv6: 1.5M–34.5M params, 50 languages including Japanese, Apache-2.0. — [Roboflow](https://roboflow.com/blog/best-open-source-ocr-models)
- **GLM-OCR (zai-org/GLM-OCR):**
  - 0.9B: CogViT 0.4B + GLM-0.5B, multi-token-prediction decoding.
  - Weights MIT; PP-DocLayoutV3 (Apache-2.0) recommended for full pages. HF tags list 8 languages.
  - OmniDocBench v1.5: 94.62. Tech report 2026-03-11.
  - — [HF](https://huggingface.co/zai-org/GLM-OCR); [lilting.ch](https://lilting.ch/articles/glm-ocr-document-parsing-layout)
  - The 8 languages include Japanese. — [Roboflow](https://roboflow.com/blog/best-open-source-ocr-models)
  - Synthetic Japanese CER: 0.0028 horizontal, 0.0071 vertical. About 27 s per page on an M4 16 GB. — [estyle](https://estyle.co.jp/media/%E3%82%A8%E3%83%B3%E3%82%B8%E3%83%8B%E3%82%A2%E3%83%96%E3%83%AD%E3%82%B0/2973/)
  - Best of 7 on the Japanese invoice (F1 0.966), with occasional simplified characters. — [Zenn](https://zenn.dev/epicai_techblog/articles/a28272a83c24d0)
- **HunyuanOCR (tencent/HunyuanOCR, about 1B):**
  - The repo now hosts v1.5 (paper 2026-07-06) under the Tencent Hunyuan Community License.
  - Tasks: spotting, parsing and translation. Recommended settings: temperature 0, repetition_penalty 1.08. Images up to 4K.
  - Needs vLLM ≥ 0.25.1 and CUDA 13 for the unified environment. A llama.cpp GGUF exists for the base model only.
  - — [HF](https://huggingface.co/tencent/HunyuanOCR)
  - v1.0 test: Japanese ◎ and vertical ◎. It read arched text mostly correctly with no Chinese substitution, but its bounding boxes were unreliable. — [LayerX](https://tech.layerx.co.jp/entry/2025/12/01/161913)
- **Sarashina2.2-OCR (sbintuitions):**
  - 3B (4B in safetensors): SigLIP2 + Sarashina2.2-3B-Instruct. MIT.
  - Converts vertical Japanese to Markdown in natural reading order.
  - VJRODa: CER 22.6 / BLEU 79.9, the best listed. Others: dots.ocr 40.1, LightOnOCR-2-1B 158, gpt-5-mini 72.4, Qwen3.5-4B 86.1.
  - Recommended input about 2.5 MP; temperature 0, repetition_penalty 1.2.
  - — [HF](https://huggingface.co/sbintuitions/sarashina2.2-ocr)
- **Chandra OCR 2 (datalab-to/chandra-ocr-2):**
  - Modified OpenRAIL-M licence that restricts commercial use. olmOCR-bench 85.8 %.
  - — [Roboflow](https://roboflow.com/blog/best-open-source-ocr-models)
  - Chandra v1 rated Japanese ◎ and vertical ◎. — [LayerX](https://tech.layerx.co.jp/entry/2025/12/01/161913)
- **dots.mocr (dots-studio/dots.mocr, about 3B):** MIT plus additional terms. olmOCR-bench 83.9 %. — [Roboflow](https://roboflow.com/blog/best-open-source-ocr-models)
  - Its predecessor dots.ocr scored VJRODa CER 40.1. — [Sarashina2.2-OCR card](https://huggingface.co/sbintuitions/sarashina2.2-ocr)
- **DeepSeek-OCR (3B, 6.7 GB):**
  - Synthetic vertical CER 4.02 with output loops (24.5 s per page vs 8.9 s horizontal). — [estyle](https://estyle.co.jp/media/%E3%82%A8%E3%83%B3%E3%82%B8%E3%83%8B%E3%82%A2%E3%83%96%E3%83%AD%E3%82%B0/2973/)
  - Native mode invented and repeated text; Gundam mode skipped vertical text. — [LayerX](https://tech.layerx.co.jp/entry/2025/12/01/161913)
  - Blank files through Ollama. — [nullmirror](https://nullmirror.com/en/blog/2026-05-24-local-vision-language-ocr-benchmark/)
  - DeepSeek-OCR-2 exists and is recommended for bulk PDFs. — [lilting.ch](https://lilting.ch/articles/glm-ocr-document-parsing-layout)
- **Other document OCR:**
  - MinerU2.5-Pro: 1.2B, Apache-2.0 with extra terms, OmniDocBench v1.6 95.75. — [Roboflow](https://roboflow.com/blog/best-open-source-ocr-models)
  - LightOnOCR-2-1B: VJRODa CER 158. — [Sarashina2.2-OCR card](https://huggingface.co/sbintuitions/sarashina2.2-ocr)
  - GOT-OCR 2.0 (superseded, 2024): invoice F1 0.837, with simplified-Chinese-like errors. — [Zenn](https://zenn.dev/epicai_techblog/articles/a28272a83c24d0)
  - Florence-2 (0.23B / 0.77B, MIT, 2024): no Japanese claims. — [Roboflow](https://roboflow.com/blog/best-open-source-ocr-models)
- **NDLOCR-Lite (National Diet Library):**
  - About 146 MB of ONNX models, CPU-only.
  - Synthetic Japanese CER: 0.0013 horizontal, 0.0008 vertical. About 1 s per page on an M4.
  - It is built for printed books and documents, not manga.
  - — [estyle](https://estyle.co.jp/media/%E3%82%A8%E3%83%B3%E3%82%B8%E3%83%8B%E3%82%A2%E3%83%96%E3%83%AD%E3%82%B0/2973/)
- **YomiToku:** supports vertical text. Licence CC BY-NC-SA, so commercial use needs a paid licence. — [note.com/daikidomon](https://note.com/daikidomon/n/nf4c45dabc7b4)

**Dataset terms that matter for the paid tier**
- **Full Manga109 (109 volumes):** academic purposes only; the data must not be passed to third parties. — [V7 dataset page](https://www.v7labs.com/open-datasets/manga109) (secondary)
- **Manga109-s (87 books; current release "Manga109-s-v2026"):**
  - Available to companies for machine-learning experiments.
  - Results, including published pre-trained models, may be used commercially if the use of Manga109-s is clearly credited.
  - Redistributing the dataset is forbidden, and so is selling manga images together with results.
  - Manga109Dialog is not included.
  - — [HF hal-utokyo/Manga109-s](https://huggingface.co/datasets/hal-utokyo/Manga109-s)
- **MangaOCR / MangaLMM:**
  - Built from the full Manga109 (109 volumes) plus the COO onomatopoeia dataset. — [MangaLMM paper](https://arxiv.org/html/2505.20298v2)
  - Code is MIT. Weights are at `hal-utokyo/MangaLMM`, with no weight licence stated. Manga109 may not be redistributed. — [GitHub manga109/MangaLMM](https://github.com/manga109/MangaLMM)
- **AnimeText-OCR:** CC BY-NC-SA 4.0. It is used by CPT-flex and the NAR models. — [HF](https://huggingface.co/muscgab/manga-ocr-base-CPT-flex)
- **JMangaBench_Read data and code:** CC BY-NC-SA 4.0. — [GitHub](https://github.com/muscgab/JMangaBench_Read)

### Inferences
- Licence and training-data implications:

  | Model | Weights licence | Training data | Paid-tier implication |
  |---|---|---|---|
  | kha-white/manga-ocr | Apache-2.0 | Manga109-s | Commercial use of results allowed with credit, per the HF terms page (legal review advised) |
  | PaddleOCR-VL-For-Manga | Apache-2.0 | Manga109-s | Same as above |
  | Baberu v1.2 | Apache-2.0 | Manga109-s | Same as above |
  | Hayai (if confirmed) | not verified | Manga109-s (reported) | Same as above |
  | Baberu v1.1 | Apache-2.0 | Distilled from manga-ocr outputs | Indirect Manga109-s lineage |
  | manga-ocr-base-CPT-flex | CC BY-NC-SA 4.0 | AnimeText-OCR (NC) + synthetic | Non-commercial only; fine for a free, user-downloaded local mode; paid tier needs the author's permission |
  | manga-ocr-nar-small | CC BY-NC-SA 4.0 | AnimeText-OCR (NC) + synthetic | Same as above |
  | MangaLMM | none stated | Full Manga109 | Academic-only; research reference |
  | PaddleOCR-VL-1.6, GLM-OCR, Sarashina2.2-OCR, Qwen, Gemma | Apache / MIT | General (no manga-specific data disclosed) | Cleanest licences for a commercial tier |

- Best local OCR plan for bubbles: use our existing balloon/text detector to make crops, then a crop OCR model.
  - Composite score order on JMangaBench: CPT-flex ≈ NAR-small > Hayai > PaddleOCR-VL-For-Manga > Baberu > original manga-ocr.
  - SFX and handwritten text are the weak spot for all of them. Baberu v1.2 reports the best SFX lCER (0.117) on Manga109 held-out titles.
- For long vertical narration boxes and signs, also test Sarashina2.2-OCR, HunyuanOCR and PaddleOCR-VL-1.6. Never use DeepSeek-OCR v1 on vertical text.

### Gaps
- Not verified:
  - Hayai's repo id, licence and training data;
  - Chandra OCR 2's parameter count;
  - the NDLOCR-Lite licence;
  - the HunyuanOCR licence details (any territory exclusions).
- No vertical-manga numbers were found for olmOCR 2, Nanonets-OCR2, MinerU, DeepSeek-OCR-2 or dots.mocr.
- The full text of the Manga109-s agreement (beyond the HF page summary) was not read. manga109.org failed with a TLS-certificate mismatch.

## 3. Evidence of Japanese / manga OCR quality: benchmarks (metric, number, source)

### Takeaway
The most manga-relevant public numbers are:
- **JMangaBench_Read** (Oct 2026, 7,789 bubble crops, composite / CER / exact match);
- **Manga109 held-out lCER** reported by the Baberu card;
- **MangaOCR** (MangaLMM, page-level detection + recognition Hmean);
- **VJRODa / JSSODa** (real and synthetic vertical Japanese, CER).

Generic OCRBench, CC-OCR and OmniDocBench scores rank the general VLMs but do not predict manga quality.

### Cited Findings

**JMangaBench_Read v1.3.2 (2026-10-20)**
- Set: 7,789 bubble and text crops from 1,847 pages by 1,847 artists, posted 2025-10-01 to 2026-10-01.
- Labels: three LLM readers plus human review, with 1,266 boxes human-confirmed. Sound effects are excluded from the main set; a separate set has 380 SFX boxes.
- Metric: composite = 100 × mean of (printed score, non-printed score), where each box scores 1 − edit distance / max length.
- Speeds measured on an RTX 2080 Ti in fp16.
- — [GitHub](https://github.com/muscgab/JMangaBench_Read)

| Model | Params | Composite | CER % | EM % | ms per crop (batch 1) |
|---|---|---|---|---|---|
| manga-ocr-base-CPT-flex | 111M | 97.47 | 1.50 | 91.71 | 11.0 |
| manga-ocr-nar-small | 54M | 97.29 | 1.71 | 91.36 | 9.1 |
| Hayai v2.5 Nova p384 | 157M | 96.64 | 2.37 | 88.20 | 54.0 |
| manga-ocr-nar-small-distil | 30M | 96.40 | 2.29 | 89.09 | — |
| PaddleOCR-VL-For-Manga | 959M | 95.04 | 1.99 | 87.91 | 366.6 |
| baberuOCR v1.1 | 113M | 93.38 | 3.62 | 81.90 | — |
| original mangaOCR | 111M | 90.27 | 4.81 | 78.51 | 84.9 |

- Unranked LLM references: Claude Opus 5.5 at composite 98.05 / CER 0.59; GPT-6 Astra at 99.47. These same LLM readers produced the labels, so their scores are inflated. — [GitHub](https://github.com/muscgab/JMangaBench_Read)
- Version note: CPT-flex scores 97.45 / 1.53 / 91.42 on v1.3 and 97.47 on v1.3.2. The benchmark author is also the CPT-flex author, and parts of the benchmark were used during development. — [CPT-flex card](https://huggingface.co/muscgab/manga-ocr-base-CPT-flex)

**Manga109 held-out titles (13 Manga109-s titles, from the Baberu card), lCER / exact match**
- Dialogue: Baberu v1.2 0.028 / 0.848, PaddleOCR-VL 0.9B 0.044 / 0.815, manga-ocr 0.047 / 0.799.
- Sound effects: Baberu v1.2 0.117 / 0.784, manga-ocr 0.631 / 0.229.
- — [Baberu card](https://huggingface.co/genshiai-daichi/baberu-ocr)
- On the same card's JMangaBench run: Baberu v1.2 scores composite 94.94 and CER 3.04; its handwritten score is 67.3, against 83.1 for CPT-flex. — [Baberu card](https://huggingface.co/genshiai-daichi/baberu-ocr)

**Manga109-s crop accuracy (sentence level)**
- PaddleOCR-VL-For-Manga reaches 70 % full-sentence accuracy; base PaddleOCR-VL reaches 27 %. — [HF](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga)

**MangaOCR / MangaVQA (MangaLMM; arXiv 2505.20298, EACL 2026 Findings)**
- Test set: 1,166 Manga109 two-page spreads (1654×1170) with about 25.6k text instances, including onomatopoeia.
- MangaLMM (Qwen2.5-VL-7B fine-tune): end-to-end P/R/Hmean 74.8 / 68.5 / 71.5; detection Hmean 78.6.
- A 3B model fine-tuned on OCR only reaches 73.5 Hmean.
- MangaVQA (LLM judge, out of 10): Gemini 2.5 Flash 7.26, MangaLMM 6.68, GPT-4o 6.00, Claude Sonnet 4.5 5.84, Qwen2.5-VL-7B 5.65, Sarashina2-Vision-8B 4.45, Gemma-3-12B 4.13, Heron-NVILA-Lite-15B 3.76, LLaVA-OV-1.5-8B 3.46, Phi-4-MM 3.39, Pangea-7B 3.23.
- Missed text is mostly onomatopoeia. The model sometimes repeats output, and OCR on 1,166 images takes several hours on an A100.
- — [arXiv HTML v2](https://arxiv.org/html/2505.20298v2); [ACL Anthology](https://preview.aclanthology.org/credits/2026.findings-eacl.284)

**Vertical Japanese (LLM-jp; arXiv 2511.15059, LREC 2026)**
- JSSODa synthetic, 1-column, raw CER (vertical vs horizontal): Qwen2.5-VL-7B 112 vs 7.75, InternVL3-8B 81.0 vs 0.462, Gemma 3 12B 20.3 vs 3.06, GPT-4.1 18.2 vs 1.88, GPT-5 21.3 vs 2.09.
- After fine-tuning on JSSODa, Qwen2.5-VL-7B's vertical CER drops to 0.104.
- VJRODa (real documents) raw CER: Qwen2.5-VL-7B 154, which falls to 65.1 after fine-tuning (BLEU 20.1 → 51.5). Gemma 3 27B 67.9, GPT-5 70.1. No model did well.
- Failure modes: vertical text read in horizontal order, repetition up to the token limit, partial output, and empty output from GPT-5 when reasoning ran out of tokens.
- — [arXiv HTML](https://arxiv.org/html/2511.15059v1); [code + data](https://github.com/llm-jp/eval_vertical_ja)
- VJRODa CER / BLEU: Sarashina2.2-OCR 22.6 / 79.9, dots.ocr 40.1 / 71.5, gpt-5-mini 72.4 / 23.6, Qwen3.5-4B 86.1 / 47.8, LightOnOCR-2-1B 158 / 28.9, KARAKURI VL 32B 280 / 14.1. — [Sarashina2.2-OCR card](https://huggingface.co/sbintuitions/sarashina2.2-ocr)

**Synthetic Japanese pages, Apple M4 16 GB (AI-generated text, about 400 characters per page)**
- CER horizontal / vertical: NDLOCR-Lite 0.0013 / 0.0008, GLM-OCR 0.0028 / 0.0071, Qwen3.5-0.8B 0.0490 / 0.0576, DeepSeek-OCR 0.0023 / 4.0236. — [estyle](https://estyle.co.jp/media/%E3%82%A8%E3%83%B3%E3%82%B8%E3%83%8B%E3%82%A2%E3%83%96%E3%83%AD%E3%82%B0/2973/)

**Japanese invoice, character-level F1 (687 characters)**
- GLM-OCR 0.966, PP-OCRv5 0.947, PaddleOCR-VL 1.5 0.895, EasyOCR 0.866, GOT-OCR 2.0 0.837, Qwen2.5-VL-7B 0.794, Tesseract 0.739. — [Zenn EpicAI](https://zenn.dev/epicai_techblog/articles/a28272a83c24d0)

**General OCR benchmarks**
- Qwen3.5-9B: OCRBench 89.2, CC-OCR 79.3. Qwen3.5-4B: 85.0 and 76.7. — [HF](https://huggingface.co/Qwen/Qwen3.5-9B)
- OCRBench: MiniCPM-o 4.5 879, Qwen3-VL-8B 819. — [arXiv 2604.27393](https://arxiv.org/pdf/2604.27393) (search snippet)
- OCRBench: Kimi-VL-2506 869 (inferred column). — [Friendli](https://friendli.ai/models/moonshotai/Kimi-VL-A3B-Thinking-2506) (search snippet)
- OCRBench: GLM-4.6V-Flash 84.7 (third-party). — [CometAPI](https://www.cometapi.com/ja/models/zhipuai/glm-4-7-flash-free/) (search snippet)
- OCRBench: SmolVLM2 72.9. — [Roboflow](https://roboflow.com/blog/best-open-source-ocr-models)
- OmniDocBench 1.5 edit distance: Gemma 4 E4B 0.181, 12B 0.164. — [Gemma 4 card](https://ai.google.dev/gemma/docs/core/model_card_4)
- OmniDocBench v1.6: PaddleOCR-VL-1.6 96.33. — [HF](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6)
- OmniDocBench v1.5: GLM-OCR 94.62. — [HF](https://huggingface.co/zai-org/GLM-OCR)

**Japanese VLM benchmarks (judge: gpt-oss-120b)**
- JDocQA: Qwen3-VL-4B 3.596, Sarashina2.2-Vision-3B 3.327, Qwen2.5-VL-3B 3.019, InternVL3.5-4B 2.626.
- JMMMU: Qwen3-VL-4B 0.493, Sarashina2.2-Vision-3B 0.486.
- — [HF Sarashina2.2-Vision-3B](https://huggingface.co/sbintuitions/sarashina2.2-vision-3b)

**Handwritten Japanese (NLS, from a 23-model comparison as quoted)**
- Gemini 3.1 Pro 0.924, YomiToku 0.770, GPT-5.4 0.714, PaddleOCR 0.353. — [note.com/daikidomon](https://note.com/daikidomon/n/nf4c45dabc7b4)

### Inferences
- On crops, local OCR comes within about 1 composite point of a frontier LLM reader: CPT-flex 97.47 against Claude Opus 5.5 at 98.05. The remaining local quality gap is detection, reading order, SFX and handwriting, not bubble reading.
- No public benchmark puts Qwen3.5, Qwen3-VL or Gemma 4 on JMangaBench-style crops. Running JMangaBench_Read (CC BY-NC-SA, evaluation use) on our candidates is the quickest apples-to-apples comparison, alongside our private 25-page set.

### Gaps
- No CC-OCR Japanese sub-score was found for any ≤14B model.
- No public JMMMU or JDocQA scores were found for Gemma 4 or Qwen3.5.
- No independent replication of the JMangaBench numbers was found; they are self-reported by the benchmark and model author.
- MangaVQA numbers for Qwen3-VL, Qwen3.5 and Gemma 4 were not found.

## 4. Can small models attribute speakers (which character says which bubble)?

### Takeaway
No open ≤14B VLM has a published, measured speaker-attribution result on Japanese manga.
- MangaLMM covers OCR and VQA only.
- Magi v1/v2/v3 (Oxford) do text-to-character association, character naming and speech-bubble-tail detection. All three are non-commercial / not-for-profit and English-tagged.
- Studies of VLM manga reading report failures in cross-panel cohesion and character consistency.

Speaker attribution in local mode should therefore be geometric (tail + proximity) plus "unknown" by default, with Magi usable only under its non-commercial terms.

### Cited Findings
- **Magi v1** (CVPR 2024): one model detects panels, text blocks and characters, then does character–character and text–character matching (speaker association). — [CVPR 2024 paper](https://openaccess.thecvf.com/content/CVPR2024/papers/Sachdeva_The_Manga_Whisperer_Automatically_Generating_Transcriptions_for_Comics_CVPR_2024_paper.pdf)
  - Known weaknesses: numeric speaker labels instead of names, and frequent misattribution. — [Liner review](https://liner.com/ko/review/manga-whisperer-automatically-generating-transcriptions-for-comics) (search snippet)
  - Licence from an HF mirror: personal, research, non-commercial and not-for-profit use; other uses need a licence from the author. — [masoniis/magi-onnx](https://huggingface.co/masoniis/magi-onnx) (search snippet)
- **Magi v2** ("Tails Tell Tales", arXiv 2408.00298, 2024-08-01):
  - Produces chapter-wide transcripts with character names, using a character bank of images and names.
  - Per-text outputs: OCR, an "essential text" flag, and the associated character.
  - English-tagged. Free for personal, research, non-commercial and not-for-profit use; anything else needs a separate licence.
  - — [HF ragavsachdeva/magiv2](https://huggingface.co/ragavsachdeva/magiv2)
- **Magi v3** ("From Panels to Prose", arXiv 2503.23344, 2025-03-30, ICCV 2025):
  - Florence-2-based, about 0.8B (F16).
  - Detects panels, characters, text and speech-bubble tails; also does OCR and character grounding.
  - English-tagged, same non-commercial licence.
  - — [HF ragavsachdeva/magiv3](https://huggingface.co/ragavsachdeva/magiv3)
- **MangaLMM** covers MangaOCR (detection + recognition) and MangaVQA only. It also lost general ability after fine-tuning: MMBench fell from 87.8 to 1.5, recovered to 82.0 with 50K natural-image samples. — [MangaLMM paper](https://arxiv.org/html/2505.20298v2)
- **Re:Verse** (ICCVW 2025, 308 annotated Re:Zero panels): VLMs read single panels well. They fail systematically at temporal causality and cross-panel cohesion, and struggle with character consistency. — [arXiv 2508.08508](https://arxiv.org/abs/2508.08508)
- **Manga109Dialog** (a speaker-detection dataset) is not part of Manga109-s, so it falls under academic-only Manga109 terms. — [HF Manga109-s](https://huggingface.co/datasets/hal-utokyo/Manga109-s)

### Inferences
- Magi v3's tail detection plus text–character association is the most directly useful open component for speaker attribution.
  - Its non-commercial licence fits at most a free, user-downloaded local mode, and even that needs legal review because the overall product has a paid tier.
  - Its English-tagged OCR should be replaced by a Japanese crop OCR.
  - Whether its detectors work well on raw Japanese pages is untested.
- A small VLM (Qwen3.5-9B / Qwen3-VL-8B) can be asked for speaker proposals with evidence, given the page image plus numbered bubble boxes. The literature suggests it will be unreliable across panels. Keep the product rule: unknown stays unknown, and reader locks win.

### Gaps
- No benchmark numbers were found for speaker-attribution accuracy of Qwen3-VL, Qwen3.5, Gemma 4 or MiniCPM on manga.
- Not read: "Zero-shot character identification and speaker prediction in comics" (ACM MM 2024), and arXiv 2608.29865 "ManGo: Manga Active Narrative Grounding Optimization". Both may be relevant.
- Magi v1–v3 training data and Japanese performance are not documented on their cards.

## 5. Per-candidate specs (repo, size, date, licence, quantized builds, projector, VRAM, image tokens, failure modes) and ranked shortlists per hardware tier

### Takeaway
On an 8 GB GPU, run a tiny crop OCR model (<0.5 GB) next to a 4–9B VLM at Q4_K_M (5–5.7 GB file plus projector). On 12–16 GB, move the VLM to Q8_0 or try Gemma 4 12B. On a 16 GB Mac, use the same models at Q4 via llama.cpp, LM Studio, MLX or CoreML. On CPU only, use ONNX crop OCR (manga-ocr-nar-small, Baberu) and skip VLM OCR.

### Cited Findings

**Qwen/Qwen3-VL-8B-Instruct**
- Apache-2.0, released 2025-10-15. — [HF](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct); [README](https://github.com/QwenLM/Qwen3-VL)
- Official GGUF `Qwen/Qwen3-VL-8B-Instruct-GGUF`: Q4_K_M 5.03 GB, Q8_0 8.71 GB, F16 16.4 GB. The mmproj comes in F16 and Q8_0 (sizes not listed). Run with `llama-mtmd-cli` or `llama-server`. — [HF GGUF](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF)
- Image budget:
  - 32×32 px per visual token; 256–1280 tokens per image by default (`shortest_edge` 256×32×32, `longest_edge` 1280×32×32).
  - Image dimensions round to multiples of 32 (28 for Qwen2.5-VL); patch size 16.
  - — [README](https://github.com/QwenLM/Qwen3-VL)
- Ollama tags `qwen3-vl:4b`, `:8b` and `:30b` returned blank output on manga spreads. — [nullmirror](https://nullmirror.com/en/blog/2026-05-24-local-vision-language-ocr-benchmark/)

**Qwen/Qwen3.5-9B, 4B, 2B, 0.8B**
- Apache-2.0, released around 2026-03-02. Natively multimodal; thinks by default. — [HF 9B](https://huggingface.co/Qwen/Qwen3.5-9B)
- GGUF `unsloth/Qwen3.5-9B-GGUF`: Q4_K_M 5.68 GB, Q8_0 9.53 GB, BF16 17.9 GB. The page does not list the mmproj. — [HF](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF)
- Q4 file sizes: 2B about 1.28 GB, 4B about 2.74 GB. — [insiderllm](https://insiderllm.com/guides/qwen-models-guide/) (search snippet)
- Works for OCR in LM Studio. — [Martin Alderson](https://martinalderson.com/posts/how-to-use-qwen-3-5-to-ocr-documents/)
- Failure modes: Chinese leakage — [estyle](https://estyle.co.jp/media/%E3%82%A8%E3%83%B3%E3%82%B8%E3%83%8B%E3%82%A2%E3%83%96%E3%83%AD%E3%82%B0/2973/); summarising instead of transcribing at small sizes — [Martin Alderson](https://martinalderson.com/posts/how-to-use-qwen-3-5-to-ocr-documents/)

**google/gemma-4-E4B-it, gemma-4-E2B-it, gemma-4-12B**
- Apache 2.0.
- GGUF `unsloth/gemma-4-E4B-it-GGUF`: Q4_K_M 4.98 GB, Q8_0 8.19 GB, BF16 15.1 GB. — [HF](https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF)
- Official llama.cpp builds: `ggml-org/gemma-4-E2B-it-GGUF`, `-E4B-it-GGUF`, `-26B-A4B-it-GGUF`, `-31B-it-GGUF`. — [llama.cpp multimodal docs](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md)
- Vision encoder about 150M on E2B/E4B. The 12B uses a 35M patch projection with no encoder. Image budget is 70–1120 tokens, and Ollama fixes it at 280. — [card](https://ai.google.dev/gemma/docs/core/model_card_4); [issue #15626](https://github.com/ollama/ollama/issues/15626)
- Sampling: temperature 1.0, top_p 0.95, top_k 64. Put the image before the text. — [HF GGUF](https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF)

**openbmb/MiniCPM-V-4.6**
- About 1.3B, Apache-2.0, SigLIP2-400M encoder. Runs in Ollama (`minicpm-v-4.6`) and llama.cpp (Q4_K_M GGUF). — [HF](https://huggingface.co/openbmb/MiniCPM-V-4_6)

**OpenGVLab/InternVL3_5-8B**
- 8.5B (0.3B vision), Apache-2.0, released 2025-08-25. 448 px tiles at 256 tokens each, up to 12 tiles plus a thumbnail. — [HF](https://huggingface.co/OpenGVLab/InternVL3_5-8B)
- ggml-org GGUFs exist only for InternVL3 (1B/2B/8B/14B), not 3.5. — [llama.cpp docs](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md)

**zai-org/GLM-4.6V-Flash**
- 9B, MIT. The repo has no official GGUF; 49 community quantizations exist. — [HF](https://huggingface.co/zai-org/GLM-4.6V-Flash)

**sbintuitions/sarashina2.2-vision-3b and sbintuitions/sarashina2.2-ocr**
- Both MIT, Transformers only (pinned to transformers 4.57.1).
- The OCR model recommends about 2.5 MP input, temperature 0 and repetition_penalty 1.2. — [HF vision](https://huggingface.co/sbintuitions/sarashina2.2-vision-3b); [HF OCR](https://huggingface.co/sbintuitions/sarashina2.2-ocr)

**PaddlePaddle/PaddleOCR-VL-1.6**
- 0.9B, Apache-2.0. Pixel caps 1280×28×28 (recognition) and 2048×28×28 (spotting). vLLM; community GGUFs. — [HF](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6)
- llama.cpp lists PaddleOCR-VL, GLM-OCR, DeepSeek-OCR, Dots.OCR and HunyuanOCR as supported OCR models, without ggml-org repo ids. These need model-specific prompts and input structures. — [llama.cpp docs](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md)

**Crop OCR models**
- manga-ocr-base-CPT-flex: 444 MB fp32 safetensors, 11 ms per crop on a 2080 Ti. — [HF](https://huggingface.co/muscgab/manga-ocr-base-CPT-flex)
- manga-ocr-nar-small: ONNX 213 MB, 58.2 ms per crop on CPU; CoreML on macOS 15+. — [HF](https://huggingface.co/muscgab/manga-ocr-nar-small)
- Baberu: ONNX 122–243 MB. — [HF](https://huggingface.co/genshiai-daichi/baberu-ocr)
- PaddleOCR-VL-For-Manga: 366.6 ms per crop on a 2080 Ti. — [JMangaBench](https://github.com/muscgab/JMangaBench_Read)

**Kaggle**
- Newer PyTorch builds (CUDA 12.8 and later) dropped Pascal, so Kaggle's P100 fails with "no kernel image" errors while T4 works. — [PyTorch forum](https://discuss.pytorch.org/t/getting-an-error-while-running-my-code-on-p100-gpu-on-kaggle/224730); [Kaggle docker-python PR #1544](https://github.com/Kaggle/docker-python/pull/1544)
- PaddleOCR-VL on a T4 needed downscaling to 1323×1871 at about 14 GB. DeepSeek-OCR ran at 1654×2339 at about 14 GB. — [LayerX](https://tech.layerx.co.jp/entry/2025/12/01/161913)

### Inferences

**Image-token cost.** The formulas come from the cited patch geometry; the arithmetic is mine.

| Model | 800×1100 single page | 1500×1100 double page |
|---|---|---|
| Qwen3-VL (Qwen3.5 probably the same, unverified) | 25 × 34–35 ≈ 850–875 tokens, inside the default budget | 47 × 34 ≈ 1,598 tokens native; the default cap of 1280 downscales it to about 1,260 tokens (about 1340×980 px) unless `longest_edge` is raised |
| Qwen2.5-VL / PaddleOCR-VL (28 px per token) | about 1,131 tokens | about 2,106 tokens; PaddleOCR-VL-1.6 downscales above 1280 tokens (recognition) or 2048 (spotting) |
| Gemma 4 | fixed 70–1120 tokens | fixed 70–1120 tokens |
| InternVL3.5 | about 6 tiles + thumbnail ≈ 1,792 tokens | 12 tiles + thumbnail ≈ 3,328 tokens |

- Qwen3-VL notes:
  - The 256-token minimum upscales small crops; a 200×400 bubble would be enlarged about 1.8×.
  - For comparison, MangaLMM used Qwen2.5-VL with a cap of 2,116,800 px (about 2,700 tokens) on 1654×1170 spreads, about 2,470 tokens per spread.
- Gemma 4 notes: at 1120 tokens one token covers about 28×28 px of an 800×1100 page, or 38×38 px of a spread. At Ollama's 280, that becomes 56 px and 77 px.
- Crop OCR models have a fixed tiny cost: at most 196 patches (CPT-flex), 324 (NAR) or a 224² input (Baberu).

**Projector (mmproj) sizes.** F16 is about 2 bytes per encoder parameter:

| Model | Encoder | Approx. mmproj F16 |
|---|---|---|
| Gemma 4 E2B / E4B | ~150M | ~0.3 GB |
| InternVL3.5 | 0.3B | ~0.6 GB |
| MiniCPM-V 4.6, LFM2.5-VL, Ministral 3, Sarashina2.2 | ~400M | ~0.8 GB |
| Gemma 4 26B / 31B | ~550M | ~1.1 GB |

The Qwen3-VL and Qwen3.5 encoder sizes are unverified; read them from the mmproj file listing before planning VRAM.

**Approximate VRAM.** Estimate = weights + mmproj + about 0.5–1.5 GB of KV cache and compute buffers for a single page with a context of about 4k tokens.

| Model | Q4_K_M | Q8_0 |
|---|---|---|
| Qwen3-VL-8B | ≈ 6.5–7.5 GB | ≈ 10–11 GB |
| Qwen3.5-9B | ≈ 7–8 GB, tight on an 8 GB laptop GPU because Windows also uses VRAM | ≈ 10.5–11.5 GB |
| Gemma 4 E4B | ≈ 5.8–6.5 GB | ≈ 9–9.5 GB |
| Gemma 4 12B (weights ~7.3 GB Q4 / ~12.7 GB Q8, estimated) | ≈ 8–9 GB, needs 12 GB | ≈ 13.5–14 GB, needs 16 GB |
| Qwen3.5-4B | ≈ 3.5–4.5 GB | — |
| MiniCPM-V 4.6 | < 2 GB | — |
| PaddleOCR-VL-1.6 / GLM-OCR / HunyuanOCR (BF16) | ≈ 2–3 GB | — |
| Sarashina2.2-OCR (BF16, ~4B) | ≈ 8–9 GB; use 8-bit on an 8 GB GPU | — |

Kaggle T4 has no fast BF16, so run FP16 or GGUF. This comes from general knowledge, not a source here.

**Ranked shortlist (a): 8 GB VRAM, e.g. RTX 4060 Laptop.** The OCR stage runs on crops from our detector; the understanding and translation stage is a separate model.

OCR stage:
1. manga-ocr-nar-small or manga-ocr-base-CPT-flex. Best accuracy and fastest, but CC BY-NC-SA.
2. PaddleOCR-VL-For-Manga. Apache-2.0 weights, Manga109-s data.
3. kha-white/manga-ocr-base. Apache-2.0, Manga109-s, baseline quality.
4. Baberu OCR v1.2. ONNX; best SFX numbers.
5. Optional: PaddleOCR-VL-1.6, Sarashina2.2-OCR in 8-bit, or HunyuanOCR for narration boxes and signs.

Understanding/translation stage:
1. Qwen3.5-9B at Q4_K_M, non-thinking.
2. Qwen3-VL-8B-Instruct at Q4_K_M.
3. Gemma 4 E4B at Q4_K_M, budget 1120, not through Ollama.
4. Qwen3.5-4B when speed matters.

**Ranked shortlist (b): 12–16 GB VRAM.** Same OCR stage.
1. Qwen3.5-9B at Q8_0.
2. Gemma 4 12B at Q4 or Q8.
3. Qwen3-VL-8B at Q8_0.
4. MiniCPM-o 4.5 (9B).
5. GLM-4.6V-Flash. MIT, but tagged zh/en only.
6. InternVL3.5-14B and Ministral 3 14B at Q4. Low priority: no Japanese OCR evidence.
7. Sarashina2.2-OCR, HunyuanOCR and PaddleOCR-VL-1.6 at BF16, as vertical-narration specialists.

**Ranked shortlist (c): Apple Silicon, 16 GB unified memory.**
- OCR:
  1. manga-ocr-nar-small via CoreML (macOS 15+).
  2. CPT-flex or manga-ocr via PyTorch MPS or CPU (MPS unverified).
  3. Baberu via ONNX.
- VLM: Qwen3.5-9B at Q4 or Qwen3-VL-8B at Q4 via llama.cpp or LM Studio; Gemma 4 E4B; Gemma 4 12B at Q4 (Google says it runs in 16 GB with MLX support, but it will be tight with a browser open); Qwen3.5-4B for speed.
- Measured M4 16 GB timings: GLM-OCR about 27 s per page; Qwen3.5-0.8B about 11 s per page; NDLOCR-Lite about 1 s per page.

**Ranked shortlist (d): CPU-only laptops.**
1. manga-ocr-nar-small-distil (30M, int8) or nar-small ONNX. About 58 ms per crop on 8 server threads, so roughly 2–4 s for a page of 30–60 boxes.
2. Baberu ONNX (122 MB).
3. kha-white manga-ocr.

Skip VLM OCR on CPU. If page understanding is needed, MiniCPM-V 4.6 (1.3B) or Qwen3.5-2B at Q4 is the ceiling, and it will be slow: 10 s or more per page, inferred from the M4 numbers.

**Kaggle test order.** Use T4 ×2, not P100.
1. Crop OCR on our 25 pages' detector crops plus a JMangaBench_Read subset: `muscgab/manga-ocr-nar-small`, `muscgab/manga-ocr-base-CPT-flex`, `jzhang533/PaddleOCR-VL-For-Manga`, `kha-white/manga-ocr-base`, `genshiai-daichi/baberu-ocr`, `PaddlePaddle/PaddleOCR-VL-1.6`, `sbintuitions/sarashina2.2-ocr`, `tencent/HunyuanOCR`, `zai-org/GLM-OCR`.
2. Whole-page and crop VLM runs with the token budget raised: `Qwen/Qwen3.5-9B` (and 4B), `Qwen/Qwen3-VL-8B-Instruct`, `google/gemma-4-E4B-it` (1120 budget), `google/gemma-4-12B`, `openbmb/MiniCPM-o-4_5` (repo id unverified), `sbintuitions/sarashina2.2-vision-3b`.
3. Only if time allows: `zai-org/GLM-4.6V-Flash`, `OpenGVLab/InternVL3_5-8B`, Ministral 3 8B.

**Deprioritise:**
- DeepSeek-OCR v1 (vertical loops) and LightOnOCR-2-1B (VJRODa CER 158).
- Phi-4-MM, Moondream 3, SmolVLM2, Florence-2, GOT-OCR2.
- Llama 4: no small model.
- Kimi-VL-2506: 16B total, no Japanese evidence.

### Gaps
- Not verified: mmproj file sizes for Qwen3-VL-8B and Qwen3.5-9B; GGUF sizes for Gemma 4 E2B and 12B; MLX repo ids for any candidate.
- Not verified: whether Ollama supports vision for Qwen3.5, and whether llama.cpp exposes per-image token limits. The llama.cpp docs page does not document `--image-min-tokens` or `--image-max-tokens`.
- No measured VRAM for any candidate on an 8 GB laptop GPU. The VRAM figures above are estimates.
- The MiniCPM-o 4.5 HF repo id and licence were not verified.

## 6. Practical tips for OCR accuracy (resolution, temperature, prompts, crop vs page)

### Takeaway
Crop each text region and run a manga crop OCR on it. Feed a VLM the page only for context, at a raised pixel budget with thinking off and temperature 0 or near-greedy. Guard against repetition loops, Chinese leakage and invented text on empty crops.

### Cited Findings
- **Crop vs whole page:**
  - The best manga readers are crop-only. JMangaBench evaluates cropped boxes and warns that scores may not transfer to other crop styles. — [JMangaBench](https://github.com/muscgab/JMangaBench_Read)
  - manga-ocr suggests smaller regions when recognition fails. — [README](https://cdn.jsdelivr.net/gh/kha-white/manga-ocr@master/README.md)
  - CPT-flex: split boxes over 32 characters. — [HF](https://huggingface.co/muscgab/manga-ocr-base-CPT-flex)
  - NAR: at most 65 output positions. — [HF](https://huggingface.co/muscgab/manga-ocr-nar-small)
  - Baberu garbles bubbles over about 190 characters. — [HF](https://huggingface.co/genshiai-daichi/baberu-ocr)
  - nullmirror found no VLM-only manga solution and recommends specialised OCR plus a VLM. — [nullmirror](https://nullmirror.com/en/blog/2026-05-24-local-vision-language-ocr-benchmark/)
- **Resolution:**
  - Gemma 4 should use a 560 or 1120 budget for OCR (not Ollama's fixed 280). — [Unsloth](https://unsloth.ai/docs/models/gemma-4) (search snippet); [issue #15626](https://github.com/ollama/ollama/issues/15626)
  - Qwen3-VL defaults to at most 1280 tokens; raise `longest_edge` for spreads. — [README](https://github.com/QwenLM/Qwen3-VL)
  - PaddleOCR-VL-1.6 spotting upscales images under 1500 px by 2×. — [HF](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6)
  - Sarashina2.2-OCR expects about 2.5 MP. — [HF](https://huggingface.co/sbintuitions/sarashina2.2-ocr)
  - For failed pages or tiny text, retry at 300 DPI; 150 DPI was the best default for document OCR. — [nullmirror](https://nullmirror.com/en/blog/2026-05-24-local-vision-language-ocr-benchmark/)
- **Sampling and thinking:**
  - Qwen3.5 OCR: thinking off, temperature 0. — [Martin Alderson](https://martinalderson.com/posts/how-to-use-qwen-3-5-to-ocr-documents/)
  - Sarashina2.2-OCR: temperature 0, repetition_penalty 1.2. — [HF](https://huggingface.co/sbintuitions/sarashina2.2-ocr)
  - HunyuanOCR: temperature 0, repetition_penalty 1.08. — [HF](https://huggingface.co/tencent/HunyuanOCR)
  - GLM-4.6V-Flash: top_k 2, repetition_penalty 1.1. — [HF](https://huggingface.co/zai-org/GLM-4.6V-Flash)
  - Qwen3-VL official VL defaults: temperature 0.7, top_p 0.8, presence_penalty 1.5. — [HF](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)
  - GPT-5 sometimes returned empty OCR output when reasoning used up the token limit. — [arXiv 2511.15059](https://arxiv.org/html/2511.15059v1)
- **Repetition:**
  - Repetition up to the token limit is common on vertical text. — [arXiv 2511.15059](https://arxiv.org/html/2511.15059v1)
  - DeepSeek-OCR loops on vertical text. — [estyle](https://estyle.co.jp/media/%E3%82%A8%E3%83%B3%E3%82%B8%E3%83%8B%E3%82%A2%E3%83%96%E3%83%AD%E3%82%B0/2973/)
  - MangaLMM repeats output; its evaluation drops segments repeated more than ten times. — [MangaLMM](https://arxiv.org/html/2505.20298v2)
- **Prompts:**
  - GLM-OCR uses a `Text Recognition:` task prompt. — [HF](https://huggingface.co/zai-org/GLM-OCR)
  - The PaddleOCR-VL-For-Manga demo sends `OCR:`. — [HF Space](https://huggingface.co/spaces/jzhang533/paddleocr-vl-for-manga-demo/blob/main/app.py)
  - Sarashina2.2-OCR takes the image with no text prompt. — [HF](https://huggingface.co/sbintuitions/sarashina2.2-ocr)
  - Qwen3.5: a short "transcribe exactly, no commentary" instruction. — [Martin Alderson](https://martinalderson.com/posts/how-to-use-qwen-3-5-to-ocr-documents/)
  - Gemma 4: put the image before the text. — [HF GGUF](https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF)
- **Fine-tuning:**
  - Fine-tuning on synthetic vertical text (JSSODa) cut Qwen2.5-VL-7B's vertical CER from 112 to 0.104 (synthetic) and from 154 to 65.1 (real). — [arXiv 2511.15059](https://arxiv.org/html/2511.15059v1)
  - Manga fine-tuning lifted PaddleOCR-VL from 27 % to 70 % sentence accuracy. — [HF](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga)
  - Full-page MangaLMM training took about 1–2 hours on 4 A100s per dataset. — [MangaLMM](https://arxiv.org/html/2505.20298v2)

### Inferences
- **Add a script and validity gate after OCR.** It should flag:
  - simplified-only Chinese characters or a very low kana ratio (leakage seen in Qwen3.5, PP-OCRv5 and GLM-OCR);
  - repeated n-grams;
  - text returned for crops our detector scored as low-confidence (manga-ocr invents text on empty crops).

  This matches the product rule against silent drops and invention.
- **For double-page spreads,** split the spread into pages, or raise the Qwen budget to keep full resolution. Downscaling to 1280 tokens costs about 10 % linear resolution on small furigana and side notes.
- **Use the cloud tier as a reference.** Score local OCR crops with the same metric as JMangaBench (composite, CER, EM), against Haiku/Opus readings of our private set, recorded separately as adjudications.

### Gaps
- Not found: furigana-specific handling numbers for any model (whether furigana are kept, dropped or merged).
- Not found: published comparisons of crop-level vs page-level accuracy for the same VLM on manga.
- Not found: recommended prompts for Gemma 4 OCR beyond the token budget and image-first ordering.
