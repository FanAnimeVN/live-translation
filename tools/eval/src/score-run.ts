/**
 * Re-score saved translation runs against the ground truth, with no model calls: GT
 * coverage, CER of the Japanese reading against the labels, and corpus chrF of the
 * Vietnamese against the gold translations (`vi_gold_trans`).
 *
 *   npx tsx tools/eval/src/score-run.ts <run>[:model] [<run>[:model] …] [--set set1] [--worst 20]
 * Without `:model` every model folder of the run is scored. `--worst N` writes the N GT
 * bubbles where each model is furthest from the gold line (private worksheet).
 */
import { readdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { cer, chrfScore, chrfStats, normalizeJa, type ChrfStats, type PageResult } from "@lt/core";
import { listPages, PRIVATE_DIR } from "@lt/server";
import { matchRegions, validGt } from "./gt";

const args = process.argv.slice(2);
const flag = (name: string) => (args.includes(`--${name}`) ? args[args.indexOf(`--${name}`) + 1] : undefined);
const sets = (flag("set") ?? "").split(",").filter(Boolean);
const worstN = Number(flag("worst") ?? "0");
const specs = args.filter((a, i) => !a.startsWith("--") && !args[i - 1]?.startsWith("--"));

const pages = (await listPages()).filter((p) => !sets.length || sets.includes(p.set));
const rows: Array<Record<string, unknown>> = [];
const worst: Array<Record<string, unknown>> = [];

for (const spec of specs) {
  const [run, only] = spec.split(":");
  const dir = join(PRIVATE_DIR, "eval", run);
  const models = only ? [only.replace(/[^a-zA-Z0-9._-]/g, "_")] : (await readdir(dir, { withFileTypes: true })).filter((d) => d.isDirectory()).map((d) => d.name);
  for (const m of models) {
    let gt = 0, found = 0, exact = 0, edits = 0, refLen = 0, regions = 0, translated = 0, cost = 0, scored = 0;
    const stats: ChrfStats[] = [];
    const lines: Array<{ page: string; gt: string; chrf: number; vi: string; gold: string; ja: string }> = [];
    for (const page of pages) {
      let r: PageResult;
      try {
        r = JSON.parse(await readFile(join(dir, m, `${page.id.replace(/[^a-zA-Z0-9._-]/g, "_")}.json`), "utf8")) as PageResult;
      } catch {
        continue;
      }
      scored++;
      regions += r.regions.length;
      translated += Object.keys(r.translations).length;
      cost += r.usage.costUsd ?? 0;
      for (const g of validGt(page.gt, page.size)) {
        gt++;
        const matched = matchRegions(g.bbox, r.regions);
        if (matched.length) found++;
        const ts = matched.map((x) => r.translations[x.id]).filter(Boolean).sort((a, b) => a!.seq - b!.seq);
        const ja = ts.map((t) => t!.ja).join("");
        const vi = ts.map((t) => t!.vi).join(" ");
        const c = cer(ja, g.ja_ocr_truth);
        edits += c.edits;
        refLen += c.refLen;
        if (normalizeJa(ja) === normalizeJa(g.ja_ocr_truth)) exact++;
        if (g.vi_gold_trans?.trim()) {
          const s = chrfStats(vi, g.vi_gold_trans);
          stats.push(s);
          lines.push({ page: page.id, gt: g.bubble_id, chrf: chrfScore([s]), vi, gold: g.vi_gold_trans, ja: g.ja_ocr_truth });
        }
      }
    }
    if (!scored) continue;
    rows.push({ run, model: m, pages: scored, gt: `${found}/${gt}`, translated: `${translated}/${regions}`, exact: `${exact}/${gt}`, cer: refLen ? (100 * edits) / refLen : null, chrf: chrfScore(stats), costPerPage: cost / scored });
    if (worstN) for (const l of [...lines].sort((a, b) => a.chrf - b.chrf).slice(0, worstN)) worst.push({ run, model: m, ...l });
  }
}

console.log("| Run / model | Pages | GT found | Regions translated | GT exact | CER vs labels | chrF vs gold VI | $/page |");
console.log("|---|---|---|---|---|---|---|---|");
for (const r of rows)
  console.log(
    `| ${r.run} / ${r.model} | ${r.pages} | ${r.gt} | ${r.translated} | ${r.exact} | ${r.cer === null ? "—" : (r.cer as number).toFixed(1) + "%"} | ${(r.chrf as number).toFixed(1)} | $${(r.costPerPage as number).toFixed(5)} |`,
  );
if (worstN) {
  const out = join(PRIVATE_DIR, "eval", "worst-lines.json");
  await writeFile(out, JSON.stringify(worst, null, 1), "utf8");
  console.log(`worst lines: ${out}`);
}
