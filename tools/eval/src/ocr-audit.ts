/**
 * OCR agreement audit on the private GT: for each label, compare the readings of two
 * models. When both models agree with each other but not with the label, the label is
 * the first suspect; when all three differ, the crop is a hard case. Writes a private
 * worksheet for human adjudication (never edits the dataset). No network, no cost.
 *
 *   npx tsx tools/eval/src/ocr-audit.ts --a v3b-haiku:anthropic/claude-haiku-5.5 --b bakeoff-20261019:google/gemini-3.8-flash
 */
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { cer, normalizeJa, type PageResult } from "@lt/core";
import { listPages, PRIVATE_DIR } from "@lt/server";
import { matchRegions, validGt } from "./gt";

const arg = (name: string, def: string) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : def;
};
const safe = (s: string) => s.replace(/[^a-zA-Z0-9._-]/g, "_");
const specs = [arg("a", "v3b-haiku:anthropic/claude-haiku-5.5"), arg("b", "bakeoff-20261019:google/gemini-3.8-flash")].map((s) => {
  const [run, model] = s.split(":");
  return { run, model };
});

async function load(run: string, model: string, pageId: string): Promise<PageResult | null> {
  try {
    return JSON.parse(await readFile(join(PRIVATE_DIR, "eval", run, safe(model), `${safe(pageId)}.json`), "utf8")) as PageResult;
  } catch {
    return null;
  }
}

const reading = (r: PageResult, box: Parameters<typeof matchRegions>[0]) =>
  matchRegions(box, r.regions)
    .map((x) => r.translations[x.id])
    .filter(Boolean)
    .sort((a, b) => a!.seq - b!.seq)
    .map((t) => t!.ja)
    .join("");

type Category = "both-match" | "one-match" | "models-agree-not-label" | "all-differ";
const rows: Array<Record<string, unknown>> = [];
const counts: Record<Category, number> = { "both-match": 0, "one-match": 0, "models-agree-not-label": 0, "all-differ": 0 };
let small = 0;
for (const page of await listPages()) {
  const [a, b] = await Promise.all(specs.map((s) => load(s.run, s.model, page.id)));
  if (!a || !b) continue;
  for (const g of validGt(page.gt, page.size)) {
    const label = normalizeJa(g.ja_ocr_truth);
    const ra = normalizeJa(reading(a, g.bbox));
    const rb = normalizeJa(reading(b, g.bbox));
    const category: Category =
      ra === label && rb === label ? "both-match" : ra === label || rb === label ? "one-match" : ra === rb ? "models-agree-not-label" : "all-differ";
    counts[category]++;
    const ca = cer(ra, label);
    // One or two characters off (a stretched sound, a dropped dot): worth a quick look, not a misreading.
    if (category !== "both-match" && Math.min(ca.edits, cer(rb, label).edits) <= 2) small++;
    rows.push({ page: page.id, gt: g.bubble_id, category, label: g.ja_ocr_truth, a: ra, b: rb, editsA: ca.edits, editsB: cer(rb, label).edits });
  }
}
const out = join(PRIVATE_DIR, "eval", "ocr-audit.json");
await writeFile(out, JSON.stringify({ models: specs, counts, rows }, null, 1), "utf8");
const total = Object.values(counts).reduce((x, y) => x + y, 0);
console.log(`labels ${total}:`, counts, `| mismatches within 2 characters of the label: ${small}`);
console.log(`worksheet: ${out}`);
