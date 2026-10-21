import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

/** Repository root (the folder holding AGENTS.md). */
export const ROOT = (() => {
  let dir = dirname(fileURLToPath(import.meta.url));
  for (let i = 0; i < 6; i++) {
    if (existsSync(join(dir, "AGENTS.md")) && existsSync(join(dir, "packages"))) return dir;
    dir = dirname(dir);
  }
  return process.cwd();
})();

// The project's .env.local wins over machine-wide variables (an old OPENROUTER_API_KEY
// in the Windows user environment must not silently replace the project key).
const envFile = join(ROOT, ".env.local");
if (existsSync(envFile)) {
  for (const line of readFileSync(envFile, "utf8").split(/\r?\n/)) {
    const m = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/.exec(line);
    if (m && !line.trimStart().startsWith("#")) process.env[m[1]] = m[2].replace(/^(['"])(.*)\1$/, "$2");
  }
}

export const PRIVATE_DIR = resolve(ROOT, ".private");

export const env = {
  openrouterKey: process.env.OPENROUTER_API_KEY ?? "",
  datasetDir: process.env.DATASET_DIR ?? "",
  /** More ground-truth folders (same JSON format), separated by ";" — e.g. the team's 50-page set. */
  extraDatasetDirs: (process.env.DATASET_DIRS ?? "").split(";").map((s) => s.trim()).filter(Boolean),
  detectorModel: process.env.DETECTOR_MODEL ?? join(ROOT, "artifacts", "comparator-models", "detector-v4-s_int8.onnx"),
  budgetUsd: Number(process.env.BUDGET_USD ?? "4.5"),
  port: Number(process.env.PORT ?? "8787"),
  /** OpenAI-compatible endpoint of a local model server: Ollama (default) or LM Studio (:1234/v1). */
  localLlmUrl: process.env.LOCAL_LLM_URL ?? "http://127.0.0.1:11434/v1",
  /**
   * Context size asked of Ollama for local models. A page request (prompt v5 + page image + crops) is
   * 5–9k tokens, and Ollama's default (4,096 below 24 GB of VRAM) rejects it: "request exceeds the
   * available context size". Its OpenAI-compatible endpoint cannot change this, so local Ollama calls
   * use the native API with this value.
   */
  localNumCtx: Number(process.env.LOCAL_NUM_CTX ?? "16384"),
};

/** Offline mode never calls a non-localhost host: only these hosts are accepted for local models. */
export function assertLocalUrl(url: string): URL {
  const u = new URL(url);
  if (!["127.0.0.1", "localhost", "[::1]", "::1"].includes(u.hostname)) throw new Error(`LOCAL_LLM_URL must point to this machine, got ${u.hostname}`);
  return u;
}
