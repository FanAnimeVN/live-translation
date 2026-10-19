/**
 * Read the GT series in order with context v2 and report cost, caching, latency and
 * the memory that was built. Optionally compares two background models on the same
 * pending dialogue. Private output in .private/eval/<run>/.
 *
 *   npx tsx tools/eval/src/context-run.ts --run ctx-v2 [--model anthropic/claude-haiku-5.5]
 *        [--bg deepseek/deepseek-v4.1-flash] [--alt-bg z-ai/glm-5.3-flash,anthropic/claude-haiku-5.5]
 *        [--anilist aisazu-ni-wa-irarenai=91059]
 * Page results go to .private/eval/<run>/<model>/ so `render.ts <model> --eval <run>` can score the lettering.
 */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { emptyMemory, mergePage, stableContext, volatileContext, type SeriesMemory } from "@lt/core";
import {
  applyPlanned,
  bootstrapFromMetadata,
  listPages,
  planMemoryUpdate,
  PRIVATE_DIR,
  readPageImage,
  searchSeries,
  spentUsd,
  translatePage,
  UPDATE_EVERY_LINES,
} from "@lt/server";

const arg = (name: string, def: string) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : def;
};
const run = arg("run", "ctx-v2");
const model = arg("model", "anthropic/claude-haiku-5.5");
const bg = arg("bg", "deepseek/deepseek-v4.1-flash");
const altBgs = arg("alt-bg", "").split(",").filter(Boolean);
const anilist = new Map(
  arg("anilist", "aisazu-ni-wa-irarenai=91059")
    .split(",")
    .filter(Boolean)
    .map((kv) => kv.split("=") as [string, string]),
);
const out = join(PRIVATE_DIR, "eval", run);
const safe = (s: string) => s.replace(/[^a-zA-Z0-9._-]/g, "_");
const pageDir = join(out, safe(model));
await mkdir(pageDir, { recursive: true });
const startedAt = new Date().toISOString();

const pages = await listPages();
const memories = new Map<string, SeriesMemory>();
const rows: Array<Record<string, unknown>> = [];
const bgRuns: Array<Record<string, unknown>> = [];

async function summarize(mem: SeriesMemory, force: boolean): Promise<SeriesMemory> {
  for (const altBg of altBgs) {
    try {
      const alt = await planMemoryUpdate(mem, force, altBg);
      if (alt) bgRuns.push({ model: altBg, ms: alt.ms, costUsd: alt.costUsd, update: alt.update });
    } catch (e) {
      bgRuns.push({ model: altBg, error: (e as Error).message });
    }
  }
  const plan = await planMemoryUpdate(mem, force, bg);
  if (!plan) return mem;
  bgRuns.push({ model: bg, ms: plan.ms, costUsd: plan.costUsd, update: plan.update });
  console.log(`   memory update (${bg}) ${plan.ms} ms $${plan.costUsd.toFixed(5)}`);
  return applyPlanned(mem, plan);
}

for (const page of pages) {
  let mem = memories.get(page.seriesId);
  if (!mem) {
    mem = emptyMemory(page.seriesId, page.title);
    const id = anilist.get(page.seriesId);
    if (id) {
      const cands = await searchSeries(page.title);
      console.log(`${page.title}: AniList candidates`, cands.slice(0, 3).map((c) => `${c.id} ${c.title.romaji} sim=${c.similarity.toFixed(2)}`).join(" | "));
      const res = await bootstrapFromMetadata(mem, Number(id));
      mem = res.memory;
      console.log(`   profile from metadata in ${res.ms} ms $${res.costUsd.toFixed(5)}:`, JSON.stringify(mem.profile).slice(0, 300));
    }
  }
  const stableChars = stableContext(mem, page.position).length;
  const volatileChars = volatileContext(mem, page.position).length;
  let result: Awaited<ReturnType<typeof translatePage>>;
  try {
    result = await translatePage(
      { id: page.id, title: page.title, seriesId: page.seriesId, position: page.position, bytes: await readPageImage(page) },
      { model, memory: mem },
    );
  } catch (e) {
    console.log(`${page.id.padEnd(9)} ERROR ${(e as Error).message}`);
    rows.push({ page: page.id, error: (e as Error).message });
    memories.set(page.seriesId, mem);
    continue;
  }
  mem = mergePage(mem, page.id, page.position, result.notes, Object.values(result.translations)).memory;
  if ((mem.pending?.length ?? 0) >= UPDATE_EVERY_LINES) mem = await summarize(mem, false);
  memories.set(page.seriesId, mem);
  const u = result.usage;
  rows.push({ page: page.id, promptTokens: u.promptTokens, cachedTokens: u.cachedTokens, costUsd: u.costUsd, first: result.timings.firstRegionMs, total: result.timings.totalMs, stableChars, volatileChars });
  await writeFile(join(pageDir, `${safe(page.id)}.json`), JSON.stringify(result), "utf8");
  console.log(
    `${page.id.padEnd(9)} prompt ${u.promptTokens} (cached ${u.cachedTokens ?? 0}) out ${u.completionTokens} $${(u.costUsd ?? 0).toFixed(5)} ` +
      `first ${result.timings.firstRegionMs} ms total ${result.timings.totalMs} ms | ctx stable ${stableChars} ch, recent ${volatileChars} ch`,
  );
}

for (const [id, mem] of memories) {
  const final = await summarize(mem, true);
  memories.set(id, final);
  await writeFile(join(out, `memory-${id}.json`), JSON.stringify(final, null, 1), "utf8");
}
await writeFile(join(out, "background-updates.json"), JSON.stringify(bgRuns, null, 1), "utf8");
await writeFile(join(out, "rows.json"), JSON.stringify(rows, null, 1), "utf8");

const sum = (k: string) => rows.reduce((s, r) => s + (Number(r[k]) || 0), 0);
console.log(`\nTOTAL prompt ${sum("promptTokens")} tokens, cached ${sum("cachedTokens")}, translation $${sum("costUsd").toFixed(5)}`);
console.log(`background updates: ${bgRuns.map((b) => `${b.model} ${b.ms}ms $${Number(b.costUsd).toFixed(5)}`).join(" | ")}`);
console.log(`ledger total $${(await spentUsd()).toFixed(4)}`);

// Per-call network view from the ledger: provider, time to first byte, request size.
const ledger = (await readFile(join(PRIVATE_DIR, "ledger.jsonl"), "utf8"))
  .split(/\r?\n/)
  .filter(Boolean)
  .map((l) => JSON.parse(l) as { at: string; model: string; purpose: string; pageId?: string; ok: boolean; ms?: number; ttfbMs?: number; provider?: string; reqKb?: number; retries?: number; costUsd: number })
  .filter((e) => e.at >= startedAt);
for (const e of ledger)
  console.log(`${e.purpose.padEnd(16)} ${e.model.padEnd(30)} ${(e.pageId ?? "").padEnd(9)} ${e.ok ? "ok " : "ERR"} ttfb ${e.ttfbMs ?? "-"} ms total ${e.ms} ms ${e.reqKb ?? "?"} kB ${e.provider ?? ""}${e.retries ? ` retries ${e.retries}` : ""} $${e.costUsd.toFixed(5)}`);
await writeFile(join(out, "ledger.json"), JSON.stringify(ledger, null, 1), "utf8");
for (const [id, mem] of memories) {
  console.log(`\n== ${id}`);
  console.log(stableContext(mem, { chapter: 99, page: 99 }));
  console.log(volatileContext(mem, { chapter: 99, page: 99 }).split("Recent dialogue")[0]);
}
