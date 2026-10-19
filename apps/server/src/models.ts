/** Vision models available through OpenRouter (ids and prices checked 2026-10-18). */
export interface ModelInfo {
  id: string;
  label: string;
  tier: "fast" | "quality" | "free" | "cheap";
  inUsd: number;
  outUsd: number;
  /** Extra request fields, e.g. reasoning control. */
  extra?: Record<string, unknown>;
  /** Anthropic models reject non-default sampling parameters. */
  noSampling?: boolean;
}

export const MODELS: ModelInfo[] = [
  { id: "anthropic/claude-haiku-5.5", label: "Claude Haiku 5.5", tier: "fast", inUsd: 0.1, outUsd: 0.5, noSampling: true, extra: { reasoning: { enabled: false } } },
  { id: "google/gemini-3.1-flash-lite", label: "Gemini 3.1 Flash-Lite", tier: "fast", inUsd: 0.25, outUsd: 1.5, extra: { reasoning: { effort: "low" } } },
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
];

export const DEFAULT_MODEL = MODELS[0].id;

export function modelInfo(id: string): ModelInfo {
  return MODELS.find((m) => m.id === id) ?? { id, label: id, tier: "cheap", inUsd: 1, outUsd: 5 };
}

/** Conservative pre-call estimate for the budget guard (~8k in / 3k out). */
export const estimateUsd = (id: string) => {
  const m = modelInfo(id);
  return (8000 * m.inUsd + 3000 * m.outUsd) / 1e6;
};
