/**
 * Japanese text left on the page: every ground-truth text box is checked against the saved
 * page result. It is "translated" when a region with a Vietnamese translation covers it, "kept"
 * when only regions the model left as art cover it (sound effects, decorative lettering, regions
 * it read as empty), and "missed" when no region covers it at all, i.e. the detector never saw
 * it and the reader still sees Japanese there. The render QA (render.ts) only checks regions that
 * exist, so this is the part it cannot see. Private output, no network.
 *
 *   npx tsx tools/eval/src/gt-coverage.ts <model> [--eval <runId>] [--list]
 */
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { intersect, type Box, type PageResult } from "@lt/core";
import { listPages, loadResult, PRIVATE_DIR } from "@lt/server";

const args = process.argv.slice(2);
const evalRun = args.includes("--eval") ? args[args.indexOf("--eval") + 1] : undefined;
const list = args.includes("--list");
const model = args.find((a, i) => !a.startsWith("--") && args[i - 1] !== "--eval")!;
const ns = process.env.NS ?? "demo";
const safe = (s: string) => s.replace(/[^a-zA-Z0-9._-]/g, "_");
const TRANSLATED = new Set(["dialogue", "thought", "narration", "sign"]);

/** Share of `gt` covered by the union of `boxes` (sampled on a 2 px grid). */
function covered(gt: Box, boxes: Box[]): number {
  const near = boxes.filter((b) => intersect(b, gt));
  if (!near.length) return 0;
  let hit = 0, n = 0;
  for (let y = gt.y + 1; y < gt.y + gt.h; y += 2)
    for (let x = gt.x + 1; x < gt.x + gt.w; x += 2) {
      n++;
      if (near.some((b) => x >= b.x && y >= b.y && x < b.x + b.w && y < b.y + b.h)) hit++;
    }
  return n ? hit / n : 0;
}

const totals = { translated: 0, kept: 0, missed: 0, partly: 0 };
const missedList: string[] = [];
const keptList: string[] = [];
for (const page of await listPages()) {
  let res: PageResult | null = null;
  if (evalRun) {
    try {
      res = JSON.parse(await readFile(join(PRIVATE_DIR, "eval", evalRun, safe(model), `${safe(page.id)}.json`), "utf8")) as PageResult;
    } catch {
      res = null;
    }
  } else res = await loadResult(ns, model, page.id);
  if (!res) continue;
  const translated: Box[] = [];
  const art: Box[] = [];
  for (const r of res.regions) {
    const t = res.translations[r.id];
    const boxes = [r.box, ...(r.bubble ? [r.bubble] : [])];
    if (t && TRANSLATED.has(t.role) && t.vi) translated.push(...boxes);
    else art.push(...boxes);
  }
  page.gt.forEach((g, i) => {
    const tag = `${page.id}#${i + 1}`;
    const c = covered(g.bbox, translated);
    if (c >= 0.5) totals.translated++;
    else if (covered(g.bbox, art) >= 0.5) {
      totals.kept++;
      keptList.push(`${tag} (${g.bbox.w}x${g.bbox.h})`);
    } else {
      totals.missed++;
      if (c > 0) totals.partly++;
      missedList.push(`${tag} (${g.bbox.w}x${g.bbox.h}${c > 0 ? `, ${Math.round(c * 100)}% under a translated region` : ""})`);
    }
  });
}
const all = totals.translated + totals.kept + totals.missed;
console.log(
  `GT text boxes ${all}: translated ${totals.translated} (${((100 * totals.translated) / all).toFixed(1)}%), ` +
    `kept as art ${totals.kept}, missed ${totals.missed} (${totals.partly} partly under a translated region)`,
);
if (list) {
  console.log("\nmissed:\n  " + missedList.join("\n  "));
  console.log("\nkept as art:\n  " + keptList.join("\n  "));
}
