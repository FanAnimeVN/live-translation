/** Vision models available through OpenRouter (ids and prices checked 2026-10-18). */
export interface ModelInfo {
  id: string;
  label: string;
  tier: "fast" | "quality" | "free" | "cheap" | "local";
  inUsd: number;
  outUsd: number;
  /** Extra request fields, e.g. reasoning control. */
  extra?: Record<string, unknown>;
  /** Anthropic models reject non-default sampling parameters. */
  noSampling?: boolean;
  /**
   * OpenRouter provider preferences for interactive calls. The same model can read images
   * far worse on some providers (measured 2026-10-19: DeepSeek V4.1 Flash 1017 on Relace read
   * 58% of characters wrong vs 26% on InferenceNet), so the cheapest is not always the same model.
   */
  provider?: Record<string, unknown>;
}

export const MODELS: ModelInfo[] = [
  { id: "anthropic/claude-haiku-5.5", label: "Claude Haiku 5.5 (mặc định)", tier: "fast", inUsd: 0.1, outUsd: 0.5, noSampling: true, extra: { reasoning: { enabled: false } } },
  { id: "google/gemini-3.1-flash-lite", label: "Gemini 3.1 Flash-Lite (chất lượng cao, đắt hơn ~5 lần)", tier: "fast", inUsd: 0.25, outUsd: 1.5, extra: { reasoning: { effort: "low" } } },
  // Price depends on the provider OpenRouter routes to: $0.05/$0.15 (Relace) up to $0.30/$1.20 (DeepSeek's own endpoint).
  { id: "deepseek/deepseek-v4.1-flash-1017", label: "DeepSeek V4.1 Flash 1017 (nhanh)", tier: "cheap", inUsd: 0.08, outUsd: 0.5, extra: { reasoning: { enabled: false } }, provider: { order: ["InferenceNet", "DeepInfra"], allow_fallbacks: true, ignore: ["Relace", "Morph"] } },
  { id: "google/gemini-2.5-flash-lite", label: "Gemini 2.5 Flash-Lite", tier: "cheap", inUsd: 0.1, outUsd: 0.4, extra: { reasoning: { enabled: false } } },
  { id: "google/gemini-2.5-flash", label: "Gemini 2.5 Flash", tier: "quality", inUsd: 0.3, outUsd: 2.5, extra: { reasoning: { enabled: false } } },
  { id: "deepseek/deepseek-v4.1-flash", label: "DeepSeek V4.1 Flash", tier: "cheap", inUsd: 0.063, outUsd: 0.12, extra: { reasoning: { enabled: false } } },
  { id: "qwen/qwen3-vl-235b-a22b-instruct", label: "Qwen3-VL 235B", tier: "cheap", inUsd: 0.21, outUsd: 1.9 },
  { id: "google/gemini-3.7-flash", label: "Gemini 3.7 Flash", tier: "quality", inUsd: 0.75, outUsd: 3.75, extra: { reasoning: { effort: "low" } } },
  { id: "anthropic/claude-sonnet-5.5", label: "Claude Sonnet 5.5", tier: "quality", inUsd: 2, outUsd: 10, noSampling: true, extra: { reasoning: { enabled: false } } },
  // Candidates added 2026-10-19 for a measured comparison (catalog list prices).
  { id: "xiaomi/mimo-v2.6-flash", label: "MiMo-V2.6-Flash", tier: "cheap", inUsd: 0.14, outUsd: 0.28, extra: { reasoning: { enabled: false } } },
  { id: "qwen/qwen3.7-flash", label: "Qwen3.7-Flash", tier: "cheap", inUsd: 0.03, outUsd: 0.13, extra: { reasoning: { enabled: false } } },
  { id: "qwen/qwen3.8-omni-flash", label: "Qwen3.8-Omni-Flash", tier: "cheap", inUsd: 0.15, outUsd: 0.47, extra: { reasoning: { enabled: false } } },
  { id: "google/gemini-3.8-flash", label: "Gemini 3.8 Flash", tier: "quality", inUsd: 0.825, outUsd: 4.125, extra: { reasoning: { effort: "low" } } },
  { id: "google/gemma-4-26b-a4b-it:free", label: "Gemma 4 26B (free)", tier: "free", inUsd: 0, outUsd: 0 },
  { id: "mock/sample", label: "Mock (offline, bản dịch giả để thử dàn chữ)", tier: "free", inUsd: 0, outUsd: 0 },
  // On the reader's own machine through Ollama or LM Studio (LOCAL_LLM_URL, localhost only): no
  // credits, nothing leaves the computer. Tags are Ollama's; candidates for a 16 GB RAM machine.
  { id: "local/qwen3-vl:8b-instruct", label: "Qwen3-VL 8B (máy bạn, offline · 6.1 GB)", tier: "local", inUsd: 0, outUsd: 0 },
  { id: "local/gemma4:e4b-it-qat", label: "Gemma 4 E4B (máy bạn, offline · 6.1 GB)", tier: "local", inUsd: 0, outUsd: 0 },
  { id: "local/qwen3-vl:4b-instruct", label: "Qwen3-VL 4B (máy bạn, offline · 3.3 GB)", tier: "local", inUsd: 0, outUsd: 0 },
  { id: "local/gemma4:e2b", label: "Gemma 4 E2B (máy bạn, offline · 4.6 GB)", tier: "local", inUsd: 0, outUsd: 0 },
];

/**
 * Default reader/translator (2026-10-19, price first, then accuracy and speed): Haiku 5.5.
 * On the team's 25 double pages it matches DeepSeek V4.1 Flash 1017 against the gold
 * Vietnamese (chrF 38.1 vs 38.4) and reads Japanese better (CER 14.5% vs 19.6%); in a blind
 * review of the 30 most divergent lines it made 3 severe meaning errors to DeepSeek's 8, for
 * ~35% more cost ($0.0014 vs $0.0010 per double page). DeepSeek is the fast option (2.7 s to
 * the first bubble vs 5.5 s); Gemini 3.1 Flash-Lite the opt-in quality tier: on the same 25 pages
 * chrF 43.4 (best) and CER 16.3%, but $0.0093 per double page (~7x) and 11 s to the first bubble.
 */
export const DEFAULT_MODEL = "anthropic/claude-haiku-5.5";

export function modelInfo(id: string): ModelInfo {
  return MODELS.find((m) => m.id === id) ?? (id.startsWith("local/") ? { id, label: id, tier: "local", inUsd: 0, outUsd: 0 } : { id, label: id, tier: "cheap", inUsd: 1, outUsd: 5 });
}

/** Conservative pre-call estimate for the budget guard (~8k in / 3k out). */
export const estimateUsd = (id: string) => {
  const m = modelInfo(id);
  return (8000 * m.inUsd + 3000 * m.outUsd) / 1e6;
};
