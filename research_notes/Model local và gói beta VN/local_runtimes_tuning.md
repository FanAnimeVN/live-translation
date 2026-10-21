# Local inference runtimes, in-browser inference and tuning for manga OCR + JA→VI translation on consumer hardware (as of 21 Oct 2026)

Scope: which local runtime(s) the extension's "local mode" should support, realistic speeds on the target hardware
(RTX 3050/4050/4060 6–8 GB laptops, RTX 3060 12 GB / 4060 Ti 16 GB desktops, M1–M4 Macs, iGPU-only laptops),
concrete tuning settings, and whether a Chrome/Edge MV3 extension can do OCR + translation fully in the browser.
Internal project facts are cited with relative links to this repo (from `research_notes/Model local và gói beta VN/`).
Note on method: the shared web-search budget for this session ran out near the end, so a few items that needed
one more search are listed as gaps instead of being filled from memory.

## 1. Which runtime(s) to support: vision support, OpenAI-compatible endpoints, structured output, parallelism, memory knobs, CORS, Windows install, phone-home behaviour

### Takeaway
Ollama (v0.40.7, 18 Oct 2026) is still the best primary target. It installs without admin rights, ships Qwen3-VL / Qwen3.5 / Gemma 4 vision models as one-command pulls, and runs on llama.cpp (and on MLX on Apple Silicon). It has two traps for an extension. It returns 403 to `chrome-extension://` origins unless `OLLAMA_ORIGINS` is set or the Origin header is rewritten. Its OpenAI-compatible endpoint cannot set `num_ctx`, while the default context on <24 GiB VRAM is only 4k. llama-server is the most controllable runtime and works best as a power-user or bundled option: JSON-schema output, `--image-max-tokens`, `--offline`, automatic memory fitting, and CORS that echoes any origin. LM Studio and KoboldCpp are worth supporting through a generic OpenAI-compatible adapter. vLLM/SGLang are not realistic for Windows consumer installs.

### Cited Findings

**Ollama: versions and engine**
- Latest release is v0.40.7 (18 Oct 2026). v0.40.0 (25 Sep 2026) made "Models run on MLX on Apple Silicon by default" for supported architectures, and added Qwen 3.8, Gemma 4, Qwen 3.6 and Qwen 3.5 on MLX. v0.40.4 (12 Oct) added multimodal embeddings "via llama-server" and improved Gemma 4 prefill on NVIDIA GPUs with MLX. v0.40.7 notes speculative decoding drafts "in llama-server". The listing order on the page does not match chronology: v0.35.x carries late-September dates after v0.40.0. — [Ollama releases](https://github.com/ollama/ollama/releases)
- v0.30.0 (13 May 2026) brought "improved compatibility and performance using llama.cpp", augmenting the MLX engine. It also added support for GGUF models from Hugging Face and own fine-tunes, and faster NVIDIA performance. Known issue at the time: `llama3.2-vision` not yet supported. — [Ollama v0.30.0](https://github.com/ollama/ollama/releases/tag/v0.30.0). A secondary feed dates a v0.30.0 pre-release to 22 May 2026, a minor conflict. — [Releasebot](https://releasebot.io/updates/ollama)
- v0.40.2 (8 Oct 2026) upgrades previously downloaded models in the background on first run "for better llama.cpp compatibility" and keeps backups on disk. Downgrading below 0.40 requires re-pulling. v0.40.3 paused background upgrades to improve request performance. — [Ollama releases](https://github.com/ollama/ollama/releases)
- Ollama's env config now includes llama.cpp knobs `LLAMA_ARG_FIT` (documented default "on") and `LLAMA_ARG_FIT_TARGET` (free-VRAM margin per device, MiB). It also has `OLLAMA_GPU_OVERHEAD` (VRAM reserved per GPU, bytes), `OLLAMA_VULKAN` (default true on non-macOS) and `OLLAMA_IGPU_ENABLE` (allow integrated GPUs). — [ollama envconfig/config.go](https://raw.githubusercontent.com/ollama/ollama/main/envconfig/config.go)

**Ollama: vision models available as pulls (download sizes, all text+image input)**
- qwen3-vl: 2b 1.9 GB (q8_0 2.7 GB), 4b 3.3 GB (q8_0 5.1 GB), 8b 6.2 GB (q8_0 9.9 GB), 30b-a3b 20 GB, 32b 21 GB. Context 256K. Instruct and thinking variants. — [ollama.com qwen3-vl tags](https://ollama.com/library/qwen3-vl/tags)
- qwen3.5 (natively multimodal): 0.8b ≈1.0–1.3 GB, 2b q4_K_M 1.9 GB, 4b q4_K_M 3.3 GB, 9b q4_K_M 6.6 GB (q8_0 10 GB), 27b q4_K_M 17 GB, 35b-a3b q4_K_M 22 GB, 122b-a10b 81 GB. Context 256K. Text+image. — [ollama.com qwen3.5 tags](https://ollama.com/library/qwen3.5/tags)
- gemma4: e2b q4_K_M 4.6 GB (qat 4.3 GB), e4b q4_K_M 6.6 GB (qat 6.1 GB), 12b q4_K_M 8.0 GB (qat 7.2 GB), 26b-a4b q4_K_M 18 GB, 31b q4_K_M 20 GB. E2B/E4B have 128K context, the others 256K. Text+image. Separate `-mlx`, `-nvfp4` and `-mxfp8` tags are MLX builds. — [ollama.com gemma4 tags](https://ollama.com/library/gemma4/tags)

**Ollama: API surface**
- The OpenAI-compatible API offers `/v1/chat/completions`, `/v1/completions`, `/v1/models`, `/v1/embeddings` and `/v1/responses` (the last added in v0.13.3). Images must be base64; image URLs are unsupported. `response_format`/JSON mode is supported. `tool_choice`, `logit_bias`, `n` and logprobs are unsupported. "The OpenAI API does not have a way of setting the context size"; the workaround is a Modelfile with `PARAMETER num_ctx`. — [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)
- Default context is 4k when VRAM <24 GiB, 32k at 24–48 GiB and 256k at ≥48 GiB. Override with the app slider or `OLLAMA_CONTEXT_LENGTH`. `ollama ps` shows CONTEXT and the CPU/GPU split in PROCESSOR. The docs advise avoiding CPU offload for best performance. — [Ollama context length](https://docs.ollama.com/context-length). The FAQ states a flat 4096 default, which matches for all target hardware (<24 GiB). — [Ollama FAQ](https://docs.ollama.com/faq)

**Ollama: memory and concurrency knobs**
- `OLLAMA_KEEP_ALIVE` defaults to 5 min. Negative means keep loaded; 0 unloads immediately; per-request `keep_alive` overrides it. — [Ollama FAQ](https://docs.ollama.com/faq); [config.go](https://raw.githubusercontent.com/ollama/ollama/main/envconfig/config.go)
- `OLLAMA_NUM_PARALLEL` defaults to 1. Per the FAQ, "Required RAM will scale by OLLAMA_NUM_PARALLEL * OLLAMA_CONTEXT_LENGTH". `OLLAMA_MAX_LOADED_MODELS` defaults to 3× the number of GPUs (3 on CPU). `OLLAMA_MAX_QUEUE` is 512, after which requests get 503. — [Ollama FAQ](https://docs.ollama.com/faq)
- Flash attention is used automatically when supported; `OLLAMA_FLASH_ATTENTION=1/0` forces it. The env var's code default is `false`, so "auto" is the runtime behaviour per the FAQ. — [Ollama FAQ](https://docs.ollama.com/faq); [config.go](https://raw.githubusercontent.com/ollama/ollama/main/envconfig/config.go)
- `OLLAMA_KV_CACHE_TYPE` defaults to f16. q8_0 uses about ½ the memory with very small precision loss; q4_0 uses about ¼ with small-to-medium loss. It is global for all models and requires flash attention. — [Ollama FAQ](https://docs.ollama.com/faq)

**Ollama: CORS and browser-extension access**
- Default allowed origins are localhost, 127.0.0.1 and 0.0.0.0 (http/https, any port), plus `app://*`, `file://*`, `tauri://*`, `vscode-webview://*` and `vscode-file://*`. `chrome-extension://` is not included. — [config.go](https://raw.githubusercontent.com/ollama/ollama/main/envconfig/config.go)
- The FAQ's fix is `OLLAMA_ORIGINS=chrome-extension://*,moz-extension://*,safari-web-extension://*`. — [Ollama FAQ](https://docs.ollama.com/faq)
- Page Assist, a widely used Ollama browser extension, rewrites the Origin header so Ollama does not return 403. The rewrite only works for `http://127.0.0.1:*` and `http://localhost:*`, can conflict with some sites, and falls back to `OLLAMA_ORIGINS`. — [Page Assist docs: connection issues](https://www.mintlify.com/n4ze3m/page-assist/troubleshooting/connection-issues); [extension conflicts](https://www.mintlify.com/n4ze3m/page-assist/troubleshooting/extension-conflicts). These are third-party-hosted docs and do not name the mechanism (likely declarativeNetRequest).
- `OLLAMA_HOST` defaults to `127.0.0.1:11434`. — [config.go](https://raw.githubusercontent.com/ollama/ollama/main/envconfig/config.go)

**Ollama: Windows install**
- Requires Windows 10 22H2+ and an NVIDIA driver ≥551.61. AMD needs a ROCm v7 or Vulkan driver; Vulkan is on by default. On mixed iGPU/dGPU systems set `GGML_VK_VISIBLE_DEVICES`. The installer needs no admin rights, installs to the home directory (`OllamaSetup.exe /DIR=...` to relocate) and needs ≥4 GB for binaries.
- A standalone `ollama-windows-amd64.zip` runs `ollama serve` without the tray app. Add-on zips exist for ROCm and for "MLX (CUDA)".
- Logs are in `%LOCALAPPDATA%\Ollama` (`app.log`, `server.log`, `upgrade.log`). Env vars are set in Windows settings, then the tray app is restarted. — [Ollama Windows docs](https://docs.ollama.com/windows)
- Models are stored at `C:\Users\%username%\.ollama\models` and relocated with `OLLAMA_MODELS`. — [Ollama FAQ](https://docs.ollama.com/faq). The dev machine already keeps models on `D:\ollama_models` because C: had only ~4.8 GB free. — [docs/DIRECTION.md](../../docs/DIRECTION.md)

**llama.cpp `llama-server` (ggml-org master, Oct 2026)**
- Key defaults:
  - `--ctx-size` default 0 = loaded from the model.
  - `-np/--parallel` default -1 (auto); continuous batching is on by default.
  - `-fa` on|off|auto, default auto.
  - `--cache-type-k/-v` default f16; options are f32, f16, bf16, q8_0, q4_0, q4_1, iq4_nl, q5_0 and q5_1.
  - `--fit` default on: it adjusts unset arguments to fit device memory, with `--fit-target` 1024 MiB margin per device and `--fit-ctx` minimum 4096.
  - `-ngl` default auto; `--cpu-moe` and `--n-cpu-moe N` keep MoE expert weights on the CPU.
  - `--jinja` default on; `--reasoning-budget` default -1. — [llama-server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- Vision:
  - `--mmproj` loads the projector; `--mmproj-auto` is on by default (useful with `-hf`).
  - `--mmproj-offload` is on by default.
  - `--image-min-tokens` / `--image-max-tokens` cap visual tokens for dynamic-resolution models; default comes from the model.
  - Images arrive as base64, a data URI, a remote URL, or a local file with `--media-path`. — [llama-server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- Structured output: `/v1/chat/completions` accepts `response_format` with a JSON schema. `/completion` accepts `json_schema` and GBNF `grammar`. — [llama-server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- CORS: by default the server "reflects any Origin header back with credentials allowed" (`--cors-origins` default `*`). The default narrows to localhost when `--tools`/`--agent` is enabled. — [llama-server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- Network: `-hf` downloads from Hugging Face (Q4_K_M by default). `--offline` forces the cache and blocks network. — [llama-server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- Router mode, `/health` and web UI:
  - Router mode uses `--models-dir`/`--models-preset`. `--models-max` defaults to 4. `--models-autoload` is on. `--sleep-idle-seconds` defaults to -1 (no idle sleep).
  - `/health` returns 503 "Loading model" until ready.
  - The web UI is on by default (`--no-ui`). — [llama-server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- Supported VLMs with ggml-org pre-quantized repos: Gemma 3 (4B/12B/27B), Gemma 4 (E2B/E4B/26B-A4B/31B), Qwen2-VL, Qwen2.5-VL (3B/7B/32B/72B), InternVL 2.5/3, SmolVLM, Pixtral 12B, Mistral Small 3.1, Llama 4 Scout and Moondream2. Gemma 4 E2B/E4B and Qwen3-Omni also take audio.
  - OCR-specialised models (PaddleOCR-VL, GLM-OCR, DeepSeek-OCR, Dots.OCR, HunyuanOCR) are covered in linked discussions and need model-specific prompts.
  - Some VLMs need a larger context, e.g. `-c 8192`. — [llama.cpp multimodal.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md)
- Qwen3.5 vision does run in llama-server: a May 2026 issue used Qwen3.5-9B-Q4_K_M with a BF16 mmproj. That issue is also a cautionary tale. The reporter saw "image slice encoded in 82047 ms" on a 7900 XTX (flash-attn off). The maintainer closed it as a user-side configuration problem, with no root cause recorded. — [llama.cpp #22582](https://github.com/ggml-org/llama.cpp/issues/22582)

**LM Studio**
- 0.4.0 (28 Jan 2026) added:
  - Parallel requests to one model with continuous batching, 4 slots by default ("Max Concurrent Predictions").
  - `llmster`, a GUI-less server-native daemon (`lms daemon up`, `lms server start`).
  - A stateful REST `/v1/chat`. — [LM Studio 0.4.0 blog](https://lmstudio.ai/blog/0.4.0); [changelog](https://lmstudio.ai/changelog/lmstudio-v0.4.0)
- Parallel requests need the llama.cpp engine runtime v2.0.0; the docs still say MLX support is "coming soon". — [LM Studio parallel requests](https://lmstudio.ai/docs/app/advanced/parallel-requests). A secondary guide claims 0.4.2 added MLX parallel, which conflicts with the docs. — [InsiderLLM](https://insiderllm.com/guides/lm-studio-tips-tricks/)
- Base URL is `http://localhost:1234/v1` (default port 1234). Endpoints: `/v1/models`, `/v1/chat/completions` (text + images), `/v1/responses`, `/v1/embeddings`, `/v1/completions` and `/v1/decisions`. — [LM Studio OpenAI compat](https://lmstudio.ai/docs/developer/openai-compat). A Structured Output doc page exists in the developer docs. — [LM Studio server docs](https://lmstudio.ai/docs/developer/core/server)
- Server settings include an "Enable CORS" switch (default not stated), Serve on Local Network, Require Authentication, Just-in-Time model loading, Auto Unload Unused JIT Models and Only Keep Last JIT Loaded Model. — [LM Studio server settings](https://lmstudio.ai/docs/developer/core/server/settings)

**KoboldCpp**
- Single-file Windows builds: `koboldcpp.exe` (CUDA), a smaller `koboldcpp-nocuda.exe` (CPU+Vulkan) and `koboldcpp-oldpc.exe`. Default `http://localhost:5001`, with an OpenAI-compatible base at `/v1`.
  - It also emulates the Ollama, KoboldAI, Anthropic, A1111, ComfyUI and XTTS APIs.
  - Vision works via `--mmproj`; the README's examples are Qwen3-VL-8B and Gemma3-4B. `--usevulkan` covers AMD/NVIDIA/Intel GPUs.
  - The README does not document CORS, grammar/JSON schema or parallelism. — [KoboldCpp README](https://github.com/LostRuins/koboldcpp)

**MLX / mlx-vlm (Apple)**
- Supported families: Qwen2/2.5/3-VL, Qwen3.5, Qwen3.8, Gemma 4 (E2B/E4B/26B-A4B/31B), gemma-3n, PaddleOCR-VL, DeepSeek-OCR, GLM-OCR, Moondream, Phi-4 and others.
- `mlx_vlm.server` is OpenAI-compatible (`/v1/chat/completions`, `/v1/responses`, `/v1/models`, `/health`). It defaults to port 8080 on host 0.0.0.0, i.e. all interfaces.
- Supports `json_schema` structured outputs and KV-cache quantisation (`--kv-bits` 8, TurboQuant 2–4 bit).
- Models come from the Hugging Face hub (`HF_HOME`/`HF_HUB_CACHE`); offline operation is not documented. — [mlx-vlm README](https://github.com/Blaizzy/mlx-vlm)

**vLLM / SGLang**
- Official vLLM still lists no native Windows support; WSL2 is the recommended route. Docker Model Runner added vLLM on Windows through a WSL2 backend (Dec 2025; Docker Desktop 4.54+; NVIDIA GPU compute capability ≥8.0). Native Windows builds exist only as unofficial community forks. — [fazm.ai summary](https://fazm.ai/t/vllm-windows-support-2026); [dasroot.net](https://dasroot.net/posts/2026/05/run-vllm-natively-windows-without-wsl/); [Docker blog](https://www.docker.com/?p=83736) (secondary sources)

**Phone-home behaviour after models are installed**
- Ollama:
  - Auto-downloads updates on macOS and Windows. — [Ollama FAQ](https://docs.ollama.com/faq)
  - Cloud models and web search can be disabled with `OLLAMA_NO_CLOUD=1` or `"disable_ollama_cloud": true` in `~/.ollama/server.json`; logs then show "Ollama cloud disabled: true". — [Ollama FAQ](https://docs.ollama.com/faq); [config.go](https://raw.githubusercontent.com/ollama/ollama/main/envconfig/config.go)
  - `OLLAMA_REMOTES` defaults to `ollama.com`. — [config.go](https://raw.githubusercontent.com/ollama/ollama/main/envconfig/config.go)
  - Recent releases add cloud "decision models" (e.g. `clef:cloud`) and cancel remote-model requests on ollama.com when the client disconnects. — [Ollama releases](https://github.com/ollama/ollama/releases)
  - No documented switch to turn off auto-update was found.
- LM Studio:
  - Chat, RAG and the local server work offline.
  - Model search (huggingface.co), downloads, catalog stats and LM Runtime update checks need the network. The app checks for updates on open on macOS/Windows.
  - No documented toggle to disable update checks; the page makes no telemetry statement. — [LM Studio offline docs](https://lmstudio.ai/docs/app/offline)
- llama.cpp: network is used only for `-hf` downloads; `--offline` blocks it. — [llama-server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- KoboldCpp: its README mentions only user-initiated HF downloads and optional remote providers. — [KoboldCpp README](https://github.com/LostRuins/koboldcpp)

### Inferences
- Primary runtime: Ollama. It is the only option that combines no-admin install, auto-detected GPUs (CUDA, ROCm, Vulkan incl. opt-in iGPU), MLX on Mac and a curated VLM library. Treat LM Studio, llama-server and KoboldCpp as "OpenAI-compatible local server" adapters with capability probing (`/v1/models`, a test image request).
- Context-length trap: on every target machine Ollama's default context is 4k. A full manga page sent to Qwen3-VL is ~2–5k image tokens (see §2), so it can blow past 4k before the prompt and JSON output are added. The OpenAI-compatible endpoint cannot raise `num_ctx`. Local mode should therefore either:
  - call Ollama's native `/api/chat` with per-request options (needs verification, see Gaps), or
  - ask the user to set `OLLAMA_CONTEXT_LENGTH` (e.g. 8192), or
  - send bubble crops instead of full pages.
- Extension access to Ollama without asking users to edit env vars is feasible: rewrite or strip the Origin header for `127.0.0.1:11434` only, as Page Assist does. Keep a documented `OLLAMA_ORIGINS=chrome-extension://<our-id>` fallback for users whose other extensions conflict.
- llama-server echoes any Origin with credentials. If we ever bundle or recommend it, any website could call it unless Chrome's Local Network Access prompt intervenes (§3). Prefer binding to 127.0.0.1 with `--api-key`, or `--cors-origins chrome-extension://<id>`. mlx_vlm.server binds 0.0.0.0 by default, so recommend `--host 127.0.0.1`.
- For strict offline guidance, tell users to set `OLLAMA_NO_CLOUD=1`. The Ollama app's own auto-update is a network call by the runtime, not by our product, but it should be disclosed. Running the standalone zip with `ollama serve` probably avoids the tray-app updater (unverified).
- vLLM/SGLang add nothing for single-user 6–8 GB laptops and their Windows story is WSL-only; skip them for local mode.

### Gaps
- Not re-verified in this pass:
  - Native Ollama `/api/chat` `format` accepting a full JSON schema, per-request `options.num_ctx`, and pull-progress streaming.
  - Whether the OpenAI-compat `response_format` accepts `json_schema` (the docs page only says "JSON mode").
- No documented way to disable Ollama's or LM Studio's auto-update checks was found.
- LM Studio's CORS default and its structured-output details were not extracted. KoboldCpp CORS, grammar and parallel behaviour are not on its README.
- SGLang Windows status was not found.
- Exact Windows installer sizes (OllamaSetup.exe, LM Studio, KoboldCpp exe) were not found.

## 2. Measured speeds on target hardware; image resolution vs OCR accuracy and latency; partial-offload costs

### Takeaway
Text generation on target GPUs is roughly 40–75 tok/s for a 7B Q4 model: RTX 3050 ≈38, RTX 4050 Laptop ≈44, T4 ≈45, RTX 4060 Ti ≈64, RTX 3060 12 GB ≈77. Prompt processing runs about 1,200–3,800 tok/s. On base M-series Macs (llama.cpp, 2023 build) it is roughly 14–24 tok/s generation and 120–220 tok/s prompt processing. Page-level VLM calls are therefore dominated by output tokens on NVIDIA and by image-token prefill on base Macs and iGPUs. Image cost is predictable: Qwen3-VL uses ≈1 token per 32×32 px, Gemma 4 uses fixed budgets of 70–1,120 tokens. No reliable published OCR-accuracy-vs-resolution numbers exist for Japanese manga, so this must be measured on the local GT set. Anything that spills out of 8 GB VRAM (dense 12B, Qwen3-VL-8B at large context, two models at once) falls off a cliff. MoE models with expert offload are the exception.

### Cited Findings

**llama.cpp CUDA scoreboard** (Llama 2 7B Q4_0, `llama-bench -ngl 99`, pp512 / tg128 in tok/s) — [llama.cpp discussion #15013](https://github.com/ggml-org/llama.cpp/discussions/15013)

| GPU | FA off pp512 / tg128 | FA on pp512 / tg128 | Notes |
|---|---|---|---|
| RTX 3050 6 GB | 1,147 / 37.4 | 1,258 / 38.5 | 15 Jul 2026 |
| RTX 4050 Laptop 6 GB | 1,726 ± 18 / 43.7 ± 0.4 | — | |
| Tesla T4 | 1,219 / 46.4 | 1,310 / 44.0 | |
| RTX 3060 12 GB | 2,138 / 75.6 | 2,408 / 76.9 | WSL2 run: 2,408 / 75.6 FA on (21 Aug 2026) |
| RTX 4060 Ti 8 GB | 3,395 / 63.9 | 3,803 / 64.0 | |
| RTX 3080 Laptop | 2,875 / 90.6 | 3,275 / 93.4 | 8 Aug 2026 |
| RTX 3080 10 GB | 5,014 / 139.7 | 5,570 / 140.0 | |

The page has no rows for RTX 4060 Laptop, RTX 4060 desktop, RTX 4070 or RTX 3070.

**llama.cpp Apple Silicon table** (LLaMA 7B, `-ngl 99`, PP512 / TG128 tok/s). These are OUTDATED: measured at commit 8e672ef (21 Nov 2023), before later Metal speedups, and Ollama now defaults to MLX on Apple Silicon. — [llama.cpp discussion #4167](https://github.com/ggml-org/llama.cpp/discussions/4167)

| Chip (GPU cores) | Memory bandwidth | Q4_0 PP / TG | Q8_0 PP / TG |
|---|---|---|---|
| M1 (8) | 68 GB/s | 118 / 14.2 | 117 / 7.9 |
| M2 (10) | 100 GB/s | 180 / 21.9 | 181 / 12.2 |
| M3 (10) | 100 GB/s | 187 / 21.3 | 188 / 12.3 |
| M4 (10) | 120 GB/s | 221 / 24.1 | 224 / 13.5 |
| M3 Pro (18) | 150 GB/s | 342 / 30.7 | — |
| M2 Pro (19) | 200 GB/s | 341 / 38.9 | — |
| M4 Pro (20) | 273 GB/s | 440 / 50.7 | 450 / 30.7 |

**Other speed data**
- mlx-vlm reports Gemma 4 26B-A4B at ~50 tok/s at 20K context (chip unnamed). Vision-feature caching raised prompt processing from ~48 to 550–825 tok/s over multi-turn chats. — [mlx-vlm README](https://github.com/Blaizzy/mlx-vlm)
- Project measurement on the dev machine (RTX 4060 Laptop 8 GB, Ollama, 120 bubbles of perfect-OCR Japanese text, 19–20 Oct 2026):

  | Model | Size | chrF | Time per bubble |
  |---|---|---|---|
  | Hy-MT2 7B Q4 | 4.6 GB | 33.8 | 0.40 s |
  | Hy-MT2 1.8B Q6 | 1.5 GB | 26.9 | 0.19 s |
  | Qwen3 4B Instruct 2507 Q4 | 2.5 GB | 24.4 | 0.19 s |
  | Claude Haiku 5.5 (cloud reference) | — | 38.7 | 1.5 s |
  | Gemma 4 E2B as image reader | 7.2 GB | — | 7–9 s per panel |

  Gemma 4 E2B was rejected because it invented text not on the page. — [docs/DIRECTION.md](../../docs/DIRECTION.md)
- A desktop RTX 4060 page reports LLaMA 3 8B Q4_K_M at only 18 tok/s single-stream. It is marked historical with loose test conditions, and it is inconsistent with the scoreboard above, where a 4060 Ti 8 GB does 64 tok/s on 7B Q4_0. Treat it as low quality. — [GigaGPU](https://gigagpu.com/?p=11102)

**Image tokens and resolution**
- Qwen3-VL:
  - Patch 16 with 32× compression, so each image token covers ≈32×32 px.
  - Resolution is set per input via `min_pixels`/`max_pixels` or `resized_height`/`resized_width` in qwen-vl-utils. Sides are rounded to multiples of 32 (28 for Qwen2.5-VL).
  - The repo's example budget is 256–1,280 tokens per image (`shortest_edge=256×32×32`, `longest_edge=1280×32×32`). — [Qwen3-VL GitHub](https://github.com/QwenLM/Qwen3-VL)
  - Release dates: 235B-A22B 23 Sep 2025, 30B-A3B 4 Oct, 4B/8B 15 Oct, 2B/32B 21 Oct 2025. — [Qwen3-VL GitHub](https://github.com/QwenLM/Qwen3-VL)
  - OCR claims: 32 languages, robust to low light, blur and tilt. Japanese and vertical text are not specifically claimed. — [Qwen3-VL-8B model card](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)
- Gemma 4:
  - Vision token budgets of 70, 140, 280, 560 or 1,120; higher budgets are recommended for OCR, document parsing and small text. Resolution is controlled through the budget.
  - Sizes: E2B (2.3B effective, 5.1B with embeddings), E4B (4.5B effective / 8B), "12B Unified" (11.95B, encoder-free), 26B A4B MoE (3.8B active) and 31B dense.
  - Context is 128K for E2B/E4B and 256K for the rest. 35+ languages out of the box (140+ in pre-training). Apache-2.0.
  - Model card last updated 30 Jul 2026. — [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)
  - A secondary source dates the release to 2 Apr 2026 with a 4-model lineup; the 12B appears to be a later addition. — [buildfastwithai](https://www.buildfastwithai.com/blogs/google-gemma-4-open-model)
- llama.cpp:
  - `--image-min-tokens` / `--image-max-tokens` cap tokens for dynamic-resolution VLMs. — [llama-server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
  - A 2025 PR added a hard image-resolution limit for qwen2vl/qwen2.5vl in mtmd. — [PR #13434 (mirror)](https://app.semanticdiff.com/gh/ggml-org/llama.cpp/pull/13434/overview)
- Token budget vs OCR accuracy (the only quantitative curve found, English documents only):
  - DeepSeek-OCR reports ≈97% decoding precision when text tokens are ≤10× vision tokens, and ≈60% at 20× (Fox benchmark, 600–1,300-token English pages). — [DeepSeek-OCR, arXiv 2510.18234](https://arxiv.org/pdf/2510.18234v1)
  - A secondary summary gives 96.5% at 10.5× with 64 vision tokens. — [themoonlight review](https://www.themoonlight.io/review/deepseek-ocr-contexts-optical-compression)

**Partial offload and VRAM spill**
- Ollama says to avoid CPU offload for best performance. `ollama ps` shows splits such as "48%/52% CPU/GPU". — [Ollama context length](https://docs.ollama.com/context-length); [Ollama FAQ](https://docs.ollama.com/faq)
- MoE expert offload anecdotes (community, not controlled):
  - Qwen3.6-35B-A3B on an 8 GB RTX 3070 Ti went from 8.7 to >40 tok/s after adding `-ncmoe`. — [Medium](https://medium.com/coding-nexus/one-flag-tripled-my-tokens-per-second-on-an-8gb-gpu-238f55d1e3bd)
  - 30–35 tok/s with `--n-cpu-moe` on 8 GB VRAM + DDR5. — [Reddit snapshots](https://reddit.sentinel-team.org/posts/1t7l56a/snapshots/2026-05-15T23%3A40%3A01.25497Z), [2](https://reddit.sentinel-team.org/posts/1w36khs/snapshots/2026-09-04T21%3A20%3A12.3645Z)
  - ≈46.8 tok/s tg128 with `-ncmoe 18` on an RTX 3060 12 GB + 32 GB DDR4. — same snapshots
  - 30B-A3B needs ~20 GB at Q4 because memory follows total, not active, parameters. — [llmhardware.io](https://llmhardware.io/guides/qwen3-hardware-requirements); the qwen3-vl:30b q4_K_M pull is 20 GB. — [ollama tags](https://ollama.com/library/qwen3-vl/tags)
  - The same threads say running a dense 27B model partly in RAM on 8 GB VRAM + 16 GB RAM is "painfully slow". — [Reddit snapshot](https://reddit.sentinel-team.org/posts/1w36khs/snapshots/2026-09-04T21%3A20%3A12.3645Z)
- Windows "shared GPU memory" spill: third-party guides describe the NVIDIA control-panel "CUDA – Sysmem Fallback Policy: Prefer No Sysmem Fallback". It turns silent slowdowns into CUDA OOM errors. The guides also note that the KV cache is allocated for the full context up front and that `ollama ps` PROCESSOR identifies placement problems. — [llmconfigurator](https://llmconfigurator.com/en/guides/troubleshooting/windows-shared-gpu-memory-slow); [runaihome](https://runaihome.com/blog/shared-gpu-memory-slow-local-ai-sysmem-fallback-fix-2026/) (not official NVIDIA documentation)

### Inferences
- Image-token arithmetic for Qwen3-VL at ≈32×32 px per token:
  - A 1,200×1,800 page is ≈38×56 ≈ 2,100 tokens; a 1,600×2,400 page is 50×75 = 3,750 tokens.
  - Qwen2.5-VL at 28 px: the 1,600×2,400 page is ≈57×86 ≈ 4,900 tokens.
  - A 384×768 bubble crop is 12×24 = 288 tokens.
  - Capping a full page at Qwen's example 1,280 tokens shrinks it to ≈1.3 MP (≈930×1,400 for 2:3). Furigana, small SFX and handwritten asides are likely to degrade. Crops keep native resolution at a fraction of the tokens.
- Gemma 4's maximum of 1,120 tokens per image means a whole page is always heavily compressed. For small text, crop regions rather than sending pages.
- Prefill at 7B-class pp512 rates (scales roughly with model size; long prompts run slower than pp512):

  | Hardware | pp512 rate (FA on) | ~3,750-token page |
  |---|---|---|
  | RTX 3060 / 4060 Ti | 2,400–3,800 tok/s | ≈1–1.6 s |
  | RTX 3050 / T4 | ~1,260–1,310 tok/s | ≈3 s |
  | M2 / M4 base (2023 build) | 180–220 tok/s | ≈17–21 s |

  Vision-encoder time comes on top and is unmeasured.
- Output dominates on NVIDIA: 600–900 JSON output tokens per page at 40–65 tok/s is ≈10–20 s. Practical levers are fewer output tokens (no "thinking" mode, compact JSON keys, no restating the input) more than smaller images. This matches the project's 7–9 s per panel for Gemma 4 E2B on the 4060 Laptop.
- Without a 4060 Laptop row, a reasonable working assumption is tg ≈ 45–60 tok/s for 7–8B Q4. Laptop 4060s share the 8 GB/128-bit design but have lower power limits and fall between the 4050 Laptop (43.7) and the 4060 Ti (64). Confirm with `llama-bench` on the dev machine.
- The DeepSeek-OCR curve suggests token budget is rarely the binding constraint for short bubble text: 30 Japanese characters need only a few dozen vision tokens. The binding constraint is per-glyph pixel size, which favours crops at native resolution over downscaled pages.

### Gaps
- No reliable published numbers for VLM image-encode latency (Qwen3-VL / Qwen3.5 / Gemma 4 mmproj) on RTX 4060 / 3060 / 4070 / T4 or M-series. No published OCR-accuracy-vs-`max_pixels` study for Japanese manga or vertical text.
- Measurement to run on the dev machine:
  - Settings: `llama-server` timings or `ollama run --verbose`, image-token caps of 256/512/1,024/2,048 on the private 10-page GT set (crops vs full pages).
  - Report: character error rate, latency, cold vs warm.
- No RTX 4060 Laptop / RTX 4070 rows in the llama.cpp scoreboard. The Apple numbers come from a 2023 build. No controlled measurements of dense-model partial offload on 8 GB + 16 GB RAM were found, only anecdotes.

## 3. Can the extension run OCR and translation fully in the browser? (WebLLM, transformers.js / ONNX Runtime Web, Chrome / Edge built-in AI, MV3 constraints)

### Takeaway
Partly. Detection, inpainting and a classic OCR model (manga-ocr or PaddleOCR rec) run well in-browser on WebGPU via ONNX Runtime Web; the project already runs inpainting this way, and Kites does OCR this way. Chrome's built-in Translator API lists both `ja` and `vi` (Chrome 138+ stable, desktop only), which makes a zero-install JA→VI text path possible with unmeasured quality. Gemini Nano's Prompt API does not support Vietnamese output and Edge's Prompt API is still Canary/Dev-only. WebLLM runs 4–9B text LLMs (Qwen3/Qwen3.5) at 3.4–5.7 GB VRAM but its only VLM is Phi-3.5-vision. Transformers.js v4 can run Qwen3-VL/Qwen3.5/Gemma 4 VLMs but with no published speeds. MV3 constraints are manageable: WebGPU works in service workers (Chrome 124+), but those workers have 30 s idle and fetch timeouts. Plan for an offscreen document, `wasm-unsafe-eval`, bundled runtime files and `unlimitedStorage`.

### Cited Findings

**WebLLM (MLC)**
- The prebuilt model list includes:
  - Text: Qwen3.5 0.8B/2B/4B/9B, Qwen3 0.6–8B, Qwen2.5 0.5–7B, Llama 3.1/3.2, Phi-4-mini, gemma-2-2b-jpn, gemma3-1b, Ministral 3 3B.
  - `gemma-4-E2B-it` (q4f16 3,387 MB VRAM, requires `shader-f16`; q4f32 3,863 MB).
  - The only `ModelType.VLM` entries are Phi-3.5-vision-instruct (q4f16 4,522 MB; q4f32 7,051 MB; 4k context).
- VRAM: Qwen3-4B q4f16 3,432 MB; Qwen3-8B q4f16 5,696 MB; Qwen2.5-7B q4f16 5,107 MB; Llama-3.1-8B q4f16 5,001 MB.
- Most models default to a 4,096 context; Qwen3.5 entries use `max_history_size: 1`. — [WebLLM config.ts](https://github.com/mlc-ai/web-llm/blob/main/src/config.ts)
- WebLLM claims it can "retain up to 80% native performance on the same device" (paper v2, revised 13 Apr 2026). — [arXiv 2412.15803](https://arxiv.org/abs/2412.15803)
- Extension integration: a service-worker engine with heartbeat keep-alive (`keepAliveMs`, `missedHeartbeat`). The docs warn Chrome can still kill the worker. Samples exist in `examples/chrome-extension` and `chrome-extension-webgpu-service-worker`. — [WebLLM advanced usage](https://webllm.mlc.ai/docs/user/advanced_usage.html)

**Transformers.js / ONNX Runtime Web**
- v4.0.0 (30 Mar 2026):
  - New WebGPU runtime "completely rewritten in C++" with the ORT team; runs in browsers and Node/Bun/Deno.
  - Models >8B; ~4× faster BERT embeddings; GPT-OSS 20B q4f16 ≈60 tok/s on an "M4 Pro Max" (as written).
  - `env.useWasmCache` for offline after first load; `ModelRegistry` for cache status.
  - Added Qwen2.5-VL, Qwen3-VL, Qwen3.5, Gemma 3 VLM, LightOnOCR, GLM-OCR and LFM2-VL.
- Later releases: v4.0.1/4.1.0 added Gemma 4 and q1/q2 dtypes; 4.1.0 re-enabled SmolVLM. v4.3.0 (16 Sep 2026) added an experimental structured-output package (JSON schema/regex) and Safari 26+ WebGPU. Latest is 4.3.1 (7 Oct 2026). — [transformers.js releases](https://github.com/huggingface/transformers.js/releases)
- ORT Web limits:
  - 2 GB protobuf limit, so use external data.
  - wasm32 has a 4 GB memory ceiling, so ORT Web cannot run models larger than 4 GB; no wasm64 yet.
  - Chrome's ArrayBuffer maximum is 0x7fe00000 (~2 GB).
  - Cache models in Cache API, OPFS or IndexedDB. — [ORT Web large models](https://onnxruntime.ai/docs/tutorials/web/large-models.html)
- OCR models available as ONNX:
  - manga-ocr export: encoder 343 MB + merged decoder 98.6 MB in fp32 (quantized variant removed). — [dnouv/manga-ocr](https://huggingface.co/dnouv/manga-ocr/tree/main/onnx)
  - A fine-tune with a 192-dim encoder: 22 MB encoder + 118 MB decoder. — [NorwayFish/manga-ocr-finetuned](https://huggingface.co/NorwayFish/manga-ocr-finetuned)
  - `onnx-community/manga-ocr-base-ONNX` is tagged for transformers.js; sizes not listed. — [mixpeek listing](https://mixpeek.com/model/onnx-community/manga-ocr-base-ONNX)
  - A PP-OCRv6 small recogniser fine-tuned on manga is 21 MB (recognition only). — [fumetodev/PP-OCRv6_small_rec_manga](https://huggingface.co/fumetodev/PP-OCRv6_small_rec_manga)
  - 8-bit weight storage typically brings float ONNX models to ~30% of original size. — [Pete Warden](https://petewarden.com/2024/12/)
- In-browser translation model option, NLLB-200-distilled-600M (transformers.js):
  - Encoder q4f16 612 MB / int8 415 MB; merged decoder q4f16 642 MB / "quantized" 476 MB. — [Xenova/nllb-200-distilled-600M](https://huggingface.co/Xenova/nllb-200-distilled-600M/tree/main/onnx)
  - License is CC-BY-NC-4.0, "research model … not released for production deployment", with ≤512-token inputs. — [facebook/nllb-200-distilled-600M](https://huggingface.co/facebook/nllb-200-distilled-600M)
- Project evidence that ORT Web + WebGPU already works on the dev machine:
  - AOT inpainting 23 MB at ~110 ms (WebGPU); LaMa-MPE 112 MB at 374 ms (WebGPU). — [docs/DIRECTION.md](../../docs/DIRECTION.md)
  - MI-GAN 28 MB at ~0.1–0.2 s per region in the browser; an 11 MB detector is planned for WebGPU on desktop. — [docs/CLOUD.md](../../docs/CLOUD.md)

**Chrome built-in AI**
- Status: Translator, Language Detector and Summarizer are stable in Chrome 138 for web and extensions. The Prompt API has been stable for extensions since 138 and is stable on the web per the table at 148. Writer/Rewriter/Proofreader are developer trials. — [Chrome built-in APIs](https://developer.chrome.com/docs/ai/built-in-apis) (header says updated 12 Sep 2025; footer conflicts)
- Translator API:
  - Supported languages include `ja` and `vi`.
  - Availability is checked per pair; each pair's model downloads on first use with a `downloadprogress` event.
  - Translations are processed sequentially.
  - Not available in Web Workers; cross-origin iframes need `allow="translator"`.
  - Desktop only ("don't work on mobile devices").
  - The page's badge lists Chrome 138 and Edge 148.
  - Page last updated 20 May 2025. — [Chrome Translator API](https://developer.chrome.com/docs/ai/translator-api)
  - A search-indexed version of the same doc described a pair rule: both languages are Chrome preferred languages, or one is preferred and the other on a "popular" list that includes ja and vi. It also named testing bypasses `--disable-features=TranslationAPIAcceptLanguagesCheck` and `chrome://flags/#translation-api`. The fetched current page did not repeat this rule; treat it as unconfirmed. — [Chrome Translator API (search snippet)](https://developer.chrome.com/docs/ai/translator-api)
- Prompt API (Gemini Nano), page updated 26 Aug 2026:
  - Input/output languages: en, ja, es, de, fr; Vietnamese is not supported.
  - Inputs: text, image, audio (audio requires a GPU).
  - Requirements: Windows 10/11, macOS 13+, Linux, or Chromebook Plus; ≥22 GB free on the profile volume (the model is deleted if free space drops below 10 GB); GPU with strictly >4 GB VRAM, or CPU with ≥16 GB RAM and ≥4 cores; unmetered network for the download.
  - Not available in Web Workers.
  - Extensions can set `temperature`/`topK`: default topK 3, max 128; default temperature 1, max 2.
  - `responseConstraint` takes a JSON schema or regex. Context overflow fires `contextoverflow` or `QuotaExceededError`. — [Chrome Prompt API](https://developer.chrome.com/docs/ai/prompt-api)
  - At Chrome 138, image/audio input was only for Early Preview Program participants. — [Chrome I/O 2025 update](https://developer.chrome.com/blog/ai-api-updates-io25)

**Edge built-in AI**
- Prompt API:
  - Still a developer preview in Edge Canary/Dev (≥138.0.3309.2), using Phi-4-mini.
  - Requirements: Windows 10/11 or macOS 13.3+, ≥20 GB free, ≥5.5 GB VRAM, unmetered network, and device performance class "High".
  - A prerelease Aion-1.0-Instruct model (Edge ≥150.0.4070, behind a flag) is smaller and supports CPU inference; it was "expected" to be open-sourced in July 2026.
  - Page updated 19 Oct 2026. — [Edge Prompt API](https://learn.microsoft.com/en-us/microsoft-edge/web-platform/prompt-api)
- Edge Translator API: a task-specific on-device model with per-pair download on first use, usable from websites and extensions. The page lists neither languages nor channel status; updated 2 Sep 2026. — [Edge Translator API](https://learn.microsoft.com/en-us/microsoft-edge/web-platform/translator-api)

**MV3 platform constraints**
- WebGPU works in service workers and shared workers since Chrome 124; the WebLLM Chrome extension is cited as an example. — [New in WebGPU 124](https://developer.chrome.com/blog/new-in-webgpu-124)
- Extension service worker lifetime:
  - Terminated after 30 s idle, after a single event/request >5 min, or when a `fetch()` response takes >30 s to arrive.
  - Extension API calls reset the timers (Chrome 110), as do offscreen-document messages (109), long-lived messaging (114) and WebSocket traffic (116). — [SW lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle)
- Offscreen documents:
  - Chrome 109+, one per extension at a time, static bundled HTML.
  - Valid reasons include `WORKERS`, `BLOBS`, `DOM_PARSER`, `LOCAL_STORAGE`, `USER_MEDIA`. Only `AUDIO_PLAYBACK` has a lifetime cap.
  - Only `chrome.runtime` is available inside; `hasDocument()` needs Chrome 150+. — [chrome.offscreen](https://developer.chrome.com/docs/extensions/reference/api/offscreen)
- CSP:
  - The default MV3 `extension_pages` policy (`script-src 'self'; object-src 'self';`) disables WebAssembly.
  - The allowed minimum adds `'wasm-unsafe-eval'`; `'unsafe-eval'` is rejected; only packaged scripts load. — [Manifest CSP](https://developer.chrome.com/docs/extensions/reference/manifest/content-security-policy)
- `unlimitedStorage` lifts quota to available disk space. — [Chrome offline storage (legacy page)](https://developer.chrome.com/docs/apps/offline_storage)
- Local Network Access (LNA):
  - The permission prompt launches in Chrome 142 for public→local and public→loopback requests (loopback = 127.0.0.0/8, ::1).
  - Workers need their origin previously granted.
  - The `targetAddressSpace` fetch option exists; an enterprise policy is planned.
  - The page does not cover extensions. — [Chrome LNA blog (Jun 2025, updated 29 Sep 2025)](https://developer.chrome.com/blog/local-network-access)
  - Third parties disagree on extensions: one lists localhost from extensions as "Works (special exemption)". — [TeamPasswordManager](https://teampasswordmanager.com/blog/chrome-142-update/). A Shopify CLI thread reports localhost calls from a public page breaking after 142. — [Shopify community](https://community.shopify.dev/t/chrome-142-default-flag-breaks-network-requests/24658)

### Inferences
- Zero-install tier, all on-device:
  - WebGPU detector, then manga-ocr or PaddleOCR-rec ONNX on crops (≈100–450 MB after int8 for manga-ocr; ~21 MB for PP-OCRv6 rec).
  - Then Chrome `Translator` ja→vi.
  - Optionally Gemini Nano (Prompt API) for Japanese-side tasks only (ja is supported), e.g. cleaning OCR or speaker hints. Never for Vietnamese output.
  - This gives "never silently drop text" coverage on iGPU laptops but cannot reason about who speaks to whom. Label it as a lower-quality mode.
- Translator API placement: not available in workers, so the extension service worker probably cannot call it. Use an offscreen document or a visible extension page (side panel), and verify in a real browser. Because pair availability may depend on the user's Chrome preferred languages, probe `Translator.availability({sourceLanguage:'ja', targetLanguage:'vi'})` at onboarding. Explain the per-pair download, which is a network call made by Chrome and must happen before going offline.
- Long-running local LLM calls should not be made from the service worker. A non-streaming page-level VLM request can exceed the 30 s `fetch()` response limit on slow hardware and get the worker killed. Stream (`stream: true`) and/or run the request from the offscreen document; Kites keeps its engines under `src/offscreen/` (§4).
- Host WebGPU work in the offscreen document; one offscreen document can host several workers. Keep the service worker as a thin router, since the 30 s idle rule and heartbeat hacks are fragile.
- The public web reader calling `http://127.0.0.1:11434` will hit the Chrome 142+ LNA prompt and Ollama's CORS allow-list (an https reader origin is not allowed by default). Route local-mode traffic through the extension, or document both steps for the reader.
- Package ORT/WebLLM wasm and JS inside the extension (no CDN; MV3 forbids remote code) and download only weights. Set `"extension_pages": "script-src 'self' 'wasm-unsafe-eval'; object-src 'self';"`. Store weights in Cache Storage/OPFS with `unlimitedStorage`.
- NLLB-600M is unusable for the paid tier (CC-BY-NC) and its manga quality is unknown. WebLLM Qwen3.5-4B (≈3.4 GB) is the more promising in-browser LLM translator, but needs a JA→VI quality check against Hy-MT2/Qwen3 measured in Ollama. Hy-MT2 is not in WebLLM's prebuilt list.

### Gaps
- No measured in-browser speeds for manga-ocr, PaddleOCR rec, or transformers.js v4 VLMs on the target GPUs or iGPUs. No JA→VI quality data for Chrome's Translator model, and unknown whether it pivots through English.
- Not confirmed:
  - Prompt API image input reaching Chrome stable (it was EPP-only at 138).
  - The current Translator pair rule (preferred/popular languages).
  - Whether Translator/Prompt APIs work in extension service workers vs offscreen documents.
  - How Chrome 142 LNA treats extension-origin requests to 127.0.0.1.
- Current OPFS/Cache Storage quota rules for extension origins were not re-verified; the `unlimitedStorage` source is a legacy page.

## 4. How existing open-source manga tools do local inference (Kites, manga-image-translator, BallonsTranslator, Mokuro, Comic Translate, Koharu)

### Takeaway
Only Kites does fully in-browser inference: a Chrome MV3 extension running PaddleOCR, LaMa/AOT inpainting and a YOLO bubble model on WebGPU, plus WebLLM for local translation. Every desktop tool runs Python or Rust natively, and none publishes sizes or speeds. For a local LLM, manga-image-translator defaults to Ollama's OpenAI endpoint on `localhost:11434`; Koharu bundles GGUF inference with Gemma 4 / Qwen3.5 / Qwen3.6. Nobody publishes reproducible speed or VRAM numbers, so our own measurements would be a differentiator.

### Cited Findings

**Kites (Unheat/Kites, GPL-3.0, Chrome MV3)**
- In-browser components:
  - PaddleOCR v3–v6 detection + recognition.
  - Inpainting: LaMa Manga, AOT-GAN, Telea and Simple Fill.
  - Bubble fit: neural YOLO on WebGPU, heuristic, or MST.
  - Local translation via WebLLM (Qwen 3.5, Qwen 3, Gemma 3, Llama 3.2).
- Other translators: a Cloud Shared Pool (100 free requests/day), Google Translate and a custom API.
- Strips taller than 14,000 px are tiled.
- No model sizes, speeds or hardware requirements are published. — [Kites README](https://github.com/Unheat/Kites)
- Per the project's competitor review:
  - OCR and inpainting run on device; image/blob cache lives in IndexedDB and is pruned after 7 days.
  - The default translator is Google Translate, so text leaves the device by default.
  - Translation engines live under `src/offscreen/engines/`. — [docs/reference/market-comparison.md](../../docs/reference/market-comparison.md); [Kites PRIVACY.md](https://github.com/Unheat/Kites/blob/main/PRIVACY.md); [CustomApiEngine.ts](https://github.com/Unheat/Kites/blob/main/src/offscreen/engines/translation/CustomApiEngine.ts)

**manga-image-translator**
- Offline translators: nllb/nllb_big, sugoi, jparacrawl(_big), mbart50, qwen2/qwen2_big, m2m100(_big) (CTranslate2/NVIDIA) and m2m100_hf.
- OCR: 32px, 48px (recommended for ja/ko), 48px_ctc and mocr. Detectors: default, dbconvnext, ctd, craft and paddle.
- Inpainters: lama_large (recommended), lama_mpe and sd. `inpainting_size` defaults to 2048, with an OOM warning.
- Local LLMs: `custom_openai` with `CUSTOM_OPENAI_API_BASE` defaulting to `http://localhost:11434/v1` (e.g. `qwen2.5:7b`); sakura uses `SAKURA_API_BASE` `http://127.0.0.1:8080/v1`.
- Models auto-download to `./models` at runtime. No VRAM or speed numbers are published. — [manga-image-translator README](https://github.com/zyddnys/manga-image-translator)

**BallonsTranslator**
- Detectors: CTD, YSGDetector and ysg_ctd. OCR: MIT 32/48px models, manga_ocr and PaddleOCRVLManga. Inpainting: AOT, a lama fine-tune and patchmatch.
- Local translators: Sakura-13B-Galgame (low-VRAM mode on by default), m2m100 1.2B (CTranslate2) and Sugoi (ja→en).
- LLM translator: history budget defaults to 10,000 tokens (≈90,000 suggested for 128K models), with glossary and visual context.
- No sizes or speeds are published; a Vietnamese README exists. — [BallonsTranslator README](https://github.com/dmMaze/BallonsTranslator)

**Mokuro**
- Uses comic-text-detector + manga-ocr, processed offline before reading. Output is the `.mokuro` format (since 0.2.0), read in the web reader at reader.mokuro.app.
- No speed or size figures; GPU needs separately installed PyTorch. — [Mokuro README](https://github.com/kha-white/mokuro)

**Comic Translate**
- Detection is RT-DETR-v2 (≈11k training images). OCR defaults to manga-ocr for Japanese and PPOCRv5 for other languages. Inpainting uses a manga-fine-tuned LaMa and AOT-GAN.
- Translation: cloud LLMs only (GPT-4.1, Claude-4.5, Gemini-2.5); local LLMs are not mentioned.
- Ships Windows/macOS apps and a Chromium extension. GPU acceleration in the desktop app works only from source (`onnxruntime-gpu`).
- No sizes or speeds. — [Comic Translate README](https://github.com/ogkalu2/comic-translate)

**Koharu (Rust, Apache-2.0)**
- Detection: RF-DETR Seg layout. OCR: PaddleOCR-VL 1.6, Manga OCR and others. Inpainting: FLUX.2 Klein, RORem, LaMa (manga) and AOT.
- Local GGUF LLMs: LFM 2.5 1.2B, Ministral 3 8B, Gemma 4 E2B→31B, Qwen 3.5 0.8B→35B-A3B, Qwen 3.6 27B/35B-A3B and Qwen 3.8 27B.
- Backends: CUDA 13.3 (Turing+, driver R610+), ROCm, Metal, Vulkan and CPU; WebGPU only for the editor canvas.
- Installs via WinGet/Homebrew. No speed, VRAM or telemetry statements on the README. — [Koharu README](https://github.com/mayocream/koharu)
- Passed 5.0k stars on 7 Aug 2026. — [gittrend](https://gittrend.io/repo/koharu-rs/koharu)
- MangoTL is an open-source Firefox add-on that needs a self-hosted backend. — [MangoTL on AMO](https://addons.mozilla.org/firefox/addon/mangotl/)

### Inferences
- The proven in-browser stack is Kites': ORT-style WebGPU vision models plus WebLLM, with engines in an offscreen document. Our planned split (WebGPU detector/inpaint in the browser, LLM via a local server) matches the desktop tools' practice of pointing at Ollama's OpenAI endpoint.
- Kites and manga-image-translator are GPL-3.0: study patterns but do not copy code. The project's competitor review already recorded this. — [docs/reference/market-comparison.md](../../docs/reference/market-comparison.md)
- Koharu's model menu (Gemma 4, Qwen3.5/3.6/3.8, PaddleOCR-VL) is a useful signal of which local models the manga-translation community considers viable in late 2026.

### Gaps
- No repository publishes per-page latency, VRAM or model download totals, so a comparison table of speeds is impossible without running them.
- Kites' WebLLM default model and size, cache mechanism and minimum GPU are not documented in its README.

## 5. Tuning for a 16 GB RAM / 8 GB VRAM machine running OCR VLM + translator

### Takeaway
On 8 GB, keep one vision model on the GPU and size it to ≤ ~4–5 GB of weights. qwen3-vl:4b or qwen3.5:4b is 3.3 GB; gemma4:e4b at 6.1–6.6 GB is borderline; qwen3-vl:8b at 6.2 GB fits only with short context and quantised KV. A second model must be small (Hy-MT2 1.8B at 1.5 GB) or swapped in deliberately.
- Settings: context 8k, flash attention + q8_0 KV cache, parallel 1 for page-level image calls, long keep-alive while reading.
- Decoding: low temperature and repetition/presence penalty off, because penalties can corrupt stutters and elongations the product must preserve.
- Output: JSON schema to bound it; avoid thinking modes.

### Cited Findings
- Model download sizes that bound VRAM use (§1): qwen3-vl 2b 1.9 / 4b 3.3 / 8b 6.2 GB; qwen3.5 4b 3.3 / 9b 6.6 GB; gemma4 e2b 4.3–4.6 / e4b 6.1–6.6 / 12b 7.2–8.0 GB. — [qwen3-vl tags](https://ollama.com/library/qwen3-vl/tags); [qwen3.5 tags](https://ollama.com/library/qwen3.5/tags); [gemma4 tags](https://ollama.com/library/gemma4/tags)
- Project data on the 4060 Laptop:
  - Hy-MT2 7B Q4 4.6 GB, Hy-MT2 1.8B Q6 1.5 GB, Qwen3 4B Q4 2.5 GB.
  - Gemma 4 E2B occupied 7.2 GB.
  - Adding "background" context to Hy-MT2 7B dropped chrF from 33.8 to 26.3, so it is called per sentence. A text-only translator cannot know who speaks to whom, so local mode needs a vision model too. — [docs/DIRECTION.md](../../docs/DIRECTION.md)
- Memory scaling:
  - Ollama RAM scales by `NUM_PARALLEL × CONTEXT_LENGTH`; q8_0 KV halves KV memory and q4_0 quarters it, both requiring flash attention. — [Ollama FAQ](https://docs.ollama.com/faq)
  - llama-server `--fit` (default on) auto-adjusts unset arguments to fit memory, with a 1 GiB margin and minimum context 4096. — [llama-server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
  - Ollama exposes `OLLAMA_GPU_OVERHEAD` (reserve VRAM) and `LLAMA_ARG_FIT_TARGET`. — [config.go](https://raw.githubusercontent.com/ollama/ollama/main/envconfig/config.go)
- Recommended sampling:
  - Qwen3-VL Instruct, vision tasks: temperature 0.7, top_p 0.8, top_k 20, repetition_penalty 1.0, presence_penalty 1.5. Text-only: temperature 1.0, top_p 1.0, top_k 40, presence_penalty 2.0. — [Qwen3-VL-8B card](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)
  - Qwen3-VL Thinking: temperature 0.6, top_p 0.95, top_k 20, presence_penalty 0. — [Qwen3-VL GitHub](https://github.com/QwenLM/Qwen3-VL)
  - Gemma 4: temperature 1.0, top_p 0.95, top_k 64. — [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)
- Parallelism: Ollama defaults to 1 parallel request per model. — [Ollama FAQ](https://docs.ollama.com/faq). LM Studio defaults to 4 concurrent predictions; batching "results in higher throughput". — [LM Studio parallel](https://lmstudio.ai/docs/app/advanced/parallel-requests). llama-server `-np` auto with continuous batching. — [llama-server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- Residency: Ollama keep-alive defaults to 5 min and `OLLAMA_MAX_LOADED_MODELS` to 3 per GPU, with negative keep-alive pinning a model. — [Ollama FAQ](https://docs.ollama.com/faq). BallonsTranslator enables a "low VRAM mode" by default for its local Sakura model. — [BallonsTranslator README](https://github.com/dmMaze/BallonsTranslator)
- Spill avoidance on Windows: set "Prefer No Sysmem Fallback" so overflow becomes an explicit OOM; the KV cache is allocated for the full `num_ctx` up front. — [llmconfigurator](https://llmconfigurator.com/en/guides/troubleshooting/windows-shared-gpu-memory-slow) (third-party)
- MoE expert offload (`--n-cpu-moe`) is the one partial-offload pattern with good community numbers (30–46 tok/s on 8–12 GB), but 30–35B-A3B models need ~20 GB at Q4. — [Medium](https://medium.com/coding-nexus/one-flag-tripled-my-tokens-per-second-on-an-8gb-gpu-238f55d1e3bd); [llmhardware.io](https://llmhardware.io/guides/qwen3-hardware-requirements)

### Inferences
- **KV budget.** Assume Qwen3-8B-like geometry for Qwen3-VL-4B/8B (36 layers, 8 KV heads × 128 dims; verify from GGUF metadata). KV is ≈144 KiB per token at f16, so 8k context ≈1.2 GB at f16 or ≈0.6 GB at q8_0, and roughly the same for the 4B because it shares the KV geometry.
  - qwen3-vl:8b: 6.2 GB weights+mmproj + 0.6–1.2 GB KV + vision compute buffers + 0.3–0.8 GB Windows desktop VRAM exceeds 8 GB, so expect spill or `--fit` offload.
  - qwen3-vl:4b or qwen3.5:4b at 3.3 GB leaves room for 8–16k context and a 1.5 GB translator.
- **Configurations for an 8 GB / 16 GB machine** (to be measured):

  | | Models | Approx. weights |
  |---|---|---|
  | A | qwen3-vl:4b (OCR + speaker/context) + Hy-MT2 1.8B (line translation) | ≈4.8 GB, both resident |
  | B | One VLM doing OCR + translation in one call (qwen3.5:4b or gemma4:e4b) | ~3.3–6.6 GB |
  | C | qwen3-vl:8b / qwen3.5:9b alone, short context, q8_0 KV | 6.2–6.6 GB; for 12 GB+ desktops |

  Hy-MT2 7B (4.6 GB) + any VLM ≥3.3 GB will not co-reside in 8 GB with KV. Alternating them costs a model reload per page; avoid it, or batch a whole chapter's OCR first and then a whole chapter's translation (the reading-position rules still apply).
- **Ollama settings for local mode:**
  - `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_CONTEXT_LENGTH=8192` (16384 only if sending full pages).
  - `OLLAMA_NUM_PARALLEL=1` (each slot multiplies KV memory).
  - `OLLAMA_MAX_LOADED_MODELS=2`, `OLLAMA_NO_CLOUD=1`, `OLLAMA_MODELS` on a non-system drive.
  - Per-request `keep_alive` of e.g. "30m" while a chapter is open and `0` on "stop local mode", so the GPU is released for games.
- **llama-server equivalent:**
  - `-c 8192 -fa on -ctk q8_0 -ctv q8_0 -np 1 --image-max-tokens 1024` (tune on the GT set) `--offline --host 127.0.0.1`.
  - Leave `--fit` on but log what it changed.
- **Batching:** for VLM OCR, send bubble or region crops at native resolution, several crops per request if the runtime handles multiple images, rather than one downscaled page. For the translator, the project's own data says per-line calls beat batched-with-context for Hy-MT2. For general LLMs (Qwen3/Qwen3.5) a page-level batch with speaker context in one JSON-schema call is likely better for consistency but must be measured. Use parallel 2–4 only for text-only calls with small contexts.
- **Decoding:**
  - For transcription: temperature 0–0.2, presence and repetition penalties at their neutral defaults (`presence_penalty` 0, `repetition_penalty` 1.0). Penalties push the model away from repeated characters such as 「あ、あ、あ…」, 「ーーー」 and 「！！！」, which the product must preserve.
  - Use JSON-schema-constrained output plus a `max_tokens` cap to stop runaway loops instead of penalties.
  - For translation, start near the vendor defaults (Qwen 0.7, Gemma 1.0) but evaluate 0.2–0.4 on the GT set.
  - Disable thinking variants (`-instruct` tags) to save output tokens.
- **Avoiding swap on 16 GB RAM:** Chrome plus the reader plus a 6 GB model spilling to RAM is enough to page. Refuse configurations whose `ollama ps` shows a CPU/GPU split for the vision model, show a "model too large for your GPU" message, and suggest the 4B tier.

### Gaps
- Not measured yet on the dev machine:
  - Qwen3-VL-4B/8B, Qwen3.5-4B/9B and Gemma 4 E4B: OCR CER, latency, VRAM with q8_0 KV, crop vs page.
  - Page-batch vs per-bubble for general LLM translators.
  - The effect of presence_penalty on stutters/elongations.
  - These need `tools/eval` runs with model, run count and cold/warm recorded.
- KV geometry for Qwen3-VL/Qwen3.5/Gemma 4 GGUFs is assumed, not read from metadata.
- No source quantifies Windows desktop VRAM overhead on Optimus laptops.

## 6. Recommended zero-friction install UX: installers, detecting a local server from the extension, download sizes and progress, fallback messaging

### Takeaway
Offer three tiers chosen automatically at onboarding:
1. **Built-in (no install):** WebGPU OCR + Chrome Translator ja→vi; Chrome desktop only; lower quality.
2. **Ollama one-click:** guide download of OllamaSetup.exe (no admin), then the extension pulls a 4B VLM (≈3.3 GB) with consent and progress.
3. **Any local OpenAI-compatible server:** LM Studio :1234, KoboldCpp :5001, llama-server, mlx-vlm.

Detect servers by probing 127.0.0.1 ports from the extension. Handle Ollama's 403 by rewriting the Origin header (fallback: an `OLLAMA_ORIGINS` instruction), and keep local traffic out of the public web reader because of LNA/CORS. Never fall back to cloud in offline mode: show a clear "local server not found / model too big" state instead.

### Cited Findings
- Ollama on Windows:
  - The installer needs no admin, installs to the home directory and needs ≥4 GB for binaries. Requires Windows 10 22H2+ and NVIDIA driver ≥551.61, or AMD ROCm v7/Vulkan.
  - A standalone zip exists for service-style installs. Env vars are set in Windows settings, then the tray app is restarted. — [Ollama Windows docs](https://docs.ollama.com/windows)
  - Models default to `C:\Users\<user>\.ollama\models`; use `OLLAMA_MODELS` to relocate. — [Ollama FAQ](https://docs.ollama.com/faq)
  - The project's dev laptop had ~4.8 GB free on C:. — [docs/DIRECTION.md](../../docs/DIRECTION.md)
- Updating to Ollama ≥0.40 converts existing models in the background, and downgrading below 0.40 requires re-pulling. — [Ollama releases](https://github.com/ollama/ollama/releases)
- Default endpoints:

  | Runtime | Default address / health check | Source |
  |---|---|---|
  | Ollama | `127.0.0.1:11434` | [config.go](https://raw.githubusercontent.com/ollama/ollama/main/envconfig/config.go) |
  | LM Studio | `localhost:1234/v1` | [LM Studio OpenAI compat](https://lmstudio.ai/docs/developer/openai-compat) |
  | KoboldCpp | `localhost:5001/v1` | [KoboldCpp README](https://github.com/LostRuins/koboldcpp) |
  | mlx_vlm.server | `:8080` | [mlx-vlm README](https://github.com/Blaizzy/mlx-vlm) |
  | llama-server | `/health` (503 while loading, 200 when ready) | [llama-server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) |

- LM Studio can run headless (`llmster`, `lms server start`) but has a CORS toggle and JIT load/auto-unload settings the user must enable or understand. — [LM Studio 0.4.0](https://lmstudio.ai/blog/0.4.0); [server settings](https://lmstudio.ai/docs/developer/core/server/settings)
- Koharu installs via WinGet/Homebrew; KoboldCpp ships as a single exe (CUDA or a smaller no-CUDA/Vulkan build). — [Koharu README](https://github.com/mayocream/koharu); [KoboldCpp README](https://github.com/LostRuins/koboldcpp)
- Ollama 403 for extensions: fixed by `OLLAMA_ORIGINS=chrome-extension://*`, or by Origin rewriting as Page Assist does (works for 127.0.0.1/localhost). — [Ollama FAQ](https://docs.ollama.com/faq); [Page Assist docs](https://www.mintlify.com/n4ze3m/page-assist/troubleshooting/connection-issues)
- Chrome's built-in models download on first use with a progress monitor. Chrome needs ≥22 GB free plus GPU >4 GB VRAM or 16 GB RAM/4 cores for Gemini Nano, and per-pair translation models download on demand. — [Chrome Prompt API](https://developer.chrome.com/docs/ai/prompt-api); [Chrome Translator API](https://developer.chrome.com/docs/ai/translator-api)
- Local Network Access prompt for public sites calling loopback from Chrome 142. — [Chrome LNA](https://developer.chrome.com/blog/local-network-access)
- Product rules that constrain fallback:
  - Offline/local mode never calls a non-localhost host.
  - No silent charges.
  - Extra-cost features are opt-in with the cost shown first.
  - Model files are pinned (revision + SHA-256). — [AGENTS.md](../../AGENTS.md)
  - The server already accepts only localhost for `LOCAL_LLM_URL` (default `http://127.0.0.1:11434/v1`). — [docs/DIRECTION.md](../../docs/DIRECTION.md)

### Inferences
- **Onboarding flow (extension side panel):**
  1. Probe `http://127.0.0.1:11434` (Ollama) and `:1234`, `:5001`, `:8080` with short timeouts. Use `127.0.0.1` rather than `localhost` to avoid IPv6 `::1` mismatches, since Ollama binds 127.0.0.1 by default.
  2. If Ollama answers 403, enable the Origin-rewrite rule or show the one-line `OLLAMA_ORIGINS` fix.
  3. List installed models via `/v1/models` and mark which are vision-capable by a tiny test image call.
  4. Recommend a model by VRAM tier: 4B VLM (≈3.3 GB) for 6–8 GB GPUs and 8 GB Macs; 8–9B VLM for 12–16 GB. Show download size and disk location (suggest moving `OLLAMA_MODELS` off a nearly full C:).
  5. Ask for explicit consent before pulling; it is bandwidth and disk, not money, but the "no silent cost" spirit applies.
- **No local server found and no WebGPU/Translator:** show "Local mode unavailable on this device" with links to install Ollama and an explanation. Never switch to cloud or BYOK in offline mode. If Chrome's Translator/Prompt models are not downloaded yet, show that the first download needs internet.
- **Pinning and integrity:** "Model files are pinned (revision + SHA-256)" is straightforward for weights the extension downloads itself (ONNX/WebLLM). For Ollama pulls, record the manifest digest shown by the runtime and warn if a model changes after an Ollama update; v0.40.2 upgrades models in the background.
- **Bundling:** shipping our own llama-server in a companion installer would give full control (`--offline`, `--cors-origins`, `--image-max-tokens`, pinned GGUFs). It adds code-signing, driver variants (CUDA/Vulkan) and update burden. Defer until Ollama-based beta feedback shows the 403/context-length/settings friction is too high.

### Gaps
- Exact installer sizes (OllamaSetup.exe, LM Studio, KoboldCpp CUDA vs no-CUDA exe) were not found.
- Not verified this pass:
  - Ollama's pull-progress API and digest semantics.
  - Whether `declarativeNetRequest` can rewrite Origin on requests from our own service worker/offscreen document (Page Assist's exact mechanism).
  - LNA behaviour for extension-initiated loopback requests in Chrome 142+.
  - llama-server's default port.
- No user-research data on how Vietnamese students react to a 3–7 GB model download or to editing environment variables.
