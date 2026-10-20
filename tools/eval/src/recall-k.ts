/**
 * Sweet spot for the recent-dialogue window K (L0): read every series page by page, in
 * order, once per K, each K with its own story memory (background updates as in the
 * server), and compare quality, prompt size, latency and cost. Private output in
 * .private/eval/<run>/; page results in .private/eval/<run>-k<K>/<model>/ (score-run.ts works on them).
 *
 *   npx tsx tools/eval/src/recall-k.ts [--run recall-k] [--k 0,10,20,40,80] [--sets local,set1]
 *        [--model anthropic/claude-haiku-5.5] [--cap 0.6] [--judge deepseek/deepseek-v4.1-flash-1017] [--score-only] [--books Uchi] [--refs]
 *
 * Within a series the K configurations are interleaved page by page (order rotated), so
 * network conditions are shared; series run in parallel. Resumable: a page whose result
 * and memory snapshot exist is not translated again.
 */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import {
  chrfScore,
  chrfStats,
  emptyMemory,
  estimateTokens,
  JsonObjectStream,
  mergePage,
  volatileContext,
  type ChrfStats,
  type PageResult,
  type SeriesMemory,
} from "@lt/core";
import { applyPlanned, listPages, planMemoryUpdate, PRIVATE_DIR, readPageImage, spentUsd, streamChat, translatePage, UPDATE_EVERY_LINES, type DatasetPage } from "@lt/server";
import { matchRegions, validGt } from "./gt";

const arg = (name: string, def: string) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : def;
};
const run = arg("run", "recall-k");
const ks = arg("k", "0,10,20,40,80").split(",").map(Number);
const sets = arg("sets", "local,set1").split(",");
const model = arg("model", "anthropic/claude-haiku-5.5");
const cap = Number(arg("cap", "0.6"));
const judgeModel = arg("judge", "");
const scoreOnly = process.argv.includes("--score-only");
// --refs: show the faces of the characters in the scene, cropped from pages already read (the memory keeps the box only).
const refs = process.argv.includes("--refs");
const safe = (s: string) => s.replace(/[^a-zA-Z0-9._-]/g, "_");
const out = join(PRIVATE_DIR, "eval", run);
const pageDir = (k: number) => join(PRIVATE_DIR, "eval", `${run}-k${k}`, safe(model));
await mkdir(out, { recursive: true });
for (const k of ks) await mkdir(pageDir(k), { recursive: true });

// --books Uchi,ARMS: only titles containing one of these.
const books = arg("books", "").split(",").filter(Boolean);
const pages = (await listPages()).filter((p) => sets.includes(p.set) && (!books.length || books.some((b) => p.title.includes(b) || p.id.includes(b))));
const series = new Map<string, DatasetPage[]>();
for (const p of pages) series.set(`${p.set}|${p.seriesId}`, [...(series.get(`${p.set}|${p.seriesId}`) ?? []), p]);
for (const list of series.values()) list.sort((a, b) => a.position.chapter - b.position.chapter || a.position.page - b.position.page);

interface Row {
  page: string;
  series: string;
  k: number;
  promptTokens: number;
  cachedTokens: number;
  completionTokens: number;
  costUsd: number;
  bgCostUsd: number;
  firstRegionMs?: number;
  volatileTokens: number;
  recall?: { regions: string[]; cards: number; revised: number; notes: string[] };
}

const rowsFile = join(out, "rows.jsonl");
const startSpent = await spentUsd();
let stop = false;

async function readJson<T>(f: string): Promise<T | undefined> {
  try {
    return JSON.parse(await readFile(f, "utf8")) as T;
  } catch {
    return undefined;
  }
}

async function readSeries(key: string, list: DatasetPage[]) {
  const mems = new Map<number, SeriesMemory>(ks.map((k) => [k, emptyMemory(list[0].seriesId, list[0].title)]));
  for (const [i, page] of list.entries()) {
    // Rotate the order of K on each page: no configuration always goes first.
    const order = ks.map((_, j) => ks[(i + j) % ks.length]);
    for (const k of order) {
      if (stop) return;
      const resFile = join(pageDir(k), `${safe(page.id)}.json`);
      const memFile = join(out, `mem-k${k}-${safe(key)}.json`);
      const snap = await readJson<{ after: string; memory: SeriesMemory }>(memFile);
      const done = await readJson<PageResult>(resFile);
      if (done && snap && list.findIndex((p) => p.id === snap.after) >= i) {
        if (snap.after === page.id) mems.set(k, snap.memory);
        continue;
      }
      if ((await spentUsd()) - startSpent > cap) {
        console.log(`spend cap $${cap} reached: stopping`);
        stop = true;
        return;
      }
      let mem = mems.get(k)!;
      const ctx = { recentLines: k, recentTokens: 1e9, volatileTokens: 1e9 };
      const volatileTokens = estimateTokens(volatileContext(mem, page.position, ctx.volatileTokens, ctx));
      let result: PageResult;
      try {
        result = await translatePage(
          { id: page.id, title: page.title, seriesId: page.seriesId, position: page.position, bytes: await readPageImage(page) },
          {
            model,
            memory: mem,
            context: ctx,
            ...(refs && {
              refImage: async (id: string) => {
                const p = pages.find((x) => x.id === id);
                return p ? readPageImage(p) : undefined;
              },
            }),
          },
        );
      } catch (e) {
        console.log(`${page.id} K=${k} ERROR ${(e as Error).message}`);
        continue;
      }
      mem = mergePage(mem, page.id, page.position, result.notes, Object.values(result.translations)).memory;
      let bgCostUsd = 0;
      const last = i === list.length - 1;
      if ((mem.pending?.length ?? 0) >= UPDATE_EVERY_LINES || last) {
        try {
          const plan = await planMemoryUpdate(mem, last);
          if (plan) {
            mem = applyPlanned(mem, plan);
            bgCostUsd = plan.costUsd;
          }
        } catch (e) {
          console.log(`   memory update failed: ${(e as Error).message}`);
        }
      }
      mems.set(k, mem);
      await writeFile(resFile, JSON.stringify(result), "utf8");
      await writeFile(memFile, JSON.stringify({ after: page.id, memory: mem }), "utf8");
      const u = result.usage;
      const row: Row = {
        page: page.id,
        series: key,
        k,
        promptTokens: u.promptTokens ?? 0,
        cachedTokens: u.cachedTokens ?? 0,
        completionTokens: u.completionTokens ?? 0,
        costUsd: u.costUsd ?? 0,
        bgCostUsd,
        firstRegionMs: result.timings.firstRegionMs,
        volatileTokens,
        recall: result.recall && { regions: result.recall.request.regions, cards: result.recall.cards, revised: result.recall.revised.length, notes: result.recall.notes.map((n) => `${n.regionId}: ${n.text}`) },
      };
      await writeFile(rowsFile, JSON.stringify(row) + "\n", { flag: "a" });
      console.log(
        `${page.id.padEnd(34)} K=${String(k).padStart(2)} in ${row.promptTokens} (ctx ~${volatileTokens}) first ${row.firstRegionMs} ms $${row.costUsd.toFixed(5)}` +
          (bgCostUsd ? ` bg $${bgCostUsd.toFixed(5)}` : "") +
          (row.recall ? ` recall ${row.recall.regions.join(",")} cards ${row.recall.cards} ps ${row.recall.notes.length}` : ""),
      );
    }
  }
}

if (!scoreOnly) {
  await Promise.all([...series].map(([key, list]) => readSeries(key, list)));
  console.log(`spent this run: $${((await spentUsd()) - startSpent).toFixed(4)}`);
}

// ---------------------------------------------------------------- scoring

const rows = (await readFile(rowsFile, "utf8").catch(() => ""))
  .split(/\r?\n/)
  .filter(Boolean)
  .map((l) => JSON.parse(l) as Row);
// The latest row per (page, K) wins (a resumed page may have been logged twice).
const latest = new Map<string, Row>();
for (const r of rows) latest.set(`${r.page}|${r.k}`, r);

/** Vietnamese person pronouns and address terms used for xưng hô. */
const PRONOUNS = new Set(["tôi", "tớ", "mình", "tao", "ta", "tui", "em", "anh", "chị", "cậu", "mày", "bạn", "ông", "bà", "cô", "chú", "con", "cháu", "bác", "ngươi", "nhóc", "bố", "mẹ", "ba", "má"]);
const pronounsOf = (s: string) => new Set(s.toLowerCase().normalize("NFC").split(/[^\p{L}]+/u).filter((w) => PRONOUNS.has(w)));

interface Line {
  gt: string;
  ja: string;
  gold: string;
  vi: Record<number, string>;
  who: Record<number, string>;
}
const linesByPage = new Map<string, Line[]>();
const stats: Record<number, { chrf: ChrfStats[]; pron: number; pronOf: number; found: number; gt: number }> = {};
for (const k of ks) stats[k] = { chrf: [], pron: 0, pronOf: 0, found: 0, gt: 0 };
const byPage: Record<number, Map<string, ChrfStats[]>> = Object.fromEntries(ks.map((k) => [k, new Map()]));
for (const page of pages) {
  const lines: Line[] = validGt(page.gt, page.size)
    .filter((g) => g.vi_gold_trans?.trim())
    .sort((a, b) => a.reading_order - b.reading_order)
    .map((g) => ({ gt: g.bubble_id, ja: g.ja_ocr_truth, gold: g.vi_gold_trans, vi: {}, who: {} }));
  for (const k of ks) {
    const r = await readJson<PageResult>(join(pageDir(k), `${safe(page.id)}.json`));
    if (!r) continue;
    for (const [i, g] of validGt(page.gt, page.size).filter((x) => x.vi_gold_trans?.trim()).sort((a, b) => a.reading_order - b.reading_order).entries()) {
      const ts = matchRegions(g.bbox, r.regions).map((x) => r.translations[x.id]).filter(Boolean).sort((a, b) => a!.seq - b!.seq);
      const vi = ts.map((t) => t!.vi).join(" ");
      lines[i].vi[k] = vi;
      lines[i].who[k] = ts.map((t) => `${t!.speaker}→${t!.to}`).join(", ");
      stats[k].gt++;
      if (ts.length) stats[k].found++;
      const cs = chrfStats(vi, g.vi_gold_trans);
      stats[k].chrf.push(cs);
      byPage[k].set(page.id, [...(byPage[k].get(page.id) ?? []), cs]);
      const gold = pronounsOf(g.vi_gold_trans);
      if (gold.size) {
        stats[k].pronOf++;
        const hyp = pronounsOf(vi);
        if (![...hyp].some((p) => gold.has(p))) stats[k].pron++;
      }
    }
  }
  linesByPage.set(page.id, lines);
}

// ---------------------------------------------------------------- blind judge (optional)

const JUDGE_SYSTEM = `You check Vietnamese translations of one Japanese manga page for two kinds of error only.
You get each line's Japanese, the translation team's reference Vietnamese, and candidate translations labelled with letters (their order is random; they differ only in how much recent dialogue the translator saw). A candidate may show the speaker→listener it assumed.
For each candidate count:
- pronoun: lines whose Vietnamese pronouns or address terms (xưng hô: tôi/tớ/mình/tao/anh/em/chị/cậu/mày/ông/bà…) imply a different speaker–listener relationship (age, closeness, politeness, gender) than the reference, or switch pronouns for the same pair within the page. A line with no pronoun where the reference also has none is fine.
- speaker: lines where who says it, or to whom, is wrong so that who does what to whom changes.
Do not count wording, style or any other difference. Return one JSON object only: {"A":{"pronoun":0,"speaker":0},"B":{…}}`;

const judged: Record<number, { pronoun: number; speaker: number; pages: number }> = {};
for (const k of ks) judged[k] = { pronoun: 0, speaker: 0, pages: 0 };
let judgeCost = 0;
if (judgeModel) {
  const judgeFile = join(out, `judge-${safe(judgeModel)}.jsonl`);
  const prev = new Map(
    (await readFile(judgeFile, "utf8").catch(() => ""))
      .split(/\r?\n/)
      .filter(Boolean)
      .map((l) => JSON.parse(l) as { page: string; byK: Record<number, { pronoun: number; speaker: number }> })
      .map((x) => [x.page, x.byK]),
  );
  for (const [pi, page] of pages.entries()) {
    const lines = linesByPage.get(page.id) ?? [];
    const present = ks.filter((k) => lines.some((l) => l.vi[k] !== undefined));
    if (!lines.length || present.length < ks.length) continue;
    let byK = prev.get(page.id);
    if (!byK) {
      if ((await spentUsd()) - startSpent > cap) break;
      // A fixed shuffle per page: letters never map to the same K across pages.
      const order = present.map((k, j) => ({ k, r: Math.sin((pi + 1) * 97.13 + j * 13.7) })).sort((a, b) => a.r - b.r).map((x) => x.k);
      const letters = order.map((_, j) => String.fromCharCode(65 + j));
      const body = lines
        .map((l, i) => [`#${i + 1} JA: ${l.ja}`, `   REF: ${l.gold}`, ...order.map((k, j) => `   ${letters[j]}: ${l.who[k] ? `[${l.who[k]}] ` : ""}${l.vi[k] || "(missing)"}`)].join("\n"))
        .join("\n");
      let value: Record<string, { pronoun?: number; speaker?: number }> | undefined;
      const parser = new JsonObjectStream((v) => {
        value ??= v as typeof value;
      });
      const s = await streamChat({ model: judgeModel, system: JUDGE_SYSTEM, parts: [{ type: "text", text: body }], purpose: "judge-k", pageId: page.id, maxTokens: 400, sort: "price", extra: { reasoning: { enabled: false } }, onText: (d) => parser.push(d) });
      judgeCost += s.costUsd;
      if (!value) continue;
      byK = {};
      order.forEach((k, j) => {
        const v = value![letters[j]] ?? {};
        byK![k] = { pronoun: Number(v.pronoun) || 0, speaker: Number(v.speaker) || 0 };
      });
      await writeFile(judgeFile, JSON.stringify({ page: page.id, byK }) + "\n", { flag: "a" });
    }
    for (const k of ks) {
      judged[k].pronoun += byK[k]?.pronoun ?? 0;
      judged[k].speaker += byK[k]?.speaker ?? 0;
      judged[k].pages++;
    }
  }
}

// ---------------------------------------------------------------- report

const median = (xs: number[]) => {
  const s = xs.filter(Number.isFinite).sort((a, b) => a - b);
  return s.length ? s[Math.floor((s.length - 1) / 2)] : NaN;
};
/**
 * Paired bootstrap over pages (2 000 resamples): 95% interval of chrF(K) − chrF(reference K).
 * Pages are the unit: lines of one page are not independent.
 */
function bootstrapDelta(k: number, ref: number): [number, number] {
  const ids = [...byPage[k].keys()].filter((id) => byPage[ref].has(id));
  let seed = 12345;
  const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
  const deltas: number[] = [];
  for (let b = 0; b < 2000; b++) {
    const pick = ids.map(() => ids[Math.floor(rnd() * ids.length)]);
    deltas.push(chrfScore(pick.flatMap((id) => byPage[k].get(id)!)) - chrfScore(pick.flatMap((id) => byPage[ref].get(id)!)));
  }
  deltas.sort((a, b) => a - b);
  return [deltas[Math.floor(0.025 * deltas.length)], deltas[Math.floor(0.975 * deltas.length)]];
}
const refK = Math.max(...ks);

const table: string[] = [
  `| K | Pages | chrF vs gold | Δ chrF vs K=${refK} [95% CI] | Pronoun mismatch (auto) | Judge: pronoun / speaker errors | Input tokens/page (mean) | Recent-context tokens (mean) | First region p50 | $/page (translate + recall) | Background $/page | Recall: pages asked / with cards / P/S |`,
  "|---|---|---|---|---|---|---|---|---|---|---|---|",
];
const summary: Record<string, unknown>[] = [];
for (const k of ks) {
  const rs = [...latest.values()].filter((r) => r.k === k);
  if (!rs.length) continue;
  const mean = (f: (r: Row) => number) => rs.reduce((a, r) => a + f(r), 0) / rs.length;
  const asked = rs.filter((r) => r.recall).length;
  const withCards = rs.filter((r) => (r.recall?.cards ?? 0) > 0).length;
  const ps = rs.reduce((a, r) => a + (r.recall?.notes.length ?? 0), 0);
  const s = stats[k];
  const row = {
    k,
    pages: rs.length,
    chrf: chrfScore(s.chrf),
    ci: k === refK ? [0, 0] : bootstrapDelta(k, refK),
    pronounMismatch: s.pronOf ? s.pron / s.pronOf : NaN,
    pronounLines: s.pronOf,
    judge: judgeModel ? judged[k] : undefined,
    inputTokens: mean((r) => r.promptTokens),
    volatileTokens: mean((r) => r.volatileTokens),
    firstRegionP50: median(rs.map((r) => r.firstRegionMs ?? NaN)),
    usdPerPage: mean((r) => r.costUsd),
    bgUsdPerPage: mean((r) => r.bgCostUsd),
    recall: { asked, withCards, ps },
  };
  summary.push(row);
  table.push(
    `| ${k} | ${rs.length} | ${row.chrf.toFixed(2)} | ${k === refK ? "—" : `${(row.chrf - chrfScore(stats[refK].chrf)).toFixed(2)} [${row.ci.map((x) => x.toFixed(2)).join(", ")}]`} | ${(100 * row.pronounMismatch).toFixed(1)}% of ${row.pronounLines} | ${row.judge ? `${row.judge.pronoun} / ${row.judge.speaker} (${row.judge.pages} p)` : "—"} | ${Math.round(row.inputTokens)} | ${Math.round(row.volatileTokens)} | ${(row.firstRegionP50 / 1000).toFixed(2)} s | $${row.usdPerPage.toFixed(5)} | $${row.bgUsdPerPage.toFixed(5)} | ${asked} / ${withCards} / ${ps} |`,
  );
}
console.log(table.join("\n"));
if (judgeModel) console.log(`judge ${judgeModel}: $${judgeCost.toFixed(4)} this run`);
await writeFile(join(out, "summary.json"), JSON.stringify({ model, ks, sets, judgeModel, summary }, null, 1), "utf8");
await writeFile(join(out, "table.md"), table.join("\n") + "\n", "utf8");
const notes = [...latest.values()].filter((r) => r.recall).map((r) => ({ page: r.page, k: r.k, ...r.recall }));
await writeFile(join(out, "recall.json"), JSON.stringify(notes, null, 1), "utf8");
