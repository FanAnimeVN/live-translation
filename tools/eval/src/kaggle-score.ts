/**
 * Score the replies that local models gave on a remote GPU (tools/kaggle/local-models.ipynb)
 * with the product's own stream parser and region rules, against the ground truth on this
 * machine: regions translated, CER of the Japanese, chrF of the Vietnamese against the gold
 * translation, and the same chrF when a translation model (Hy-MT2) translates the reader's
 * Japanese instead (two-stage local mode). Reads .private/kaggle/results/ (unzipped results.zip).
 *
 *   npx tsx tools/eval/src/kaggle-score.ts [--results .private/kaggle/results]
 */
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { applyRegionRules, cer, chrfScore, chrfStats, isNotesObject, JsonObjectStream, parseRegionObject, percentile, type ChrfStats, type RegionTranslation, type TextRegion } from "@lt/core";
import { getPage, PRIVATE_DIR } from "@lt/server";
import { matchRegions, validGt } from "./gt";

const args = process.argv.slice(2);
const dir = args.includes("--results") ? args[args.indexOf("--results") + 1] : join(PRIVATE_DIR, "kaggle", "results");
const packDir = join(PRIVATE_DIR, "kaggle", "pack", "pages");

interface Reply {
  model: string;
  pageId: string;
  raw: string;
  ttfbMs?: number;
  totalMs?: number;
  promptTokens?: number;
  completionTokens?: number;
  error?: string;
  /** Two-stage: translator model -> region id -> Vietnamese. */
  mt?: Record<string, Record<string, string>>;
}

const meta = JSON.parse(await readFile(join(dir, "meta.json"), "utf8").catch(() => "{}")) as { gpu?: string; models?: Record<string, { sizeGb?: number; vramMb?: number; loadSec?: number }> };
const rows: string[] = [];
const mtRows: string[] = [];
for (const modelDir of (await readdir(dir, { withFileTypes: true })).filter((d) => d.isDirectory())) {
  const files = (await readdir(join(dir, modelDir.name))).filter((f) => f.endsWith(".json"));
  let model = modelDir.name;
  let pagesOk = 0, regionsTotal = 0, translated = 0, edits = 0, refLen = 0, errors = 0;
  const chrf: ChrfStats[] = [];
  const mtChrf: Record<string, ChrfStats[]> = {};
  const ttfb: number[] = [];
  const total: number[] = [];
  const tps: number[] = [];
  for (const f of files) {
    const r = JSON.parse(await readFile(join(dir, modelDir.name, f), "utf8")) as Reply;
    model = r.model;
    const pack = JSON.parse(await readFile(join(packDir, f), "utf8")) as { regions: TextRegion[] };
    regionsTotal += pack.regions.length;
    if (r.error) errors++;
    if (r.ttfbMs) ttfb.push(r.ttfbMs);
    if (r.totalMs) total.push(r.totalMs);
    if (r.completionTokens && r.totalMs && r.ttfbMs) tps.push(r.completionTokens / ((r.totalMs - r.ttfbMs) / 1000));
    // Same parsing path as apps/server/src/pipeline.ts.
    const ids = new Set(pack.regions.map((x) => x.id));
    const ts: Record<string, RegionTranslation> = {};
    let seq = 0;
    const parser = new JsonObjectStream((value) => {
      if (isNotesObject(value)) return;
      const parsed = parseRegionObject(value, ids, seq);
      if (!parsed || ts[parsed.id]) return;
      ts[parsed.id] = applyRegionRules(parsed, pack.regions.find((x) => x.id === parsed.id));
      seq++;
    });
    parser.push(r.raw ?? "");
    const n = Object.keys(ts).length;
    translated += n;
    if (n) pagesOk++;
    const page = await getPage(r.pageId);
    const size = { w: Math.max(...pack.regions.map((x) => x.box.x + x.box.w)), h: Math.max(...pack.regions.map((x) => x.box.y + x.box.h)) };
    for (const g of validGt(page.gt, { w: size.w * 2, h: size.h * 2 })) {
      const matched = matchRegions(g.bbox, pack.regions).filter((x) => ts[x.id]).sort((a, b) => ts[a.id].seq - ts[b.id].seq);
      const c = cer(matched.map((x) => ts[x.id].ja).join(""), g.ja_ocr_truth);
      edits += c.edits;
      refLen += c.refLen;
      if (!g.vi_gold_trans?.trim()) continue;
      chrf.push(chrfStats(matched.map((x) => ts[x.id].vi).join(" "), g.vi_gold_trans));
      for (const [mt, byId] of Object.entries(r.mt ?? {})) (mtChrf[mt] ??= []).push(chrfStats(matched.map((x) => byId[x.id] ?? "").join(" "), g.vi_gold_trans));
    }
  }
  const m = meta.models?.[model];
  rows.push(
    `| ${model} | ${m?.sizeGb ?? "?"} GB | ${m?.vramMb ? Math.round(m.vramMb / 1024 * 10) / 10 + " GB" : "?"} | ${pagesOk}/${files.length} | ${translated}/${regionsTotal} | ${refLen ? ((100 * edits) / refLen).toFixed(1) : "—"}% | ${chrfScore(chrf).toFixed(1)} | ` +
      `${ttfb.length ? (percentile(ttfb, 0.5) / 1000).toFixed(1) : "—"} s | ${total.length ? (percentile(total, 0.5) / 1000).toFixed(1) : "—"} s | ${tps.length ? percentile(tps, 0.5).toFixed(0) : "—"} | ${errors} |`,
  );
  for (const [mt, st] of Object.entries(mtChrf)) mtRows.push(`| ${model} → ${mt} | ${chrfScore(st).toFixed(1)} | ${chrfScore(chrf).toFixed(1)} |`);
}
console.log(`GPU: ${meta.gpu ?? "?"}\n`);
console.log("| Reader model | Size | VRAM | Pages parsed | Regions | CER vs labels | chrF vs gold VI | First token p50 | Page p50 | Tokens/s | Errors |");
console.log("|---|---|---|---|---|---|---|---|---|---|---|");
for (const r of rows) console.log(r);
if (mtRows.length) {
  console.log("\n| Two-stage: reader → translator | chrF (translator's Vietnamese) | chrF (reader's own Vietnamese) |\n|---|---|---|");
  for (const r of mtRows) console.log(r);
}
