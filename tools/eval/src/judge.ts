/**
 * Blind translation judge: a neutral model reads each page itself (numbered regions + zoomed
 * crops) and grades anonymized Vietnamese candidates per region. A screening signal only: the
 * team's blind rating decides the default model. Private output in .private/eval/<run>/.
 *
 *   npx tsx tools/eval/src/judge.ts --run bakeoff-20261019 --models a,b,c@other-run [--judge openai/gpt-5.6-terra] [--pages …]
 * A model written as `id@run` is read from that run's results instead of --run.
 */
import { appendFile, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { JsonObjectStream, type PageResult, type PromptPart } from "@lt/core";
import { decodeImage, listPages, markedPageDataUrl, PRIVATE_DIR, readPageImage, regionCrops, spentUsd, streamChat } from "@lt/server";

const arg = (name: string, def: string) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : def;
};
const run = arg("run", "bakeoff-20261019");
const models = arg("models", "").split(",").filter(Boolean);
const judge = arg("judge", "openai/gpt-5.6-terra");
const only = arg("pages", "").split(",").filter(Boolean);
const safe = (s: string) => s.replace(/[^a-zA-Z0-9._-]/g, "_");
const dir = join(PRIVATE_DIR, "eval", run);
const LETTERS = "ABCDEFGH";

const SYSTEM = `You are a senior Japanese→Vietnamese manga translator and editor, judging translations blind.
The page image shows numbered regions; zoomed crops of small text follow. Read the Japanese yourself from the image and use the art for context (who speaks to whom).
For every region id, grade each candidate letter with [m, n, a]:
 m meaning 0-3: 3 faithful (negation, subject/object, giving/receiving, question, condition, nuance right); 2 small nuance loss; 1 misleading error; 0 wrong, missing, untranslated or invented.
 n Vietnamese naturalness 0-2: 2 natural and fits the character; 1 understandable but stiff or awkward; 0 broken.
 a address 0-2: 2 pronouns and forms of address fit speaker→listener, meaningful Japanese honorifics kept and never stacked (not "chị nee-chan"); 1 questionable; 0 wrong gender, relationship or register.
"severe" lists every letter with a serious error: meaning flipped or lost, wrong gender or relationship, invented content, untranslated text.
Sound effects: judge meaning only and give n=2, a=2 unless clearly broken.
Output one JSON object per line in region order and nothing else:
{"id":"r1","A":[3,2,2],"B":[2,1,2],"severe":["B"],"best":"A","why":"at most 12 English words"}`;

/** Deterministic per-page shuffle so letters never map to the same model across pages. */
function shuffled<T>(items: T[], seedText: string): T[] {
  let seed = [...seedText].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
  const a = [...items];
  for (let i = a.length - 1; i > 0; i--) {
    seed = (seed * 1103515245 + 12345) >>> 0;
    const j = seed % (i + 1);
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

interface Grade {
  id: string;
  severe?: string[];
  best?: string;
  why?: string;
  [letter: string]: unknown;
}

const tally = new Map(models.map((m) => [m, { graded: 0, m: 0, n: 0, a: 0, severe: 0, best: 0, missing: 0 }]));
const pagesOut: Array<Record<string, unknown>> = [];

async function judgePage(page: Awaited<ReturnType<typeof listPages>>[number]) {
  const results: PageResult[] = [];
  for (const m of models) {
    try {
      const [id, from] = m.split("@");
      results.push(JSON.parse(await readFile(join(from ? join(PRIVATE_DIR, "eval", from) : dir, safe(id), `${safe(page.id)}.json`), "utf8")) as PageResult);
    } catch {
      console.log(`${page.id}: no result for ${m}, skipped`);
      return;
    }
  }
  const regions = [...results[0].regions].sort((a, b) => a.order - b.order);
  const order = shuffled(models, page.id);
  const block = regions
    .map((r) => `${r.id}\n${order.map((m, i) => `${LETTERS[i]}: ${results[models.indexOf(m)].translations[r.id]?.vi?.trim() || "(no translation)"}`).join("\n")}`)
    .join("\n\n");
  const decoded = await decodeImage(await readPageImage(page));
  const parts: PromptPart[] = [
    { type: "text", text: `Page ${page.id}. Candidates per region:\n\n${block}` },
    { type: "image", dataUrl: await markedPageDataUrl(decoded, regions) },
  ];
  for (const c of await regionCrops(decoded, regions)) parts.push({ type: "text", text: `Zoomed crop of ${c.id}:` }, { type: "image", dataUrl: c.dataUrl });

  const grades: Grade[] = [];
  const parser = new JsonObjectStream((v) => grades.push(v as Grade));
  // OpenRouter reserves max_tokens × price while a request is in flight: keep the cap modest.
  const stats = await streamChat({ model: judge, system: SYSTEM, parts, purpose: "judge", pageId: page.id, maxTokens: 5000, extra: { reasoning: { effort: "low" } }, onText: (d) => parser.push(d) });

  for (const g of grades) {
    if (!regions.some((r) => r.id === g.id)) continue;
    order.forEach((m, i) => {
      const s = g[LETTERS[i]];
      if (!Array.isArray(s) || s.length < 3) return;
      const t = tally.get(m)!;
      t.graded++;
      t.m += Number(s[0]) || 0;
      t.n += Number(s[1]) || 0;
      t.a += Number(s[2]) || 0;
      if (g.severe?.includes(LETTERS[i])) t.severe++;
      if (g.best === LETTERS[i]) t.best++;
      if (!results[models.indexOf(m)].translations[g.id]?.vi?.trim()) t.missing++;
    });
  }
  const row = { page: page.id, letters: Object.fromEntries(order.map((m, i) => [LETTERS[i], m])), regions: regions.length, graded: grades.length, costUsd: stats.costUsd, ms: Math.round(stats.totalMs), grades };
  pagesOut.push(row);
  // Paid output is kept even if the run stops early.
  await appendFile(join(dir, `judge-${safe(judge)}.jsonl`), `${JSON.stringify(row)}\n`, "utf8");
  console.log(`${page.id}: ${grades.length}/${regions.length} regions graded in ${Math.round(stats.totalMs)} ms, $${stats.costUsd.toFixed(4)}`);
}

const pages = (await listPages()).filter((p) => !only.length || only.includes(p.id));
// One page at a time: in-flight reservations count against the account balance.
for (const p of pages) await judgePage(p).catch((e) => console.log(`${p.id}: ERROR ${(e as Error).message}`));

await writeFile(join(dir, `judge-${safe(judge)}.json`), JSON.stringify({ judge, models, pages: pagesOut, tally: Object.fromEntries(tally) }, null, 1), "utf8");
console.log(`\nJudge ${judge} (blind, letters shuffled per page)`);
console.log("| Model | Regions graded | Meaning 0–3 | Natural 0–2 | Address 0–2 | Severe | Best |");
console.log("|---|---|---|---|---|---|---|");
for (const [m, t] of tally) {
  const avg = (x: number) => (t.graded ? (x / t.graded).toFixed(2) : "—");
  const pct = (x: number) => (t.graded ? `${((100 * x) / t.graded).toFixed(0)}%` : "—");
  console.log(`| ${m} | ${t.graded} | ${avg(t.m)} | ${avg(t.n)} | ${avg(t.a)} | ${pct(t.severe)} | ${pct(t.best)} |`);
}
console.log(`ledger total $${(await spentUsd()).toFixed(4)}`);
