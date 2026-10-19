/**
 * Text-only translation quality and speed: the labelled Japanese of each bubble (perfect OCR)
 * translated alone, scored with chrF against the team's gold Vietnamese. Separates the
 * translator from reading and speaker attribution, so local translation models (Hy-MT2) can be
 * compared with the cloud reader on equal footing. Each model sees the two previous bubbles of
 * the page as context. Private output in .private/eval/mt-text/.
 *
 *   npx tsx tools/eval/src/mt-text.ts --models local/hy-mt2:1.8b-q6,anthropic/claude-haiku-5.5 [--set set1] [--n 120] [--no-context]
 */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { chrfScore, chrfStats, type ChrfStats } from "@lt/core";
import { listPages, PRIVATE_DIR, streamChat } from "@lt/server";

const args = process.argv.slice(2);
const flag = (n: string, d: string) => (args.includes(`--${n}`) ? args[args.indexOf(`--${n}`) + 1] : d);
const models = flag("models", "local/hy-mt2:1.8b-q6").split(",");
const set = flag("set", "set1");
const n = Number(flag("n", "120"));
// --no-context: the line alone (Hy-MT2 sometimes translates the background lines instead of the source).
const noContext = args.includes("--no-context");

interface Item { page: string; ja: string; gold: string; before: string[] }
const items: Item[] = [];
const pages = (await listPages()).filter((p) => p.set === set);
// Spread the sample over the pages: every k-th labelled bubble, in reading order.
const all: Item[] = [];
for (const p of pages) {
  const bubbles = [...p.gt].sort((a, b) => a.reading_order - b.reading_order).filter((g) => g.ja_ocr_truth.trim() && g.vi_gold_trans.trim());
  bubbles.forEach((g, i) => all.push({ page: p.id, ja: g.ja_ocr_truth.trim(), gold: g.vi_gold_trans.trim(), before: noContext ? [] : bubbles.slice(Math.max(0, i - 2), i).map((x) => x.ja_ocr_truth.trim()) }));
}
const step = Math.max(1, Math.floor(all.length / n));
for (let i = 0; i < all.length && items.length < n; i += step) items.push(all[i]);
console.log(`${items.length} bubbles from ${pages.length} pages of set ${set}`);

const HYMT = /hy-mt/i;
const SYSTEM = "You translate Japanese manga dialogue into natural Vietnamese. Keep Japanese honorifics and vocatives (-san, -kun, -chan, senpai, nee-chan...) as they are, keep the delivery (… ! ? stutters). Output only the Vietnamese translation of the last line.";
function request(model: string, it: Item): { system: string; text: string } {
  if (HYMT.test(model)) {
    // Hy-MT2's documented prompt, with the previous bubbles as background.
    const bg = it.before.length ? `${it.before.join("\n")}\n` : "";
    return bg
      ? { system: "", text: `${bg}\nPlease translate the following text into Vietnamese, taking the provided background information into consideration.\n[Source Text]\n${it.ja}` }
      : { system: "", text: `Translate the following text into Vietnamese. Note that you should only output the translated result without any additional explanation:\n${it.ja}` };
  }
  const ctx = it.before.length ? `Previous lines (context only):\n${it.before.join("\n")}\n\n` : "";
  return { system: SYSTEM, text: `${ctx}Line to translate:\n${it.ja}` };
}

const out = join(PRIVATE_DIR, "eval", "mt-text");
await mkdir(out, { recursive: true });
const rows: string[] = [];
for (const model of models) {
  const stats: ChrfStats[] = [];
  const ms: number[] = [];
  const lines: Array<{ ja: string; gold: string; hyp: string }> = [];
  let cost = 0, failed = 0;
  for (const it of items) {
    const { system, text } = request(model, it);
    let hyp = "";
    const t0 = performance.now();
    try {
      const st = await streamChat({ model, system, parts: [{ type: "text", text }], purpose: "eval-mt-text", maxTokens: 300, onText: (d) => (hyp += d) });
      cost += st.costUsd;
    } catch (e) {
      failed++;
      console.error(model, (e as Error).message.slice(0, 160));
    }
    ms.push(performance.now() - t0);
    hyp = hyp.replace(/<think>[\s\S]*?<\/think>/g, "").trim().split("\n").filter(Boolean).pop() ?? "";
    lines.push({ ja: it.ja, gold: it.gold, hyp });
    stats.push(chrfStats(hyp, it.gold));
  }
  const sorted = [...ms].sort((a, b) => a - b);
  rows.push(`| ${model} | ${items.length - failed}/${items.length} | ${chrfScore(stats).toFixed(1)} | ${Math.round(sorted[Math.floor(sorted.length / 2)])} ms | ${Math.round(sorted[Math.floor(sorted.length * 0.9)])} ms | $${cost.toFixed(4)} |`);
  await writeFile(join(out, `${model.replace(/[^\w.-]/g, "_")}${noContext ? "-nocontext" : ""}.json`), JSON.stringify(lines, null, 1), "utf8");
  console.log(rows[rows.length - 1]);
}
console.log("\n| Model | Bubbles | chrF vs gold VI | Time per bubble p50 | p90 | Cost |\n|---|---|---|---|---|---|");
for (const r of rows) console.log(r);
