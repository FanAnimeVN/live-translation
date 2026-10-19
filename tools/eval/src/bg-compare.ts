/**
 * Compare background (summary) models on the SAME input: rebuild each series' memory from the
 * page results of a context run without any background update, so every model sees identical
 * pending dialogue. Reports cost, time and what the memory keeps after evidence checks.
 *
 *   npx tsx tools/eval/src/bg-compare.ts --run ctx-v2b [--model anthropic/claude-haiku-5.5]
 *        [--bg deepseek/deepseek-v4.1-flash,z-ai/glm-5.3-flash,anthropic/claude-haiku-5.5]
 */
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { emptyMemory, mergePage, type PageResult, type SeriesMemory } from "@lt/core";
import { applyPlanned, listPages, planMemoryUpdate, PRIVATE_DIR } from "@lt/server";

const arg = (name: string, def: string) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : def;
};
const run = arg("run", "ctx-v2b");
const model = arg("model", "anthropic/claude-haiku-5.5");
const bgs = arg("bg", "deepseek/deepseek-v4.1-flash,z-ai/glm-5.3-flash,anthropic/claude-haiku-5.5,google/gemini-3.1-flash-lite").split(",").filter(Boolean);
const safe = (s: string) => s.replace(/[^a-zA-Z0-9._-]/g, "_");
const dir = join(PRIVATE_DIR, "eval", run);

const memories = new Map<string, SeriesMemory>();
for (const page of await listPages()) {
  let result: PageResult;
  try {
    result = JSON.parse(await readFile(join(dir, safe(model), `${safe(page.id)}.json`), "utf8")) as PageResult;
  } catch {
    continue;
  }
  const mem = memories.get(page.seriesId) ?? emptyMemory(page.seriesId, page.title);
  memories.set(page.seriesId, mergePage(mem, page.id, page.position, result.notes, Object.values(result.translations)).memory);
}

const out: Array<Record<string, unknown>> = [];
for (const [series, mem] of memories) {
  console.log(`\n== ${series}: ${mem.pending?.length ?? 0} pending lines, ${mem.entities.length} entities, ${mem.address.length} address rules before update`);
  for (const bg of bgs) {
    try {
      const plan = await planMemoryUpdate(mem, true, bg);
      if (!plan) continue;
      const after = applyPlanned(mem, plan);
      const u = plan.update;
      const row = {
        series,
        model: bg,
        ms: plan.ms,
        costUsd: plan.costUsd,
        parsed: !!u,
        storyWords: u?.story_so_far?.split(/\s+/).filter(Boolean).length ?? 0,
        events: u?.events?.length ?? 0,
        proposedAddress: u?.address?.length ?? 0,
        keptAddress: after.address.filter((a) => a.source === "summary").length,
        characters: u?.characters?.length ?? 0,
        update: u,
      };
      out.push(row);
      console.log(
        `${bg.padEnd(32)} ${String(plan.ms).padStart(6)} ms $${plan.costUsd.toFixed(5)} parsed=${row.parsed} story ${row.storyWords} words, ` +
          `${row.events} events, ${row.characters} characters, address ${row.keptAddress}/${row.proposedAddress} kept after evidence check`,
      );
    } catch (e) {
      out.push({ series, model: bg, error: (e as Error).message });
      console.log(`${bg.padEnd(32)} ERROR ${(e as Error).message.slice(0, 200)}`);
    }
  }
}
await writeFile(join(dir, "bg-compare.json"), JSON.stringify(out, null, 1), "utf8");
console.log(`\nWritten ${join(dir, "bg-compare.json")}`);
