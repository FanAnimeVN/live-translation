/**
 * Blind judge for background summaries: a neutral model reads the dialogue the summary
 * models saw and grades their anonymized outputs (faithfulness first). Text only, cheap.
 * Reads .private/eval/<run>/bg-compare.json; writes bg-judge-<judge>.jsonl next to it.
 *
 *   npx tsx tools/eval/src/bg-judge.ts --run ctx-v2b [--judge openai/gpt-5.6-terra]
 */
import { appendFile, readFile } from "node:fs/promises";
import { join } from "node:path";
import { emptyMemory, JsonObjectStream, mergePage, type PageResult, type SeriesMemory } from "@lt/core";
import { listPages, PRIVATE_DIR, spentUsd, streamChat } from "@lt/server";

const arg = (name: string, def: string) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : def;
};
const run = arg("run", "ctx-v2b");
const judge = arg("judge", "openai/gpt-5.6-terra");
const pageModel = arg("model", "anthropic/claude-haiku-5.5");
const safe = (s: string) => s.replace(/[^a-zA-Z0-9._-]/g, "_");
const dir = join(PRIVATE_DIR, "eval", run);
const LETTERS = "ABCDEFGH";

const SYSTEM = `You audit story-memory summaries written for a manga translator. You get the dialogue the summarizers read (ids PAGE:REGION, speaker→listener when known, Japanese => draft Vietnamese) and several anonymized JSON outputs.
Grade each letter:
 f faithfulness 0-3: 3 every statement is supported by the dialogue; 2 one small overreach; 1 a wrong fact or invented relationship/gender; 0 several.
 c coverage 0-2: the key events and who is who are there.
 v Vietnamese 0-2: natural, clear.
 h hygiene 0-2: character entries are real characters with names used consistently (no phrases, objects or "unknown" listed as characters; relations not reversed).
List concrete errors per letter (short). Output exactly one JSON object and nothing else:
{"A":{"f":3,"c":2,"v":2,"h":2,"errors":["…"]},"B":{…}}`;

function shuffled<T>(items: T[], seedText: string): T[] {
  let seed = [...seedText].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 11);
  const a = [...items];
  for (let i = a.length - 1; i > 0; i--) {
    seed = (seed * 1103515245 + 12345) >>> 0;
    const j = seed % (i + 1);
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

const rows = JSON.parse(await readFile(join(dir, "bg-compare.json"), "utf8")) as Array<{ series: string; model: string; update?: unknown; costUsd?: number; ms?: number }>;
const memories = new Map<string, SeriesMemory>();
for (const page of await listPages()) {
  let result: PageResult;
  try {
    result = JSON.parse(await readFile(join(dir, safe(pageModel), `${safe(page.id)}.json`), "utf8")) as PageResult;
  } catch {
    continue;
  }
  const mem = memories.get(page.seriesId) ?? emptyMemory(page.seriesId, page.title);
  memories.set(page.seriesId, mergePage(mem, page.id, page.position, result.notes, Object.values(result.translations)).memory);
}

const tally = new Map<string, { n: number; f: number; c: number; v: number; h: number; errors: number; cost: number; ms: number }>();
for (const [series, mem] of memories) {
  const outs = rows.filter((r) => r.series === series && r.update);
  if (outs.length < 2) continue;
  const order = shuffled(outs, series);
  const dialogue = (mem.pending ?? []).map((l) => `${l.pageId}:${l.regionId} [${l.speaker}${l.to && l.to !== "unknown" ? `→${l.to}` : ""}] ${l.ja} => ${l.vi}`).join("\n");
  const block = order.map((o, i) => `${LETTERS[i]}:\n${JSON.stringify(o.update)}`).join("\n\n");
  let graded: Record<string, { f: number; c: number; v: number; h: number; errors?: string[] }> | null = null;
  const parser = new JsonObjectStream((v) => {
    graded ??= v as typeof graded;
  });
  const stats = await streamChat({
    model: judge,
    system: SYSTEM,
    parts: [{ type: "text", text: `DIALOGUE (${series}):\n${dialogue}\n\nOUTPUTS:\n${block}` }],
    purpose: "bg-judge",
    maxTokens: 4000,
    extra: { reasoning: { effort: "low" } },
    onText: (d) => parser.push(d),
  });
  const g = (graded ?? {}) as Record<string, { f: number; c: number; v: number; h: number; errors?: string[] }>;
  await appendFile(join(dir, `bg-judge-${safe(judge)}.jsonl`), `${JSON.stringify({ series, letters: Object.fromEntries(order.map((o, i) => [LETTERS[i], o.model])), graded: g, costUsd: stats.costUsd })}\n`, "utf8");
  order.forEach((o, i) => {
    const s = g[LETTERS[i]];
    if (!s) return;
    const t = tally.get(o.model) ?? { n: 0, f: 0, c: 0, v: 0, h: 0, errors: 0, cost: 0, ms: 0 };
    t.n++;
    t.f += s.f;
    t.c += s.c;
    t.v += s.v;
    t.h += s.h;
    t.errors += s.errors?.length ?? 0;
    t.cost += o.costUsd ?? 0;
    t.ms += o.ms ?? 0;
    tally.set(o.model, t);
  });
  console.log(`${series}: graded ${Object.keys(g).length}/${order.length} in ${Math.round(stats.totalMs)} ms, $${stats.costUsd.toFixed(4)}`);
}
console.log("\n| Summary model | Series | Faithful 0–3 | Coverage 0–2 | Vietnamese 0–2 | Hygiene 0–2 | Errors | Cost (sum) | Time (sum) |");
console.log("|---|---|---|---|---|---|---|---|---|");
for (const [m, t] of [...tally].sort((a, b) => b[1].f / b[1].n - a[1].f / a[1].n)) {
  const avg = (x: number) => (x / t.n).toFixed(2);
  console.log(`| ${m} | ${t.n} | ${avg(t.f)} | ${avg(t.c)} | ${avg(t.v)} | ${avg(t.h)} | ${t.errors} | $${t.cost.toFixed(5)} | ${(t.ms / 1000).toFixed(1)} s |`);
}
console.log(`ledger total $${(await spentUsd()).toFixed(4)}`);
