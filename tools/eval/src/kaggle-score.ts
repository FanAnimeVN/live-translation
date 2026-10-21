/**
 * Score what local models produced on a remote GPU (tools/kaggle/local-models.py) against the ground
 * truth on this machine, with the product's own stream parser and region rules:
 *   vlm  page requests answered by vision models: regions translated, CER of the Japanese, chrF of the Vietnamese
 *   ocr  crop OCR models: CER on label-box crops (OCR alone) and on detected regions (as the pipeline sees them)
 *   mt   translation of the labelled Japanese lines (perfect OCR): chrF against the gold Vietnamese
 *   mt2  translation of the OCR text of detected regions (two-stage local mode): chrF against the gold
 * Reads the unzipped results.zip (default .private/kaggle/results) and the pack it was made from.
 *
 *   npx tsx tools/eval/src/kaggle-score.ts [--results .private/kaggle/results] [--pack .private/kaggle/team25]
 */
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { applyRegionRules, cer, chrfScore, chrfStats, isNotesObject, JsonObjectStream, parseRegionObject, percentile, type ChrfStats, type RegionTranslation, type TextRegion } from "@lt/core";
import { getPage, PRIVATE_DIR, type DatasetPage } from "@lt/server";
import { matchRegions, validGt } from "./gt";

const args = process.argv.slice(2);
const flag = (n: string, d: string) => (args.includes(`--${n}`) ? args[args.indexOf(`--${n}`) + 1] : d);
const dir = flag("results", join(PRIVATE_DIR, "kaggle", "results"));
const packDir = join(flag("pack", join(PRIVATE_DIR, "kaggle", "team25")), "pages");

interface Reply {
  model: string;
  pageId: string;
  raw: string;
  ttfbMs?: number;
  totalMs?: number;
  promptTokens?: number;
  completionTokens?: number;
  error?: string;
}
interface PackPage { pageId: string; regions: TextRegion[] }

const fileOf = (pageId: string) => `${pageId.replace(/[^\w.-]/g, "_")}.json`;
const readJson = async <T>(p: string): Promise<T | undefined> => JSON.parse(await readFile(p, "utf8").catch(() => "null")) ?? undefined;
const listJson = async (d: string) => (await readdir(d).catch(() => [] as string[])).filter((f) => f.endsWith(".json"));
const pageCache = new Map<string, DatasetPage>();
const page = async (id: string) => pageCache.get(id) ?? pageCache.set(id, await getPage(id)).get(id)!;
const packCache = new Map<string, PackPage>();
const pack = async (id: string) => packCache.get(id) ?? packCache.set(id, (await readJson<PackPage>(join(packDir, fileOf(id))))!).get(id)!;
const pageSize = (regions: TextRegion[]) => ({ w: Math.max(...regions.map((x) => x.box.x + x.box.w)) * 2, h: Math.max(...regions.map((x) => x.box.y + x.box.h)) * 2 });
const pct = (edits: number, len: number) => (len ? `${((100 * edits) / len).toFixed(1)}%` : "—");
const secs = (ms?: number) => (ms === undefined ? "—" : `${(ms / 1000).toFixed(1)} s`);

/** Region texts matched to each label box, in the regions' reading order (same rule as the bake-off). */
async function perLabel(pageId: string, byRegion: Record<string, string>, order: (id: string) => number) {
  const p = await page(pageId);
  const regions = (await pack(pageId)).regions;
  return validGt(p.gt, pageSize(regions)).map((g) => {
    const matched = matchRegions(g.bbox, regions).filter((r) => byRegion[r.id] !== undefined).sort((a, b) => order(a.id) - order(b.id));
    return { g, text: matched.map((r) => byRegion[r.id]).join(" ") };
  });
}

const meta = (await readJson<{ gpus?: string[]; models?: Record<string, { sizeGb?: number; vramMb?: number; pullSec?: number; error?: string }> }>(join(dir, "meta.json"))) ?? {};
console.log(`GPU: ${meta.gpus?.join("; ") ?? "?"}\n`);

// ---------------------------------------------------------------- vlm
const vlmRoot = join(dir, "vlm");
const vlmRows: string[] = [];
for (const m of (await readdir(vlmRoot, { withFileTypes: true }).catch(() => [])).filter((d) => d.isDirectory())) {
  let pagesOk = 0, regionsTotal = 0, translated = 0, edits = 0, refLen = 0, errors = 0;
  const chrf: ChrfStats[] = [], ttfb: number[] = [], total: number[] = [], tps: number[] = [];
  const files = await listJson(join(vlmRoot, m.name));
  for (const f of files) {
    const r = (await readJson<Reply>(join(vlmRoot, m.name, f)))!;
    const regions = (await pack(r.pageId)).regions;
    regionsTotal += regions.length;
    if (r.error) errors++;
    if (r.ttfbMs) ttfb.push(r.ttfbMs);
    if (r.totalMs) total.push(r.totalMs);
    if (r.completionTokens && r.totalMs && r.ttfbMs) tps.push(r.completionTokens / ((r.totalMs - r.ttfbMs) / 1000));
    // Same parsing path as apps/server/src/pipeline.ts.
    const ids = new Set(regions.map((x) => x.id));
    const ts: Record<string, RegionTranslation> = {};
    let seq = 0;
    new JsonObjectStream((value) => {
      if (isNotesObject(value)) return;
      const parsed = parseRegionObject(value, ids, seq);
      if (!parsed || ts[parsed.id]) return;
      ts[parsed.id] = applyRegionRules(parsed, regions.find((x) => x.id === parsed.id));
      seq++;
    }).push(r.raw ?? "");
    if (Object.keys(ts).length) pagesOk++;
    translated += Object.keys(ts).length;
    const ja = Object.fromEntries(Object.entries(ts).map(([k, v]) => [k, v.ja]));
    const vi = Object.fromEntries(Object.entries(ts).map(([k, v]) => [k, v.vi]));
    const order = (id: string) => ts[id].seq;
    for (const { g, text } of await perLabel(r.pageId, ja, order)) {
      const c = cer(text, g.ja_ocr_truth);
      edits += c.edits;
      refLen += c.refLen;
    }
    for (const { g, text } of await perLabel(r.pageId, vi, order)) if (g.vi_gold_trans?.trim()) chrf.push(chrfStats(text, g.vi_gold_trans));
  }
  vlmRows.push(`| ${m.name} | ${pagesOk}/${files.length} | ${translated}/${regionsTotal} | ${pct(edits, refLen)} | ${chrfScore(chrf).toFixed(1)} | ${secs(ttfb.length ? percentile(ttfb, 0.5) : undefined)} | ${secs(total.length ? percentile(total, 0.5) : undefined)} | ${tps.length ? percentile(tps, 0.5).toFixed(0) : "—"} | ${errors} |`);
}
if (vlmRows.length) {
  console.log("## Vision models answering the product's page request\n");
  console.log("| Model | Pages parsed | Regions | CER vs labels | chrF vs gold VI | First token p50 | Page p50 | Tokens/s | Errors |\n|---|---|---|---|---|---|---|---|---|");
  vlmRows.forEach((r) => console.log(r));
}

// ---------------------------------------------------------------- ocr
const ocrRows: string[] = [];
for (const f of await listJson(join(dir, "ocr"))) {
  const r = (await readJson<{ gt?: Record<string, string>; det?: Record<string, Record<string, string>>; msPerCrop?: number; error?: string }>(join(dir, "ocr", f)))!;
  const name = f.replace(/\.json$/, "");
  if (r.error) {
    ocrRows.push(`| ${name} | failed: ${r.error.slice(0, 80)} | | | | |`);
    continue;
  }
  let e1 = 0, l1 = 0, exact = 0, n1 = 0;
  for (const [key, text] of Object.entries(r.gt ?? {})) {
    const [pageId, i] = [key.slice(0, key.lastIndexOf("#")), Number(key.slice(key.lastIndexOf("#") + 1))];
    const ref = (await page(pageId)).gt[i]?.ja_ocr_truth ?? "";
    if (!ref.trim()) continue;
    const c = cer(text, ref);
    e1 += c.edits;
    l1 += c.refLen;
    n1++;
    if (!c.edits) exact++;
  }
  let e2 = 0, l2 = 0;
  for (const [pageId, byRegion] of Object.entries(r.det ?? {})) {
    const regions = (await pack(pageId)).regions;
    const order = (id: string) => regions.find((x) => x.id === id)?.order ?? 0;
    for (const { g, text } of await perLabel(pageId, byRegion, order)) {
      const c = cer(text, g.ja_ocr_truth);
      e2 += c.edits;
      l2 += c.refLen;
    }
  }
  ocrRows.push(`| ${name} | ${pct(e1, l1)} | ${n1 ? ((100 * exact) / n1).toFixed(0) : "—"}% | ${pct(e2, l2)} | ${r.msPerCrop ?? "—"} ms |`);
}
if (ocrRows.length) {
  console.log("\n## Crop OCR\n");
  console.log("| Model | CER on label boxes (OCR alone) | Exact lines | CER on detected regions | Time per crop |\n|---|---|---|---|---|");
  ocrRows.forEach((r) => console.log(r));
}

// ---------------------------------------------------------------- mt
const mtRows: string[] = [];
for (const f of await listJson(join(dir, "mt"))) {
  const r = (await readJson<{ model: string; mode: string; out: Record<string, string>; msTotal: number; calls: number; fallbackPages?: number }>(join(dir, "mt", f)))!;
  const stats: ChrfStats[] = [];
  let empty = 0;
  for (const [key, vi] of Object.entries(r.out)) {
    const [pageId, i] = [key.slice(0, key.lastIndexOf("#")), Number(key.slice(key.lastIndexOf("#") + 1))];
    const gold = (await page(pageId)).gt[i]?.vi_gold_trans ?? "";
    if (!gold.trim()) continue;
    if (!vi.trim()) empty++;
    stats.push(chrfStats(vi, gold));
  }
  const lines = Object.keys(r.out).length;
  mtRows.push(`| ${f.replace(/\.json$/, "")} | ${r.mode} | ${chrfScore(stats).toFixed(1)} | ${empty}/${stats.length} | ${lines ? (r.msTotal / lines).toFixed(0) : "—"} ms | ${r.fallbackPages ?? 0} |`);
}
if (mtRows.length) {
  console.log("\n## Translation of the labelled Japanese (perfect OCR)\n");
  console.log("| Config | Mode | chrF vs gold VI | Empty lines | Time per line | Pages that fell back |\n|---|---|---|---|---|---|");
  mtRows.sort((a, b) => Number(b.split("|")[3]) - Number(a.split("|")[3])).forEach((r) => console.log(r));
}

// ---------------------------------------------------------------- mt2
const mt2Rows: string[] = [];
for (const f of await listJson(join(dir, "mt2"))) {
  const r = (await readJson<{ ocr: string; mode: string; out: Record<string, Record<string, string>>; msTotal: number; calls: number }>(join(dir, "mt2", f)))!;
  const stats: ChrfStats[] = [];
  let regions = 0;
  for (const [pageId, byRegion] of Object.entries(r.out)) {
    regions += Object.keys(byRegion).length;
    const packRegions = (await pack(pageId)).regions;
    const order = (id: string) => packRegions.find((x) => x.id === id)?.order ?? 0;
    for (const { g, text } of await perLabel(pageId, byRegion, order)) if (g.vi_gold_trans?.trim()) stats.push(chrfStats(text, g.vi_gold_trans));
  }
  mt2Rows.push(`| ${f.replace(/\.json$/, "").replace("__", " → ")} | ${r.mode} | ${chrfScore(stats).toFixed(1)} | ${regions} | ${(r.msTotal / Math.max(1, Object.keys(r.out).length) / 1000).toFixed(1)} s |`);
}
if (mt2Rows.length) {
  console.log("\n## Two-stage: crop OCR of detected regions → translator\n");
  console.log("| OCR → translator | Mode | chrF vs gold VI | Regions | Translation time per page |\n|---|---|---|---|---|");
  mt2Rows.forEach((r) => console.log(r));
}

const sized = Object.entries(meta.models ?? {});
if (sized.length) {
  console.log("\n## Models\n\n| Model | Size | Peak VRAM (whole GPU) | Pull | Note |\n|---|---|---|---|---|");
  for (const [k, v] of sized) console.log(`| ${k} | ${v.sizeGb ?? "?"} GB | ${v.vramMb ? (v.vramMb / 1024).toFixed(1) + " GB" : "?"} | ${v.pullSec ?? "?"} s | ${v.error ?? ""} |`);
}
