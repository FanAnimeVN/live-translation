import { appendFile, mkdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { env, PRIVATE_DIR } from "./env";

export interface LedgerEntry {
  at: string;
  model: string;
  purpose: string;
  pageId?: string;
  ok: boolean;
  costUsd: number;
  promptTokens?: number;
  completionTokens?: number;
  ms?: number;
  ttfbMs?: number;
  provider?: string;
  error?: string;
}

const FILE = join(PRIVATE_DIR, "ledger.jsonl");
let spentCache: number | undefined;

export async function spentUsd(): Promise<number> {
  if (spentCache !== undefined) return spentCache;
  try {
    const text = await readFile(FILE, "utf8");
    spentCache = text
      .split("\n")
      .filter(Boolean)
      .reduce((sum, line) => sum + (Number((JSON.parse(line) as LedgerEntry).costUsd) || 0), 0);
  } catch {
    spentCache = 0;
  }
  return spentCache;
}

export class BudgetError extends Error {
  code = "budget";
}

/** Refuse a paid call that could cross the user-approved budget. */
export async function assertBudget(estimateUsd = 0.05): Promise<void> {
  const spent = await spentUsd();
  if (spent + estimateUsd > env.budgetUsd) {
    throw new BudgetError(`Budget reached: $${spent.toFixed(4)} spent of $${env.budgetUsd.toFixed(2)} allowed. Ask the user before raising it.`);
  }
}

export async function record(entry: LedgerEntry): Promise<void> {
  await mkdir(PRIVATE_DIR, { recursive: true });
  await appendFile(FILE, JSON.stringify(entry) + "\n", "utf8");
  spentCache = (await spentUsd()) + (entry.costUsd || 0);
}
