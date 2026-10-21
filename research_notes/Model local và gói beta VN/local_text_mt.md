# Local open-weight text MT models for Japanese→Vietnamese manga dialogue (status 2026-10-21)

Scope: open-weight text models ≤ ~14B that run on an 8 GB laptop GPU, plus notable 20–32B options for 16–24 GB GPUs or Kaggle (T4 16 GB ×2 / P100). Baseline already measured by the team (private set, 120 bubbles, perfect OCR, chrF, Ollama, RTX 4060 Laptop 8 GB): Claude Haiku 5.5 (cloud) 38.7; Hy-MT2-7B Q4 33.8 (0.40 s/bubble; 26.3 with surrounding context); Hy-MT2-1.8B Q6 26.9; Qwen3-4B-Instruct-2507 Q4 24.4. All public numbers below are vendor or third-party numbers on other test sets. None of them is a ja→vi manga measurement.

## Q1. Which open models translate Japanese→Vietnamese best as of October 2026 (names, sizes, release dates, status)?

### Takeaway
No public source reports a ja→vi score for local models. On the closest public evidence (FLORES-200 non-English↔non-English averages and WMT25), **Tencent Hy-MT2-7B** (released 2026-05-21, Apache-2.0) is the strongest open model at ≤8B. It roughly matches Gemma 4 31B and Qwen3.5-397B. New models worth testing against it:
- **Xiaomi MiLMMT-46-12B v1.0** (August 2026, Gemma licence). Its authors say it beats Hy-MT2, but they publish no numbers.
- **Google TranslateGemma 4B/12B** (January 2026).
- **Gemma 4** E4B/12B, and 26B-A4B/31B for larger GPUs (April–June 2026, Apache-2.0).
- **ByteDance Seed-X-PPO-7B** (July 2025).
- **Hy-MT2-30B-A3B**, for 24 GB GPUs.

Hunyuan-MT-7B, Hunyuan-MT-Chimera and HY-MT1.5 are superseded by Hy-MT2, and GemmaX2-28 by MiLMMT-46. Sailor2 has no Japanese. The Vietnamese-only LLMs (Vistral, VyLinh, GemSUra, VinaLLaMA, PhoGPT) are from 2023–2024 and have no ja→vi evidence.

### Cited Findings

**Tencent Hy-MT2 (current state of the art among open MT-specialised models)**
- The exact name is "Hy-MT2" (Hugging Face ids `tencent/Hy-MT2-1.8B`, `tencent/Hy-MT2-7B`, `tencent/Hy-MT2-30B-A3B`). It was open-sourced on **May 21, 2026** on Hugging Face and ModelScope, together with the IFMTBench benchmark. Sizes are 1.8B, 7B and 30B-A3B (MoE, about 3B active) — [GitHub Tencent-Hunyuan/Hy-MT2](https://github.com/Tencent-Hunyuan/Hy-MT2); [Tencent Hy on X](https://x.com/TencentHunyuan/status/2057384034544804136); [arXiv 2605.22064](https://arxiv.org/html/2605.22064v1)
- The announcement says 33 languages. The README table has 38 entries (it adds variants such as zh-Hant and yue), and both Vietnamese and Japanese are listed. One Medium post says 36 languages — [GitHub](https://github.com/Tencent-Hunyuan/Hy-MT2); [AI Weekly](https://aiweekly.co/alerts/tencent-launches-open-source-hy-mt2-translation-models)
- Tencent says the 7B and 30B-A3B models beat DeepSeek-V4-Pro and Kimi K2.6 (non-thinking mode), and that the 1.8B model beats mainstream commercial APIs (Microsoft Translator, Doubao). These are self-reported claims — [GitHub](https://github.com/Tencent-Hunyuan/Hy-MT2); [Tencent Cloud techpedia](https://www.tencentcloud.com/techpedia/144776?lang=en)
- Training: about 1T tokens of MT-oriented mid-training, then per-language-family on-policy distillation from a "Chimera" teacher built on Hy3-Preview, then GRPO. In GRPO, outputs with severe repetition or mixed languages get reward 0, scoring uses an MQM-style LLM judge, and there is a length penalty — [arXiv 2605.22064](https://arxiv.org/html/2605.22064v1)
- On FLORES-200 XX⇔XX, Hy-MT2-7B reaches 97.9% of Gemini 3.1 Pro's score, the 30B-A3B 98.6% and the 1.8B 89.9% — [arXiv 2605.22064](https://arxiv.org/html/2605.22064v1)

**Hunyuan-MT-7B / Hunyuan-MT-Chimera-7B / HY-MT1.5 (superseded by Hy-MT2)**
- Hunyuan-MT-7B and Hunyuan-MT-Chimera-7B were open-sourced on **2025-09-01**. They placed first in 30 of the 31 WMT25 categories they entered. Both languages (vi, ja) are supported — [HF tencent/Hunyuan-MT-7B](https://huggingface.co/tencent/Hunyuan-MT-7B)
- HY-MT1.5-1.8B and HY-MT1.5-7B were open-sourced on **2025-12-30** (technical report arXiv 2512.24092). They add terminology intervention, contextual translation and formatted translation, and are optimised for annotated and mixed-language input. The card now points to Hy-MT2 and announces an official WMT26 partnership — [HF tencent/HY-MT1.5-7B](https://huggingface.co/tencent/HY-MT1.5-7B)
- Hy-MT2-7B scores 86.89 XCOMET-XXL on FLORES-200 XX⇔XX, against 80.98 for HY-MT1.5-7B. On WMT25 it scores 63.86 against 61.59 — [arXiv 2605.22064](https://arxiv.org/html/2605.22064v1)

**Xiaomi MiLMMT-46 (new challenger; successor to GemmaX2-28)**
- MiLMMT-46 v0.1 (arXiv 2602.11961, posted 2026-02-12) is built on Gemma 3 and covers 46 languages, including ja and vi. The training-data tables list: ar az bg bn ca cs da de el en es fa fi fr he hi hr hu id it ja kk km ko lo ms my nb nl pl pt ro ru sk sl sv ta th tl tr ur uz vi yue zhs zht. The authors claim it beats Seed-X, HY-MT1.5 and TranslateGemma — [arXiv 2602.11961](https://arxiv.org/html/2602.11961v1); [search summary citing the paper](https://www.alphaxiv.org/abs/2602.11961.md)
- MiLMMT-46 v1.0 (arXiv 2608.10812, submitted **2026-08-11**) adds GRPO with a reward that averages two reference-free QE models, gated by language ID, and then interpolates the SFT and RL checkpoints. The authors claim it **outperforms Seed-X, HY-MT2 and TranslateGemma** and leads Google Translate, Gemini 3 Pro and GPT-5 on reference-free scores. The abstract page has no numbers — [arXiv 2608.10812](https://arxiv.org/abs/2608.10812)
- The official 12B repo is `xiaomi-research/MiLMMT-46-12B-v1.0` (base `google/gemma-3-12b-pt`, licence tag "gemma"). Related repos are `xiaomi-research/MiLMMT-46-12B-v0.1` and `-12B-Pretrain` — [HF MiLMMT-46-12B-v1.0](https://huggingface.co/xiaomi-research/MiLMMT-46-12B-v1.0)
- A 4B v0.1 exists (for example the MLX conversion `mlx-community/MiLMMT-46-4B-v0.1-6bit`). A "4B v1.0" turned up only as a community upload (`KennyJA/MiLMMT-46-4B-v1.0`) — [HF mlx-community](https://huggingface.co/mlx-community/MiLMMT-46-4B-v0.1-6bit); [HF KennyJA](https://huggingface.co/KennyJA/MiLMMT-46-4B-v1.0)
- GemmaX2-28 (2B/9B, Gemma 2 base, paper 2025-02-04, 28 languages including ja and vi, licence "gemma") says on its card that MiLMMT-46 is now available — [HF ModelSpace/GemmaX2-28-9B-v0.1](https://huggingface.co/ModelSpace/GemmaX2-28-9B-v0.1)

**Google TranslateGemma**
- Sizes are 4B, 12B and 27B, built on Gemma 3, covering 55 languages. The technical report (arXiv 2601.09012) was published 2026-01-13 — [Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/translategemma/); [HF translategemma-12b-it](https://huggingface.co/google/translategemma-12b-it); [InfoQ](https://infoq.com/news/2026/01/google-translategemma-models)
- Google says the 12B beats the Gemma 3 27B baseline on WMT24++ MetricX, and that the 4B rivals the Gemma 3 12B baseline — [Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/translategemma/)
- Ollama's library page lists `ja` among the language codes — [Ollama translategemma](https://ollama.com/library/translategemma)

**Google Gemma 4 (general multimodal LLM, Apache-2.0)**
- Released **2026-04-02** in E2B, E4B, 26B MoE and 31B dense. Google says the family was trained on more than 140 languages. Gemma 4 uses the Apache 2.0 licence, while Gemma 1–3 used the Gemma Terms — [Wikipedia: Gemma](https://en.wikipedia.org/wiki/Gemma_(language_model)); [AlternativeTo](https://alternativeto.net/news/2026/4/google-releases-gemma-4-open-weight-ai-models-with-apache-2-0-license)
- The Hugging Face card lists five sizes:
  - E2B: 2.3B effective, 5.1B with embeddings
  - E4B: 4.5B effective, 8B with embeddings
  - 12B "Unified": 11.95B
  - 26B-A4B: 25.2B total, 3.8B active
  - 31B: 30.7B

  The card says "35+ languages out of the box, pre-trained on 140+". The technical report is arXiv 2607.02770 (2026-07-02). Wikipedia dates the 12B to 2026-06-03 — [HF google/gemma-4-E4B-it](https://huggingface.co/google/gemma-4-E4B-it); [Wikipedia](https://en.wikipedia.org/wiki/Gemma_(language_model))

**Qwen 3.5 / 3.6 / 3.8**
- Qwen3.5 small models (0.8B, 2B, 4B, 9B) were released **2026-03-02** under Apache-2.0. They have native vision and a hybrid thinking/non-thinking mode — [Artificial Analysis](https://artificialanalysis.ai/articles/qwen3-5-small-models); [Gigazine](https://gigazine.net/gsc_news/en/20260303-qwen-3-5-small)
- The Qwen3.5-9B card says the series covers 201 languages and dialects and is a causal LM with a vision encoder — [HF Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)
- Qwen3.6-27B (dense) and Qwen3.6-35B-A3B (MoE) are Apache-2.0. Release dates conflict: 2026-04-22 in one source, 2026-05-09 on SiliconFlow — [NYU RITS](https://rits.shanghai.nyu.edu/ai/qwen3-6-27b-a-dense-27b-model-that-beats-a-397b-moe-on-coding); [SiliconFlow](https://siliconflow.com/models/qwen3-6-27b); [dsebastien](https://www.dsebastien.net/qwen3-6-35b-a3b/)
- Qwen3.8-27B (dense multimodal, about 27.78B, 262K context) had its open weights published **2026-08-14** according to secondary sources. Its Apache-2.0 status is disputed by one source that warns about the Tongyi Qianwen licence — [DataNorth](https://datanorth.ai/news/alibaba-releases-qwen3-8-27b); [Pasquale Pillitteri](https://pasqualepillitteri.it/en/news/11335/qwen3-8-27b-run-local-16gb-lm-studio-unsloth); [OrcaRouter (nl)](https://www.orcarouter.ai/nl/blog/qwen-3-8-27b-open-weights-leak)

**ByteDance Seed-X**
- The models are Seed-X-Instruct-7B and Seed-X-PPO-7B (paper 2025-07-18). They use the Mistral architecture (Hugging Face metadata says about 8B parameters, BF16) and cover 28 languages including ja and vi. The licence is OpenMDW. The card claims parity with or wins over Gemini-2.5, Claude-3.5 and GPT-4, and recommends PPO over Instruct — [HF ByteDance-Seed/Seed-X-PPO-7B](https://huggingface.co/ByteDance-Seed/Seed-X-PPO-7B)

**Southeast-Asian and Vietnamese-focused models**
- Sailor2 comes in 1B, 8B and 20B, expanded from Qwen2.5 0.5B/7B/14B, under Apache-2.0 (paper 2025-02-18). It covers 15 languages including Vietnamese but **not Japanese** — [HF sail/Sailor2-8B-Chat](https://huggingface.co/sail/Sailor2-8B-Chat)
- SEA-LION v4 includes Qwen-SEA-LION-v4-4B-VL and -8B-VL (Qwen3-VL based, English plus 7 Southeast-Asian languages including Vietnamese). Translation is scored in SEA-HELM with MetricX-24 — [Friendli 8B-VL](https://friendli.ai/models/aisingapore/Qwen-SEA-LION-v4-8B-VL); [Friendli 4B-VL](https://friendli.ai/models/aisingapore/Qwen-SEA-LION-v4-4B-VL)
- VinaLLaMA is LLaMA-2 plus 800B Vietnamese tokens (December 2023). Its authors claim state of the art on VLSP, VMLU and the Vietnamese Vicuna benchmark — [arXiv 2312.11011](https://arxiv.org/abs/2312.11011)
- Arcee-VyLinh is a 3B model (Qwen2.5-3B-Instruct, merged). On the Vietnamese m-ArenaHard with a Claude 3.5 Sonnet judge, its vendor reports a 95.4% win rate against PhoGPT-4B-Chat and 80% against Vistral-7B-chat — [Arcee blog](https://blog.arcee.ai/introducing-arcee-vylinh-a-powerful-3b-parameter-vietnamese-language-model)
- A 2025 customer-support benchmark compared Vistral 7B, GemSUra 7B and VinaLLaMA 7B, for example hallucination scores on general questions of 0.522, 0.694 and 0.518 — [arXiv 2507.22542](https://arxiv.org/pdf/2507.22542)
- GreenNode's GreenMind-Medium-14B-R1 is described as the first open-source Vietnamese LLM optimised for NVIDIA NIM — [VietnamNet](https://vietnamnet.vn/en/vietnam-unveils-first-vietnamese-llm-on-nvidia-nim-2445851.html)
- Viettel's VT-Super is said to be 120B and built on Nemotron 3 Super. This comes from a single secondary blog — [ScaleInPeace](https://scaleinpeace.com/ia-vietnam-2026-infrastructure/)
- None of these Vietnamese or Southeast-Asian sources reports Japanese→Vietnamese results (see Gaps).

**Others (licence-limited, too large, or wrong direction)**
- Cohere Tiny Aya Global is 3.35B, released 2026-02-17, 70+ languages, CC BY-NC 4.0 according to an aggregator — [gradually.ai](https://www.gradually.ai/en/ai-models/tiny-aya-global/); [Gigazine](https://gigazine.net/gsc_news/en/20260218-cohere-tiny-aya)
- Cohere North-Small-Translate-1.0 is a sparse MoE with 218B total and 25B active parameters, covering 50 languages, under CC BY-NC 4.0 (Hugging Face page updated September 10). It is too large for local use — [HF CohereLabs/North-Small-Translate-1.0](https://huggingface.co/CohereLabs/North-Small-Translate-1.0)
- Sugoi-14B-Ultra (GGUF) is Japanese→English only. Its self-reported BLEU is 21.38, against 13.67 for the earlier quantised Sugoi 14B — [HF sugoitoolkit/Sugoi-14B-Ultra-GGUF](https://huggingface.co/sugoitoolkit/Sugoi-14B-Ultra-GGUF)
- SakuraLLM / GalTransl is Japanese→Chinese and licensed CC BY-NC-SA 4.0, which forbids commercial use — [HF SakuraLLM/GalTransl-v1](https://huggingface.co/SakuraLLM/GalTransl-v1)

### Inferences
- **Test priority for the private set.** Every item below is a public candidate that can be pulled.
  1. **Hy-MT2-7B at Q6_K (6.16 GB) and Q8_0 (7.98 GB), not only Q4_K_M**, using Tencent's own terminology and background templates (see Q3/Q4). This is the cheapest way to raise the 33.8 baseline. The vendor table shows Q4_K_M loses about 8 points of constraint-following (IFMTBench), even though plain translation quality is nearly unchanged.
  2. **MiLMMT-46-12B-v1.0**. It is the only newer model that claims to beat Hy-MT2. On Kaggle it fits as BF16/FP16 on 2×T4 (about 24 GB of weights); locally it needs a Q4 GGUF of about 7–8 GB, by analogy with Gemma-3-12B-based Ollama builds.
  3. **TranslateGemma-12B** (`translategemma:12b`, 8.1 GB) and **TranslateGemma-4B** (3.3 GB). Run them sentence-only, because the official format has no slot for context or glossary.
  4. **Gemma 4 E4B and 12B** (Apache-2.0, real system prompt). These are the best general-LLM option for glossary and pronoun rules at 8 GB.
  5. **Seed-X-PPO-7B** (AWQ-Int4 official), sentence-only.
  6. On Kaggle or a 24 GB GPU: **Hy-MT2-30B-A3B**, **Gemma 4 26B-A4B / 31B**, **Qwen3.6-27B / 35B-A3B**, **Qwen3.8-27B**.
- The team's gap between Hy-MT2 7B and 1.8B (33.8 vs 26.9 chrF) mirrors the vendor gap on FLORES XX⇔XX (86.89 vs 79.77 XCOMET). So the vendor's non-English-pair numbers seem to rank models in the same order as the private set does.
- Gemma4-E4B scores about the same as Hy-MT2-1.8B on FLORES XX⇔XX (79.96 vs 79.77). A general 4B LLM is therefore unlikely to beat Hy-MT2-7B on raw translation. It may still win when glossary and pronoun rules matter, because it follows a system prompt.
- Do not invest in Vietnamese-only 2023–2024 LLMs, in Sailor2 (no Japanese), or in GemmaX2, Hunyuan-MT or HY-MT1.5 (all superseded). NC-licensed models (Aya, Tiny Aya, North, Sakura) are unusable for a paid tier.

### Gaps
- I found no public **ja→vi** per-direction score for any candidate. Hy-MT2 publishes only ZH⇔XX, EN⇔XX and XX⇔XX averages. The Xiaomi per-language tables shown cover en↔ja, en↔vi, zh→vi and ja→zh, but not ja→vi.
- MiLMMT-46 v1.0 numbers are only in figures or the full paper, and I could not extract them. Whether an official 4B v1.0 exists is unverified.
- The Hunyuan-MT-7B and HY-MT1.5 licence name and territory terms are not shown on the pages I fetched. They are widely reported to be the Tencent Hunyuan Community License, which excludes the EU, UK and South Korea, but I did not verify this. By contrast, Hy-MT2's LICENSE.txt is plain Apache-2.0 (see Q5).
- I did not verify in this session: Llama 3.x/4 small models (official language lists), Mistral NeMo / Small 3.x / Ministral 3 (Koharu lists `ministral-3-8b-instruct`), SeaLLMs v3, Aya Expanse (the brief notes it is CC-BY-NC), and the NLLB-200 / MADLAD-400 licences.
- I found nothing on Vietnamese 2025–2026 open-weight releases from FPT, VNG/Zalo or VinAI. Search returned only marketing pages.
- The Gemma 4 12B release date (2026-06-03) comes only from Wikipedia. The Qwen3.6 and Qwen3.8 dates and licences come only from secondary sources.

## Q2. Evidence: FLORES-200 / FLORES+ / WMT24++ / WMT25 scores (direction and metric for each)

### Takeaway
The best apples-to-apples public table is the Hy-MT2 paper. It reports XCOMET-XXL on FLORES-200 XX⇔XX (non-English, non-Chinese pairs, the closest proxy to ja→vi) and on WMT25. There, Hy-MT2-7B (86.89) ≈ Gemma4-31B (86.84) > Qwen3.5-397B (86.29) > Gemma4-26B-A4B (85.60) > Qwen3.6-35B-A3B (82.11) > HY-MT1.5-7B (80.98) > Gemma4-E4B (79.96) ≈ Hy-MT2-1.8B (79.77). TranslateGemma-27B scored an unexplained 58.02. For en→vi and en→ja proxies, the Xiaomi paper gives per-language FLORES+ and WMT24++ numbers for Qwen2.5/3 and Gemma 2/3, and en↔ja numbers for Seed-X, TranslateGemma and HY-MT.

### Cited Findings

**Hy-MT2 paper, Table 2.** Cells are XCOMET-XXL / CometKiwi / GEMBA (GEMBA is an LLM judge). Rows are non-thinking unless marked (T) — [arXiv 2605.22064](https://arxiv.org/html/2605.22064v1)

| Model | FLORES-200 ZH⇔XX | FLORES-200 EN⇔XX | FLORES-200 XX⇔XX | WMT25 |
|---|---|---|---|---|
| Hy-MT2-30B-A3B | – | – | 87.47 / 76.34 / 88.79 | 62.89 (XCOMET) |
| Hy-MT2-7B | 89.45 / 78.97 / 88.89 | 93.52 / 88.07 / 89.34 | 86.89 / 76.03 / 87.23 | 63.86 / 71.21 / 82.24 |
| Hy-MT2-1.8B | 84.26 / 76.43 / 82.71 | 90.00 / 85.46 / 84.05 | 79.77 / 73.41 / 78.64 | 50.30 / 64.59 / 70.36 |
| HY-MT1.5-7B | 86.90 / 79.24 / 84.35 | 90.93 / 86.50 / 85.66 | 80.98 / 73.36 / 78.30 | 61.59 / 68.85 / 75.91 |
| HY-MT1.5-1.8B | – | – | 78.40 / 71.82 / 75.12 | 53.08 (XCOMET) |
| Gemma4-31B | 88.40 / 78.68 / 89.89 | 93.30 / 87.96 / 91.03 | 86.84 / 76.16 / 88.67 | 52.49 / 65.66 / 75.75 |
| Gemma4-26B-A4B | 87.61 / 78.31 / 88.97 | 92.80 / 87.71 / 90.65 | 85.60 / 76.58 / 87.97 | 49.62 / 64.22 / 74.36 |
| Gemma4-E4B | 83.36 / 75.92 / 83.52 | 89.54 / 85.61 / 86.95 | 79.96 / 72.91 / 80.97 | 38.36 / 55.45 / 59.95 |
| Gemma4-E2B | – | – | 75.97 (XCOMET) | 35.60 (XCOMET) |
| Qwen3.6-35B-A3B | 86.32 / 78.00 / 87.34 | 90.87 / 86.52 / 88.77 | 82.11 / 74.81 / 84.92 | 51.11 / 66.70 / 75.28 |
| Qwen3.5-397B-A17B | 88.50 / 78.64 / 90.66 | 93.07 / 87.73 / 91.49 | 86.29 / 76.39 / 88.87 | 55.79 / 68.80 / 83.14 |
| TranslateGemma-27B-IT | – (not supported) | – | 58.02 / 66.08 / 81.24 | – |
| Tower-Plus-72B | 79.69 / 71.82 / 77.86 | 84.16 / 81.13 / 78.82 | 70.02 / 65.53 / 67.85 | 41.00 / 55.54 / 54.85 |
| Gemini 3.1 Pro (T) | – | – | 88.74 / 77.60 / 90.97 | 57.58 (XCOMET) |
| GPT-5.5 | – | – | 87.92 / 77.20 / 90.37 (one row); 88.44 for the (T) row as extracted | 56.68 (XCOMET) |
| DeepSeek-V4-Pro / Kimi K2.6 | – | – | 83.29 / 84.05 (XCOMET) | 53.97 / 49.76 |
| Microsoft Translator | – | – | 80.13 / 72.42 / 83.85 | 42.01 |

- The paper does not explain TranslateGemma-27B's low XX⇔XX score. A dash only means the model does not support that test set — [arXiv 2605.22064](https://arxiv.org/html/2605.22064v1)
- Hy-MT2 publishes **no per-pair** (for example ja→vi) breakdown, and no BLEU or chrF — [arXiv 2605.22064](https://arxiv.org/html/2605.22064v1)
- DomainMTBench and WildMTBench (XCOMET), in that order:
  - Hy-MT2-7B: 94.92 and 90.28
  - Hy-MT2-1.8B: 93.41 and 87.43
  - TranslateGemma-27B: 94.30 and 88.44
  - Gemma4-31B: 93.65 and 86.35
  - Gemma4-E2B: 90.09 and 82.01

  Source: [arXiv 2605.22064](https://arxiv.org/html/2605.22064v1)

**TranslateGemma (vendor; English-centric WMT24++, 55 languages)**
- WMT24++ MetricX (lower is better): 4B 5.32, 12B 3.60, 27B 3.09. COMET: 81.6, 83.5, 84.4. WMT25 MQM (10 languages, lower is better): 12B 7.94, 27B 5.86. Vistra image translation MetricX: 2.57, 2.08, 1.57 — [HF translategemma-12b-it](https://huggingface.co/google/translategemma-12b-it)
- The human MQM evaluation covered 10 pairs. Japanese appears only as ja→en, and there is no Vietnamese pair — [TranslateGemma tech report](https://arxiv.org/pdf/2601.09012) (from a search snippet; I could not parse the PDF text)

**Xiaomi scaling paper (arXiv 2602.11961), per-language proxies.** This paper's base-model evaluation used in-context examples with an "X=Y" template. Metrics are FLORES+ spBLEU / COMET and WMT24++ XCOMET / COMETKiwi. All rows are from [arXiv 2602.11961](https://arxiv.org/html/2602.11961v1).

| Model | FLORES+ en→vi | FLORES+ en→ja | FLORES+ ja→en | FLORES+ zh→vi | WMT24++ en→vi (XCOMET/Kiwi) | WMT24++ en→ja |
|---|---|---|---|---|---|---|
| Qwen3-4B | 37.20 / 87.72 | 22.17 / 89.10 | 30.05 / 87.45 | 27.19 / 86.71 | 77.37 / 70.78 | 74.08 / 77.24 |
| Qwen3-8B | 39.85 / 88.46 | 27.20 / 90.35 | 32.03 / 87.94 | 29.51 / 87.77 | 80.25 / 74.50 | 79.94 / 81.58 |
| Qwen3-14B | 41.64 / 89.15 | 28.98 / 90.91 | 34.00 / 88.29 | 30.55 / 88.19 | 82.83 / 77.54 | 82.13 / 83.22 |
| Qwen2.5-7B | 37.03 / 87.80 | 23.93 / 89.39 | 30.77 / 87.65 | 27.25 / 87.02 | 78.54 / 72.20 | 73.72 / 77.49 |
| Gemma3-4B | 40.62 / 88.25 | 25.57 / 89.38 | 31.72 / 87.53 | 28.91 / 87.35 | 78.64 / 73.14 | 75.38 / 77.41 |
| Gemma3-12B | 44.23 / 89.35 | 32.24 / 91.35 | 35.86 / 88.57 | 32.54 / 88.53 | 83.0 / 78.5 | 83.26 / 84.42 |
| Gemma2-9B | 42.39 / 89.04 | 30.55 / 91.11 | 34.95 / 88.37 | 29.05 / 87.12 | 81.44 / 76.29 | 82.48 / 83.72 |

- The same paper gives MT-specialised models on en→ja / ja→en. The table header was not visible in the extracted text; the values match spBLEU / COMET on FLORES+ — [arXiv 2602.11961](https://arxiv.org/html/2602.11961v1)

| Model | en→ja | ja→en |
|---|---|---|
| Seed-X-PPO-7B | 39.17 / 92.32 | 31.93 / 88.55 |
| Seed-X-Instruct-7B | 37.48 / 91.75 | 34.16 / 88.1 |
| HY-MT1.5-7B | 29.74 / 92.46 | 26.99 / 88.04 |
| HY-MT1.5-1.8B | 25.35 / 91.71 | 21.18 / 86.78 |
| Hunyuan-MT-7B | 29.58 / 92.41 | 26.57 / 87.94 |
| TranslateGemma-12B | 26.6 / 91.91 | 27.53 / 88.03 |
| TranslateGemma-4B | 26.16 / 91.25 | 25.88 / 87.41 |
| GemmaX2-9B | 33.41 / 91.28 | 36.42 / 88.78 |
| Tower-Plus-9B | 33.86 / 92.24 | 34.57 / 88.93 |

**Qwen3.5 (vendor):**
- WMT24++: Qwen3.5-9B 72.6, Qwen3.5-4B 66.6. The metric is not named on the card. Its multilingual instruction-following benchmark MAXIFE gives 83.4 and 78.0 — [HF Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)

**Gemma 4 (vendor):**
- MMMLU: E2B 67.4, E4B 76.6, 12B 83.4, 26B-A4B 86.3, 31B 88.4. The card shows no WMT24++ number — [HF google/gemma-4-E4B-it](https://huggingface.co/google/gemma-4-E4B-it)

**Dialogue, literary and manga benchmarks:**
- Japanese→English manga (Lippmann et al., COLING 2025, GPT-4 Turbo only), chrF: line-by-line 32.7, page-by-page 36.0, page-by-page with image 36.6, numbered bubbles with image 36.8 (best), whole volume 34.9. In human MQM, the best system scored −1.98 against −1.31 for the official translation and −4.25 for Google Translate — [arXiv 2411.02589](https://arxiv.org/html/2411.02589v2)
- VNTL leaderboard (Japanese visual-novel lines → English, 256 samples, cosine similarity to the reference, with chrF secondary): Sugoi Translator 0.6093, Google Translate 0.5395, Papago 0.4560. The README calls the results preliminary — [VNTL leaderboard README](https://www.huggingface.co/datasets/lmg-anon/vntl-leaderboard/blob/main/README.md?code=true)

**Independent community tests (Japanese):**
- On an RTX 4070 Ti, Hy-MT2-1.8B passed Markdown, terminology, glossary and keigo tests. Hy-MT2-7B added an unrequested "【日本語訳】" prefix and inserted unsourced sentences with garbled Japanese in the keigo (JA→EN) test. The author recommends starting with the 1.8B — [META-MARK, 2026-05-25](https://meta-mark.com/blog/hy-mt2-vs-deepl-local-translation-test)
- A patent-translation test scored Hy-MT2-1.8B at 54/100 (search snippet only, not opened) — [note.com maekawa_ip](https://note.com/maekawa_ip/n/n53de1d0f4958)
- A 2026 personal ranking puts TranslateGemma (12B) first for translation, ahead of Gemma3 27B (search snippet only) — [note.com Catapp-Art3D](https://note.com/catap_art3d/n/nda04c904717e)

### Inferences
- For ja→vi, the most relevant public signal is XX⇔XX (a non-English pair on both sides). By that signal, Hy-MT2-7B is at least as good as the best open general LLMs up to 31B, and much better than any ≤9B general LLM.
- Seed-X-PPO-7B's high en→ja spBLEU (39.17, against about 30 for the Hunyuan family) shows it is strong at Japanese generation. For our task the source side (Japanese reading) matters more. On ja→en, Seed-X-Instruct (34.16) and GemmaX2-9B (36.42) beat HY-MT1.5-7B (26.99) on spBLEU, but COMET is close (88.0–88.8). These are pre-Hy-MT2 numbers.
- Gemma3-12B as a base model, with few-shot examples, scores very well on en→vi (44.23 spBLEU / 89.35 COMET). That supports trying Gemma-family 12B models (Gemma 4 12B, TranslateGemma-12B, MiLMMT-46-12B) as the next size tier for Vietnamese output.
- Treat the team's own chrF numbers as the decision metric. Public XCOMET and spBLEU differences of 1–2 points between models do not predict dialogue quality, pronoun choice or honorific handling.

### Gaps
- I found no FLORES ja→vi row in any accessible table, no WMT24++ en→vi value for TranslateGemma or Hy-MT2, and no subtitle or dialogue benchmark with Vietnamese.
- Hy-MT2's Table 5 BF16 values differ from Table 2 (for example WMT25 for the 7B is 73.05 in Table 5 and 63.86 in Table 2). They probably use a different metric or subset, so compare only within a table.

## Q3. Context handling: which models accept a glossary, names, pronoun rules and page context; required templates; known failure modes; techniques

### Takeaway
MT-specialised models are template-bound.
- **Hy-MT2** has official, separate templates for terminology (glossary pairs), background context, style, user preferences, delimiter-preserving batches and structured data. It has **no system prompt**, an 8K context limit, and measured constraint-following (IFMTBench) that drops sharply at Q4_K_M.
- **TranslateGemma** officially accepts only one text item per user turn and no system role, so context or glossary injection is "unofficial".
- **Seed-X** has no chat template and expects a target-language tag.
- **MiLMMT-46** uses a fixed three-line prompt.

General LLMs (Gemma 4, Qwen3.5/3.6) accept a real system prompt with glossary and pronoun rules. Thinking must be turned off.

Evidence on context: page-level context with numbered lines helps a large model (GPT-4 Turbo, +3.3 chrF over line-by-line). Context beyond one page does not help. Few-shot examples help 7B–14B models but hurt a 3B one, and JSON multi-output breaks small models.

### Cited Findings

**Hy-MT2 templates.** Use full language names (for example "Vietnamese"). There is no default system prompt. Sampling for 1.8B/7B: temperature 0.7, top_p 0.6, top_k 20, repetition_penalty 1.05. For 30B-A3B: top_p 1.0, top_k -1, repetition_penalty 1.0. Max context 8192 — [GitHub Hy-MT2](https://github.com/Tencent-Hunyuan/Hy-MT2); [HF tencent/Hy-MT2-7B](https://huggingface.co/tencent/Hy-MT2-7B)
- Default: `Translate the following text into {target_lang}.` followed by an instruction to output only the translation without extra explanation, then the source text.
- Terminology: a "Reference the following translations:" block of `{src} translates to {tgt}` lines, then the default instruction.
- Background or contextual (also called structured data 2): asks the model to translate the text into `{target_lang}` taking a `[Background Information]` block into account.
- Delimiters: asks the model to keep exactly the same number of delimiters and not to omit, escape or translate them.
- Personalization: a `[Translation Tasks]` list of user preferences, then the instruction to translate the `[Source Text]`.
- Style: the translation style must follow `{target_style}`.
- Structured data 1: translate only the user-facing text inside `{format_type}` data and never alter tags, keys or placeholders.

**HY-MT1.5 contextual template.** This shows Tencent's intent: the context comes first, then the instruction "参考上面的信息，把下面的文本翻译成{target_language}，注意不需要翻译上文，也不要额外解释：" followed by the source. In English: use the information above, translate the text below, do not translate the context, do not explain. The terminology template is "参考下面的翻译：{source_term} 翻译成 {target_term}" followed by the standard instruction. The XX⇔XX template is `Translate the following segment into {target_language}, without additional explanation.` — [HF tencent/HY-MT1.5-7B](https://huggingface.co/tencent/HY-MT1.5-7B)

**Hunyuan-MT-Chimera-7B** fuses up to six candidate translations into one refined output, using an "only output the refined translation" instruction — [HF tencent/Hunyuan-MT-7B](https://huggingface.co/tencent/Hunyuan-MT-7B)

**IFMTBench (Hy-MT2 paper).**
- It has 7,344 samples (4,506 single-constraint, 2,838 multi-constraint) testing terminology, format and style. Languages are zh, de, ja, fr, en, es and ko, so **Vietnamese is not included**.
- Total scores: Hy-MT2-1.8B 69.36, 7B 83.14, 30B-A3B 84.69.
- The paper says HY-MT1.5 "may ignore constraints". The 30B-A3B is weaker in later turns of Multi-IF.
- Language mixing and degeneration were handled in training (reward 0). The paper reports no test-time failure rates.

Source: [arXiv 2605.22064](https://arxiv.org/html/2605.22064v1)

**TranslateGemma format.**
- Only User and Assistant roles are supported. The user `content` must be a list with **exactly one entry** of `{type: "text", source_lang_code, target_lang_code, text}`. Codes may be ISO 639-1 or regional (for example `ja`, `vi`, `en-GB`), and unsupported codes raise an error. Other prompting is "unofficial" and must be built by hand with Gemma 3 control tokens — [HF translategemma-12b-it](https://huggingface.co/google/translategemma-12b-it)
- Ollama's template is a single user message: a "professional {SOURCE_LANG} ({SOURCE_CODE}) to {TARGET_LANG} ({TARGET_CODE}) translator" persona, an instruction to produce only the translation and to keep the original's meaning and nuances, then "Please translate the following {SOURCE_LANG} text into {TARGET_LANG}:", **two blank lines**, and the text — [Ollama translategemma](https://ollama.com/library/translategemma)

**Seed-X.** Do not use `apply_chat_template`, and avoid multi-round prompts. The language tag is required at the end, as in the card's example `Translate the following English sentence into Chinese:\nMay the force be with you <zh>` (for this project the tag would be `<vi>`). A CoT variant adds "and explain it in detail". Recommended decoding is beam search (beam 4, max 512 tokens) or greedy — [HF Seed-X-PPO-7B](https://huggingface.co/ByteDance-Seed/Seed-X-PPO-7B)

**MiLMMT-46.** The prompt is three lines: `Translate this from <src name> to <tgt name>:`, then `<src name>: <text>`, then `<tgt name>:`. Language names must be written exactly as the card gives them — [HF MiLMMT-46-12B-v1.0](https://huggingface.co/xiaomi-research/MiLMMT-46-12B-v1.0)

**Gemma 4.**
- It has a native `system` role. Thinking is on when `<|think|>` starts the system prompt, and the example code uses `enable_thinking=False`. E2B and E4B emit no thought block when thinking is off; larger models still emit an empty one — [HF gemma-4-E4B-it](https://huggingface.co/google/gemma-4-E4B-it)
- Ollama's recommended sampling is temperature 1.0, top_p 0.95, top_k 64 — [Ollama gemma4](https://ollama.com/library/gemma4)

**Qwen3.5.** Thinking is on by default. Disable it with `enable_thinking: False` in `chat_template_kwargs`; the `/think` and `/nothink` soft switches are not supported. Non-thinking sampling: temperature 0.7, top_p 0.8, top_k 20, presence_penalty 1.5 — [HF Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)

**Sugoi-14B-Ultra.** It needs a specific system prompt, works best with about 10 lines of context, and is recommended at temperature 0.1, top_k 40, top_p 0.95 — [HF Sugoi-14B-Ultra-GGUF](https://huggingface.co/sugoitoolkit/Sugoi-14B-Ultra-GGUF)

**Ollama runtime pitfall.** Running Tencent's GGUF via `hf.co/tencent/Hy-MT2-1.8B-GGUF` required fixing the Modelfile `stop` token. Without the fix the output ran on, had trailing text and did not end cleanly — [META-MARK](https://meta-mark.com/blog/hy-mt2-vs-deepl-local-translation-test)

**Manga context research (GPT-4 Turbo, JA→EN).**
- Page-by-page beats line-by-line (36.0 vs 32.7 chrF). Context beyond the page "does not enhance translation quality": 3 pages scored 35.9, the whole volume 34.9. A rolling summary was the best of the long-context methods.
- Replacing bubble text in the image with reading-order numbers (PBP-VIS-NUM) was best at 36.8. Long-context variants asked for JSON with `line`, `translation` and `reasoning` fields.
- One-shot and five-shot examples showed no measurable difference.

Source: [arXiv 2411.02589](https://arxiv.org/html/2411.02589v2)

**Local-LLM prompting study (Arcan, 2026-07-28).** On English→EU languages, FLORES devtest, 5-shot prompting helped `mistral:latest` (7B) and `qwen2.5:14b` but hurt `llama3.2:3b`. Embedding-similar examples were best on average, but only modestly. JSON "family-scope" multi-output prompts exposed structured-output failures in smaller models — [arXiv 2607.26286](https://arxiv.org/abs/2607.26286)

**Production practice in manga-image-translator.** Lines carry `<|1|>`-style IDs, and a rule requires 1:1 input-to-output line IDs and a redo if the counts differ. Per-language few-shot samples are provided. JSON mode is off by default (Gemini only). An auto-selected glossary file and `--context-size` (pages of context) apply only to the OpenAI translator. The user prompt template is a plain "translate the following text from a manga to {to_lang}" request — [GitHub manga-image-translator](https://github.com/zyddnys/manga-image-translator)

**BallonsTranslator.** Its LLM translator carries a glossary and page history across a project (search summary of a review) — [hysenlabs review](https://hysenlabs.com/projects/dmmaze-ballonstranslator)

### Inferences
- **The likely reasons Hy-MT2-7B fell from 33.8 to 26.3 chrF with context:**
  - (a) a non-official context prompt, so the model translated or merged the context;
  - (b) Q4_K_M's measured loss in instruction following (IFMTBench 83.14 → 75.11, see Q4);
  - (c) possibly an untuned Ollama `stop` token producing run-on output.

  Concrete A/B tests on the 120-bubble set:
  1. Q4_K_M vs Q6_K vs Q8_0 with the **official Hy-MT2 background template** (context in `[Background Information]`, target bubble alone as the source).
  2. The **terminology template**, listing only the glossary entries whose source string actually appears in the bubble. This keeps prompts short.
  3. A **delimiter-batch** call: the whole page's bubbles joined with a fixed delimiter under the official delimiter template. The model sees the page as context but must return the same number of segments. Verify the count and fall back to per-bubble on a mismatch.
  4. Correct `stop` tokens in Ollama.
- **Honorifics and directed pronouns.** No template targets them. The terminology template is the natural slot for fixed renderings (for example a name with its honorific mapped to "Tanaka-san", or 先輩 to "senpai"). A directed pair such as "A calls B 'chị', A calls self 'em'" fits only the personalization or background template, or a general LLM's system prompt. No evidence exists on how well any model follows such rules in Vietnamese; IFMTBench excludes Vietnamese.
- **TranslateGemma** should be evaluated sentence-only, with no glossary. Inserting context breaks its official one-item format. For names, apply placeholder substitution before translation and restore after (for example replace a name with a token and re-insert the locked Vietnamese rendering); this needs testing.
- **General LLMs** (Gemma 4 E4B/12B, Qwen3.5-9B) are the right vehicle for system-prompt glossaries and pronoun rules. Use numbered lines (`<|n|>` IDs) rather than JSON for ≤9B models, check line counts, and turn thinking off.
- Add automatic guards for known failure modes: an unrequested prefix (such as "【…訳】"), extra sentences (length-ratio check), Japanese characters left in the Vietnamese output (script or language-ID check), and dropped honorifics (if the source has さん/くん/ちゃん/先輩, check that the output has -san/-kun/-chan/senpai). Retry with a no-context call when a guard trips.

### Gaps
- No measurement exists of honorific retention or directed Vietnamese pronoun accuracy for any local model.
- Hy-MT2's paper gives no quantitative results for the background-context or glossary templates (only IFMTBench in other languages).
- I found no public report of the "translates the context instead of the target" failure for Hy-MT2 specifically. It is inferred from the HY-MT1.5 template wording, which explicitly forbids translating the preceding context.

## Q4. Quantization impact on translation quality (Q4_K_M vs Q5/Q6/Q8 vs FP16)

### Takeaway
The only MT-specific measured evidence is Tencent's Hy-MT2 Table 5. For the 7B, **Q4_K_M ≈ BF16 on translation quality**: FLORES XX⇔XX XCOMET 86.90 vs 87.06, and WMT25 72.30 vs 73.05. But **instruction or constraint following drops about 8 points**: IFMTBench 75.11 vs 83.14. The 1.8B loses more from Q4_K_M (XX⇔XX −2.0, WMT25 −2.9). An older human study found automatic metrics understate quantization damage for Japanese (−1.7% automatic vs −16% human).

### Cited Findings
- Hy-MT2 Table 5 values (BF16 → FP8 → Q4_K_M → 2-bit). Metric is mostly XCOMET-XXL. Columns are FLORES ZH⇔XX / EN⇔XX / XX⇔XX / WMT25 / IFMTBench — [arXiv 2605.22064](https://arxiv.org/html/2605.22064v1)
  - 7B BF16: 89.17 / 91.43 / 87.06 / 73.05 / 83.14
  - 7B FP8: 88.92 / 91.45 / 86.92 / 72.59 / 82.38
  - 7B Q4_K_M: 88.96 / 91.46 / 86.90 / 72.30 / **75.11**
  - 1.8B BF16: 83.49 / 87.02 / 79.21 / 60.33 / 69.36
  - 1.8B FP8: 83.11 / 86.66 / 78.63 / 59.51 / 67.06
  - 1.8B Q4_K_M: 82.22 / 85.87 / 77.19 / 57.46 / 63.47
  - 1.8B 2-bit: 80.86 / 84.74 / 76.31 / 57.96 / 58.99
  - 30B-A3B BF16 → FP8: XX⇔XX 88.13 → 88.01, IFMTBench 84.69 → 83.47. No GGUF row is given for the 30B.
- Hy-MT2's 1.25-bit 1.8B takes about 440 MB and runs about 1.5× faster than 4-bit Hy-MT1.5 on an Apple A15. The paper gives **no accuracy numbers** for 1.25-bit — [arXiv 2605.22064](https://arxiv.org/html/2605.22064v1); [Tencent Cloud](https://www.tencentcloud.com/techpedia/144776?lang=en)
- Seed-X ships official GPTQ-Int8 and AWQ-Int4 builds, and its card **advises against unofficial quantized versions** for local deployment — [HF Seed-X-PPO-7B](https://huggingface.co/ByteDance-Seed/Seed-X-PPO-7B)
- Marchisio et al. (Findings of EMNLP 2024; Command R/R+ and Aya 23, 8B–103B, up to 23 languages):
  - Automatic metrics showed −1.7% for Japanese, but human evaluators saw −16.0% on realistic prompts.
  - Non-Latin-script languages are hit hardest.
  - Automatic metrics understate the harm.

  This is from search snippets and secondary summaries; I did not open the full paper — [ACL Anthology 2024.findings-emnlp.935](https://aclanthology.org/2024.findings-emnlp.935/); [Moonlight review](https://www.themoonlight.io/review/how-does-quantization-affect-multilingual-llms)

### Inferences
- On an 8 GB GPU, use **Hy-MT2-7B Q6_K (6.16 GB)** as the default when glossary or context prompts are used. Q8_0 (7.98 GB) will likely spill out of an 8 GB laptop GPU once the KV cache and display are counted. Keep Q4_K_M for plain sentence calls if speed matters. Q5_K_M is not published by Tencent, so it would need a community or self-made GGUF.
- For the 1.8B, Q6/Q8 is advisable; its Q4 penalty is larger. On Kaggle, run FP16 to obtain the "upper bound" for each candidate on the private set. Then quantify the Q4/Q6/Q8 deltas with chrF and a human spot-check of pronouns and honorifics, because metric deltas may understate the harm for Japanese.
- Prefer official quants where they exist: Seed-X AWQ/GPTQ, Tencent GGUF and FP8.

### Gaps
- I found no MT-specific measurements of Q5_K_M or Q6_K for any model, and no quantization data for TranslateGemma, MiLMMT, Gemma 4 or Qwen3.5 on ja or vi.
- Whether imatrix quants (for example community "i1" GGUFs) help MT quality is unknown.

## Q5. Per-candidate details: Hugging Face repo, GGUF/Ollama, size on disk, VRAM, speed, licence

### Takeaway
At 8 GB the realistic local set is: Hy-MT2-7B (Q4_K_M 4.62 GB / Q6_K 6.16 GB, Apache-2.0); TranslateGemma-4B/12B (Ollama 3.3 / 8.1 GB, Gemma Terms, gated); Gemma 4 E4B/12B (Ollama 6.6–9.5 / 7.7–8.0 GB, Apache-2.0); Qwen3.5-4B/9B (3.3–4.0 / 6.6–7.6 GB, Apache-2.0); Seed-X-PPO-7B AWQ-Int4 (OpenMDW); and MiLMMT-46-12B (Gemma licence, needs a 4-bit build). At 16–24 GB, add Hy-MT2-30B-A3B (FP8 official, no official GGUF), Gemma 4 26B/31B (16–20 GB), Qwen3.5/3.6/3.8-27B (17–20 GB) and TranslateGemma-27B (17 GB).

### Cited Findings

| Model | HF repo id(s) | Released | GGUF / Ollama (sizes) | Licence | Source |
|---|---|---|---|---|---|
| Hy-MT2-7B (≈8B BF16) | `tencent/Hy-MT2-7B`, `tencent/Hy-MT2-7B-FP8` | 2026-05-21 | Official `tencent/Hy-MT2-7B-GGUF`: `Hy-MT2-7B-Q4_K_M.gguf` 4.62 GB, `HY-MT2-7B-Q6_K.gguf` 6.16 GB, `HY-MT2-7B-Q8_0.gguf` 7.98 GB (mixed-case file names). Ollama via `hf.co/tencent/Hy-MT2-7B-GGUF:<quant>` | Apache-2.0 (HF metadata and repo LICENSE.txt) | [HF GGUF tree](https://huggingface.co/tencent/Hy-MT2-7B-GGUF/tree/main); [HF card](https://huggingface.co/tencent/Hy-MT2-7B); [LICENSE.txt](https://raw.githubusercontent.com/Tencent-Hunyuan/Hy-MT2/main/LICENSE.txt); [META-MARK](https://meta-mark.com/blog/hy-mt2-vs-deepl-local-translation-test) |
| Hy-MT2-1.8B | `tencent/Hy-MT2-1.8B`, `-FP8` | 2026-05-21 | `tencent/Hy-MT2-1.8B-GGUF` (about 1.1 GB per META-MARK); `Hy-MT2-1.8B-2bit-GGUF`; `Hy-MT2-1.8B-1.25bit-GGUF` (about 440 MB) | Apache-2.0 | [GitHub](https://github.com/Tencent-Hunyuan/Hy-MT2); [META-MARK](https://meta-mark.com/blog/hy-mt2-vs-deepl-local-translation-test) |
| Hy-MT2-30B-A3B (MoE) | `tencent/Hy-MT2-30B-A3B`, `-FP8` | 2026-05-21 | No official GGUF listed. vLLM (built from source) and SGLang examples. transformers ≥ 5.6.0 with `trust_remote_code` | Apache-2.0 (repo) | [GitHub](https://github.com/Tencent-Hunyuan/Hy-MT2) |
| HY-MT1.5-7B / 1.8B (superseded) | `tencent/HY-MT1.5-7B`, `-FP8`, `-GPTQ-Int4` | 2025-12-30 | 18 community quants (unnamed) | Not shown on the fetched page | [HF](https://huggingface.co/tencent/HY-MT1.5-7B) |
| Hunyuan-MT-7B / Chimera-7B (superseded) | `tencent/Hunyuan-MT-7B`, `-fp8`, `tencent/Hunyuan-MT-Chimera-7B`, `-fp8` | 2025-09-01 | Community quants | Not shown on the fetched page | [HF](https://huggingface.co/tencent/Hunyuan-MT-7B) |
| TranslateGemma 4B / 12B / 27B | `google/translategemma-4b-it`, `-12b-it`, `-27b-it` (gated) | Report 2026-01-13 | Ollama `translategemma:4b` 3.3 GB, `:12b` 8.1 GB, `:27b` 17 GB (128K context, text and image). 32 quantized models on HF | Gemma Terms of Use | [HF](https://huggingface.co/google/translategemma-12b-it); [Ollama](https://ollama.com/library/translategemma) |
| MiLMMT-46-12B v1.0 | `xiaomi-research/MiLMMT-46-12B-v1.0` (also `-v0.1`, `-Pretrain`) | v1.0 paper 2026-08-11 | 2 quantized models listed (format not stated). MLX community builds of 4B and 12B v0.1 | "gemma" | [HF](https://huggingface.co/xiaomi-research/MiLMMT-46-12B-v1.0); [arXiv 2608.10812](https://arxiv.org/abs/2608.10812) |
| Gemma 4 E2B / E4B / 12B / 26B-A4B / 31B | `google/gemma-4-E4B-it` etc. | 2026-04-02 (12B: 2026-06-03 per Wikipedia) | Ollama `gemma4:e2b` 4.6–7.5 GB, `:e4b` 6.6–9.5 GB, `:12b` 7.7–8.0 GB, `:26b` 16–19 GB, `:31b` 19–20 GB. Context 128K for E2B/E4B, 256K for the others | Apache-2.0 | [Ollama](https://ollama.com/library/gemma4); [HF](https://huggingface.co/google/gemma-4-E4B-it) |
| Qwen3.5 0.8B / 2B / 4B / 9B / 27B / 35B-A3B | `Qwen/Qwen3.5-9B` etc. | 2026-02 / 03 | Ollama `qwen3.5:4b` 3.3–4.0 GB, `:9b` 6.6–7.6 GB, `:27b` 17–20 GB, `:35b` 22 GB (256K context, text and image) | Apache-2.0 | [Ollama](https://ollama.com/library/qwen3.5); [HF](https://huggingface.co/Qwen/Qwen3.5-9B) |
| Qwen3.6-27B / 35B-A3B | `Qwen/Qwen3.6-27B` etc. (repo ids not verified) | April or May 2026 | 27B Q4_K_M about 16.8 GB; 35B-A3B Q4_K_S about 21 GB (secondary sources) | Apache-2.0 (secondary) | [NYU RITS](https://rits.shanghai.nyu.edu/ai/qwen3-6-27b-a-dense-27b-model-that-beats-a-397b-moe-on-coding); [dsebastien](https://www.dsebastien.net/qwen3-6-35b-a3b/) |
| Qwen3.8-27B | `Qwen/Qwen3.8-27B` (per secondary source) | 2026-08-14 (secondary) | Unsloth quants said to run in 16 GB, smallest about 9 GB | Apache-2.0 per DataNorth; disputed | [DataNorth](https://datanorth.ai/news/alibaba-releases-qwen3-8-27b); [Pillitteri](https://pasqualepillitteri.it/en/news/11335/qwen3-8-27b-run-local-16gb-lm-studio-unsloth) |
| Seed-X-PPO-7B / Instruct-7B | `ByteDance-Seed/Seed-X-PPO-7B`, `-GPTQ-Int8`, `-AWQ-Int4` | 2025-07 | 14 quants in the model tree (most unofficial; the card discourages them) | OpenMDW | [HF](https://huggingface.co/ByteDance-Seed/Seed-X-PPO-7B) |
| GemmaX2-28-2B / 9B (superseded) | `ModelSpace/GemmaX2-28-9B-v0.1` | 2025-02 | Community | "gemma" | [HF](https://huggingface.co/ModelSpace/GemmaX2-28-9B-v0.1) |
| Sailor2-1B / 8B / 20B (no Japanese) | `sail/Sailor2-8B-Chat` etc. | 2024-12 / 2025-02 | Community | Apache-2.0 | [HF](https://huggingface.co/sail/Sailor2-8B-Chat) |
| Sugoi-14B-Ultra (JA→EN only) | `sugoitoolkit/Sugoi-14B-Ultra-GGUF` | n/a | GGUF | Not verified | [HF](https://huggingface.co/sugoitoolkit/Sugoi-14B-Ultra-GGUF) |
| SakuraLLM GalTransl (JA→ZH only) | `SakuraLLM/GalTransl-v1` | n/a | GGUF (Sakura line) | CC BY-NC-SA 4.0, no commercial use | [HF](https://huggingface.co/SakuraLLM/GalTransl-v1) |

**Runtime notes:**
- Tencent's Hy-MT2 card says its GGUF depends on the "STQ" kernel from llama.cpp PR #22836, and its example uses `-ngl 0`. Ollama and LM Studio are not mentioned — [HF Hy-MT2-7B](https://huggingface.co/tencent/Hy-MT2-7B); [GitHub](https://github.com/Tencent-Hunyuan/Hy-MT2)
- The `translation` pipeline is unsupported in transformers v5 (stated on both the Hy-MT2 and North-Small-Translate cards) — [HF Hy-MT2-7B](https://huggingface.co/tencent/Hy-MT2-7B); [HF North-Small-Translate](https://huggingface.co/CohereLabs/North-Small-Translate-1.0)
- Hy-MT2-7B had 13,590 downloads in the last month and 23 quantized models in its model tree. A WebGPU GGUF Space exists (`localellm/WebGPU-hy-mt2-7b-i1-gguf`) — [HF Hy-MT2-7B](https://huggingface.co/tencent/Hy-MT2-7B)

**Speed (consumer GPUs):**
- On an RTX 4070 Ti 12 GB with Ollama, Hy-MT2-1.8B ran at **167–234 tok/s** and Hy-MT2-7B at **33–84 tok/s** (quantization not stated) — [META-MARK](https://meta-mark.com/blog/hy-mt2-vs-deepl-local-translation-test)
- The team's own measurement on the RTX 4060 Laptop is Hy-MT2-7B Q4 at 0.40 s per bubble (from the brief, not a public source).

### Inferences
- VRAM ≈ GGUF file size + about 0.5–1.5 GB for KV cache and buffers at short (≤2K-token) prompts. This is a rule of thumb, not measured here. So on 8 GB: Hy-MT2-7B Q6_K fits comfortably, Q8_0 is marginal or spills, TranslateGemma-12B (8.1 GB) and Gemma 4 12B (7.7–8.0 GB) will spill partly to the CPU (slower), and Gemma 4 E4B and Qwen3.5-9B fit.
- On Kaggle 2×T4 (16 GB each):
  - FP16 Hy-MT2-7B (about 16 GB of weights) needs tensor parallel across both T4s, or a single T4 with the Q8_0 GGUF.
  - MiLMMT-46-12B FP16 (about 24 GB) fits on 2×T4.
  - Gemma 4 26B-A4B and 31B, Qwen3.6-27B and TranslateGemma-27B need Q4 GGUF with a layer split across both GPUs.
  - Hy-MT2-30B-A3B is FP8 only officially. T4 (Turing) has no native FP8 or BF16 support (general hardware knowledge, not sourced here), so it would need a community GGUF or FP16 weights larger than 32 GB. Check the Hy-MT2-30B-A3B model tree for community GGUFs first.
  - Gemma-family models in FP16 have historically been prone to overflow. Verify outputs on T4 or prefer the P100/T4 GGUF path. This is unverified here.
- Licence fit for a paid or cloud tier:
  - Apache-2.0 or permissive: Hy-MT2, Gemma 4, Qwen3.5/3.6, Sailor2, and Seed-X (OpenMDW).
  - Gemma Terms (usable commercially, with use-policy conditions): TranslateGemma, MiLMMT-46, GemmaX2.
  - Non-commercial, avoid: Aya, Tiny Aya, North, Sakura.

### Gaps
- No official Ollama library tag for Hy-MT2 or MiLMMT was found. Use `hf.co/...` GGUF pulls and check the chat template and stop tokens.
- I could not confirm whether the standard Hy-MT2 Q4_K_M/Q6_K/Q8_0 files need the STQ kernel. They evidently run in Ollama (META-MARK, and the team's own runs), so the STQ requirement probably applies only to the 2-bit and 1.25-bit files. This is inferred.
- I found no tokens/s figures for TranslateGemma, MiLMMT, Seed-X or Gemma 4 on consumer GPUs.
- The exact Qwen3.6 and Qwen3.8 repo ids and licences were not verified on Hugging Face.

## Q6. Is "OCR → text MT" competitive with "one VLM does both" for small local models? What do manga and subtitle tools use?

### Takeaway
No public study compares a small open VLM end-to-end against OCR plus a small MT model on manga. Indirect evidence points both ways:
- Images help a large model translate manga: GPT-4 Turbo gained +0.6 to +2.9 chrF JA→EN.
- Large closed MLLMs (Gemini 2.5) beat OCR plus a 9B text LLM on synthetic image-text.
- But at small sizes, MT-specialised text models clearly beat general multimodal models on text quality: Hy-MT2-7B scores 86.89 against 79.96 for Gemma4-E4B on XX⇔XX.

Local manga tools mostly use dedicated OCR plus a separate translator: Sugoi for JA→EN, Sakura for JA→ZH, and lately Gemma 4 or Qwen 3.5–3.8 general LLMs via llama.cpp. None ships Vietnamese-specific local MT.

### Cited Findings
- Lippmann et al. (COLING 2025), JA→EN, GPT-4 Turbo:
  - Adding the page image raised line-by-line chrF from 32.7 to 35.6 and page-by-page from 36.0 to 36.6 (xCOMET 0.758 → 0.776).
  - On JA→PL the gain was nil (25.6 vs 25.6).
  - Open multimodal models were left to future work because of their "limited availability and quality".

  Source: [arXiv 2411.02589](https://arxiv.org/html/2411.02589v2)
- Puchol et al. (2026-05-28): docTR OCR plus text models (M2M100-1.2B, Llama-3.x 1–8B, EuroLLM 1.7B/9B) compared with Gemini 2.5 MLLMs on synthetic IWSLT sentence images (en/de/fr). In BLEU, the best pipeline (EuroLLM-9B) against Gemini-2.5-pro was:
  - en→de: 31.2 vs 35.6
  - de→en: 39.1 vs 41.4
  - en→fr: 36.8 vs 44.6
  - fr→en: 37.6 vs 43.5

  No small open VLMs were tested — [alphaXiv 2605.29476](https://www.alphaxiv.org/abs/2605.29476.md)
- Text MT quality, specialised vs general multimodal at small size, on FLORES-200 XX⇔XX XCOMET: Hy-MT2-7B 86.89, Gemma4-E4B 79.96, Gemma4-E2B 75.97 — [arXiv 2605.22064](https://arxiv.org/html/2605.22064v1)
- TranslateGemma also accepts image input. On Vistra (filtered to images with a single piece of text) it scored MetricX 2.57 / 2.08 / 1.57 for 4B / 12B / 27B — [HF translategemma-12b-it](https://huggingface.co/google/translategemma-12b-it)
- manga-image-translator:
  - Offline translators: `offline`, `nllb`, `nllb_big`, `sugoi`, `jparacrawl(_big)`, `m2m100(_big)`, `m2m100_hf(_big)`, `mbart50`, `qwen2(_big)`.
  - It recommends **Sugoi** for JA→EN and **sakura** (or OpenAI) for JA→ZH, and gives no recommendation for other pairs.
  - `custom_openai` defaults to Ollama at `localhost:11434/v1`, with an example model `qwen2.5:7b`.

  Source: [GitHub manga-image-translator](https://github.com/zyddnys/manga-image-translator)
- Koharu (local manga translator):
  - Local GGUF LLM options: LFM 2.5 1.2B, Ministral 3 8B, Gemma 4 (E2B…31B), Qwen 3.5 (0.8B…35B-A3B), Qwen 3.6 (27B, 35B-A3B), Qwen 3.8 27B, plus uncensored variants.
  - OCR options: PaddleOCR-VL 1.6, Manga OCR, Baberu OCR, Hayai OCR.
  - No Hy-MT2 or TranslateGemma.

  Source: [GitHub mayocream/koharu](https://github.com/mayocream/koharu)
- A Korean JA→KO manga app uses BallonsTranslator for detection and OCR, plus llama.cpp `llama-server` with **Gemma 4 E4B** (about 5 GB) for translation. It pre-translates the next pages and needs an RTX 30-series or newer — [GitHub kyj0503/manga-translate](https://github.com/kyj0503/manga-translate)
- LunaTranslator (GPLv3) integrates the SakuraLLM JA→ZH models via the Sakura API. The Sakura models are CC BY-NC-SA 4.0. According to an aggregator, 7B needs about 8–10 GB of VRAM and 14B about 11–24 GB — [SourcePulse (aggregator)](https://www.sourcepulse.org/projects/1832118); [HF SakuraLLM/GalTransl-v1](https://huggingface.co/SakuraLLM/GalTransl-v1)
- On JA→EN quality, dedicated Sugoi beats Google and Papago on VNTL (0.6093 / 0.5395 / 0.4560) — [VNTL README](https://www.huggingface.co/datasets/lmg-anon/vntl-leaderboard/blob/main/README.md?code=true)

### Inferences
- **For local mode on 8 GB, keep the two-stage pipeline:** Japanese OCR (manga-ocr or PaddleOCR-VL) followed by Hy-MT2-7B (Q6_K). A single small VLM (Gemma 4 E4B, Qwen3.5-4B/9B) would likely lose several XCOMET-equivalent points of translation quality. What it would add is visual cues: who speaks, gender, and whether text is SFX or a sign.
- **A hybrid worth testing:** use the small VLM only to propose metadata (speaker, gender, addressee, text type) and feed it to the MT model through Hy-MT2's background or terminology templates. The VLM's suggestions must stay "proposals" under the project's memory rules.
- **Pivoting via English (JA→EN with Sugoi or VNTL, then EN→VI)** is not supported by any evidence found. English discards honorific and register distinctions and the asymmetry Vietnamese pronouns need (anh/em, tớ/cậu, tao/mày). It also doubles latency. Hy-MT2 is trained for direct non-English pairs, where its strength is measured (XX⇔XX). Pivoting is not recommended except as an experiment.
- None of the local manga tools surveyed ships a Vietnamese-tuned local MT. Hy-MT2 with a ja→vi glossary would be a differentiator. Koharu and the Korean app show the community trend toward Gemma 4 E4B and Qwen 3.5+ GGUF via llama.cpp, not dedicated MT models.

### Gaps
- No manga or comic benchmark for Japanese→Vietnamese exists in the sources found. I found no OCR-pipeline vs small-open-VLM comparison on manga, and no evidence on whether giving page images to a small VLM improves pronoun or gender choices.
- LunaTranslator's and BallonsTranslator's own documentation on recommended local LLMs was not reached; only aggregator or review summaries were found.
- I found no Vietnamese community (manga or light-novel translator) reports comparing local models for JA→VI. Vietnamese searches returned only generic "local LLM" articles.
