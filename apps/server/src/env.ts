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
  detectorModel: process.env.DETECTOR_MODEL ?? join(ROOT, "artifacts", "comparator-models", "detector-v4-s_int8.onnx"),
  budgetUsd: Number(process.env.BUDGET_USD ?? "4.5"),
  port: Number(process.env.PORT ?? "8787"),
};
