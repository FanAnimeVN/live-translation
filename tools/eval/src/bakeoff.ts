/**
 * Model bake-off on the private GT pages: same detector, prompt and memory flow for
 * every model. Pages of a series run in order so each model builds its own memory.
 *
 *   npm run eval -- --models anthropic/claude-haiku-5.5,google/gemini-3.1-flash-lite --runs 1
 *
 * Output (private): .private/eval/<runId>/<model>/<page>.json, summary.json, latest.json
 */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { cer, emptyMemory, mergePage, normalizeJa, percentile, type PageResult, type SeriesMemory } from "@lt/core";
import { listPages, modelInfo, PRIVATE_DIR, readPageImage, spentUsd, translatePage } from "@lt/server";
import { matchRegions, validGt } from "./gt";

const arg = (name: string, def: string) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : def;
};
const DEFAULT_MODELS = [
  "google/gemini-3.1-flash-lite",
  "deepseek/deepseek-v4.1-flash-1017",
  "anthropic/claude-haiku-5.5",
  "google/gemini-3.8-flash",
];
const models = arg("models", DEFAULT_MODELS.join(",")).split(",").filter(Boolean);
const runs = Number(arg("runs", "1"));
// Request fields applied to every model in this run, e.g. --extra '{"reasoning":{"enabled":false}}'.
const extra = arg("extra", "") ? (JSON.parse(arg("extra", "{}")) as Record<string, unknown>) : undefined;
const only = arg("pages", "").split(",").filter(Boolean);
const runId = arg("run", new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19));
const safe = (s: string) => s.replace(/[^a-zA-Z0-9._-]/g, "_");
const outDir = join(PRIVATE_DIR, "eval", runId);

const pages = (await listPages()).filter((p) => !only.length || only.includes(p.id));

interface PageScore {
  pageId: string;
  run: number;
  ok: boolean;
  error?: string;
  regions: number;
  translated: number;
  missing: number;
  gt: number;
  gtFound: number;
  exact: number;
  edits: number;
  refLen: number;
  firstRegionMs?: number;
  totalMs?: number;
  costUsd: number;
  roles: Record<string, number>;
}

const summary: Record<string, unknown> = { runId, startedAt: new Date().toISOString(), models: {} as Record<string, unknown> };
const blind: Array<{ pageId: string; gtId: string; ja: string; outputs: Record<string, string> }> = [];

for (const model of models) {
  const scores: PageScore[] = [];
  const dir = join(outDir, safe(model));
  await mkdir(dir, { recursive: true });
  let stop = false;
  for (let run = 1; run <= runs && !stop; run++) {
    const memories = new Map<string, SeriesMemory>();
    for (const page of pages) {
      const memory = memories.get(page.seriesId) ?? emptyMemory(page.seriesId, page.title);
      const base: PageScore = { pageId: page.id, run, ok: false, regions: 0, translated: 0, missing: 0, gt: 0, gtFound: 0, exact: 0, edits: 0, refLen: 0, costUsd: 0, roles: {} };
      try {
        const result = await translatePage(
          { id: page.id, title: page.title, seriesId: page.seriesId, position: page.position, bytes: await readPageImage(page) },
          { model, memory, extra },
        );
        memories.set(page.seriesId, mergePage(memory, page.id, page.position, result.notes, Object.values(result.translations)).memory);
        if (run === 1) await writeFile(join(dir, `${safe(page.id)}.json`), JSON.stringify(result), "utf8");
        const s = score(result, page.gt, page.size);
        scores.push({ ...base, ...s, ok: true });
        if (run === 1) collectBlind(model, result, page.id, page.gt, page.size);
        console.log(`${model} run${run} ${page.id}: ${s.translated}/${s.regions} regions, GT exact ${s.exact}/${s.gt}, first ${s.firstRegionMs}ms total ${s.totalMs}ms $${s.costUsd.toFixed(5)}`);
      } catch (e) {
        const err = e as { message?: string; code?: string };
        scores.push({ ...base, error: err.message ?? String(e) });
        console.log(`${model} run${run} ${page.id}: ERROR ${err.message}`);
        if (err.code === "budget" || err.code === "bad-key" || /Key limit exceeded/.test(err.message ?? "")) stop = true;
        if (stop) break;
      }
    }
  }
  (summary.models as Record<string, unknown>)[model] = aggregate(model, scores);
}

summary.finishedAt = new Date().toISOString();
summary.spentUsdTotal = await spentUsd();
summary.blind = blind;
await mkdir(outDir, { recursive: true });
await writeFile(join(outDir, "summary.json"), JSON.stringify(summary, null, 1), "utf8");
// The demo shows latest.json; a latency-only rerun must not replace the model comparison.
if (!process.argv.includes("--no-latest")) await writeFile(join(PRIVATE_DIR, "eval", "latest.json"), JSON.stringify(summary), "utf8");
printTable(summary.models as Record<string, ReturnType<typeof aggregate>>);
console.log(`\nWritten ${outDir}. Ledger total $${(summary.spentUsdTotal as number).toFixed(4)}`);

function score(result: PageResult, gtAll: Parameters<typeof validGt>[0], size: { w: number; h: number }) {
  const gt = validGt(gtAll, size);
  const ts = Object.values(result.translations);
  let exact = 0;
  let edits = 0;
  let refLen = 0;
  let gtFound = 0;
  for (const g of gt) {
    const matched = matchRegions(g.bbox, result.regions);
    if (matched.length) gtFound++;
    const hyp = matched
      .map((r) => result.translations[r.id])
      .filter(Boolean)
      .sort((a, b) => a!.seq - b!.seq)
      .map((t) => t!.ja)
      .join("");
    const c = cer(hyp, g.ja_ocr_truth);
    edits += c.edits;
    refLen += c.refLen;
    if (normalizeJa(hyp) === normalizeJa(g.ja_ocr_truth)) exact++;
  }
  const roles: Record<string, number> = {};
  for (const t of ts) roles[t.role] = (roles[t.role] ?? 0) + 1;
  return {
    regions: result.regions.length,
    translated: ts.length,
    missing: result.missingIds.length,
    gt: gt.length,
    gtFound,
    exact,
    edits,
    refLen,
    firstRegionMs: result.timings.firstRegionMs,
    totalMs: result.timings.totalMs,
    costUsd: result.usage.costUsd ?? 0,
    roles,
  };
}

function collectBlind(model: string, result: PageResult, pageId: string, gtAll: Parameters<typeof validGt>[0], size: { w: number; h: number }) {
  for (const g of validGt(gtAll, size)) {
    const vi = matchRegions(g.bbox, result.regions)
      .map((r) => result.translations[r.id])
      .filter(Boolean)
      .sort((a, b) => a!.seq - b!.seq)
      .map((t) => t!.vi)
      .join(" / ");
    let item = blind.find((b) => b.pageId === pageId && b.gtId === g.bubble_id);
    if (!item) blind.push((item = { pageId, gtId: g.bubble_id, ja: g.ja_ocr_truth, outputs: {} }));
    item.outputs[model] = vi;
  }
}

function aggregate(model: string, scores: PageScore[]) {
  const ok = scores.filter((s) => s.ok);
  const first = ok.map((s) => s.firstRegionMs).filter((v): v is number => v !== undefined);
  const total = ok.map((s) => s.totalMs).filter((v): v is number => v !== undefined);
  const sum = (k: keyof PageScore) => ok.reduce((a, s) => a + (Number(s[k]) || 0), 0);
  const firstRun = ok.filter((s) => s.run === 1);
  const sum1 = (k: keyof PageScore) => firstRun.reduce((a, s) => a + (Number(s[k]) || 0), 0);
  const info = modelInfo(model);
  return {
    label: info.label,
    pagesOk: ok.length,
    pagesFailed: scores.length - ok.length,
    errors: scores.filter((s) => !s.ok).map((s) => `${s.pageId}: ${s.error}`).slice(0, 5),
    regionCoverage: `${sum1("translated")}/${sum1("regions")}`,
    gtExact: `${sum1("exact")}/${sum1("gt")}`,
    gtFound: `${sum1("gtFound")}/${sum1("gt")}`,
    cerVsLabels: sum1("refLen") ? sum1("edits") / sum1("refLen") : null,
    firstRegionMs: { p50: percentile(first, 0.5), p90: percentile(first, 0.9), p95: percentile(first, 0.95), n: first.length },
    pageMs: { p50: percentile(total, 0.5), p90: percentile(total, 0.9), p95: percentile(total, 0.95), n: total.length },
    costPerPageUsd: ok.length ? sum("costUsd") / ok.length : null,
    costTotalUsd: sum("costUsd"),
    roles: firstRun.reduce<Record<string, number>>((m, s) => {
      for (const [k, v] of Object.entries(s.roles)) m[k] = (m[k] ?? 0) + v;
      return m;
    }, {}),
  };
}

function printTable(rows: Record<string, ReturnType<typeof aggregate>>) {
  console.log("\n| Model | Pages ok | Regions translated | GT exact (vs labels) | CER vs labels | First region p50 | Page p50 | $/page |");
  console.log("|---|---|---|---|---|---|---|---|");
  for (const [, r] of Object.entries(rows)) {
    console.log(
      `| ${r.label} | ${r.pagesOk} | ${r.regionCoverage} | ${r.gtExact} | ${r.cerVsLabels === null ? "—" : (100 * r.cerVsLabels).toFixed(1) + "%"} | ${fmt(r.firstRegionMs.p50)} | ${fmt(r.pageMs.p50)} | ${r.costPerPageUsd === null ? "—" : "$" + r.costPerPageUsd.toFixed(5)} |`,
    );
  }
}

function fmt(ms: number) {
  return Number.isFinite(ms) ? `${(ms / 1000).toFixed(2)} s` : "—";
}
