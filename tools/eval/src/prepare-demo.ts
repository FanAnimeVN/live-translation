/**
 * Prepare the local demo: reset each series' story memory in a namespace, then translate
 * every page in reading order through the running server (same path as the demo UI:
 * memory, background summaries, inpainting during translation). Pages then open from the
 * saved text instantly. Needs `npm run server`; costs one page call per page.
 *
 *   npx tsx tools/eval/src/prepare-demo.ts [--ns demo] [--model google/gemini-3.1-flash-lite] [--series uchi-no-nyan-s-diary,...]
 *   npx tsx tools/eval/src/prepare-demo.ts --warm   (after starting the server: rebuild backgrounds into its memory, no API cost)
 */
import { predictInpaint } from "@lt/render";
import type { PageResult } from "@lt/core";
import { decodeImage, listPages, readPageImage } from "@lt/server";

const arg = (name: string, def: string) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : def;
};
const ns = arg("ns", "demo");
const model = arg("model", "google/gemini-3.1-flash-lite");
const only = arg("series", "").split(",").filter(Boolean);
const base = arg("server", "http://127.0.0.1:8787");

const pages = (await listPages()).filter((p) => !only.length || only.includes(p.seriesId));

if (process.argv.includes("--warm")) {
  // Backgrounds live only in the server's memory: rebuild them once so every page opens complete.
  let n = 0;
  const t0 = performance.now();
  for (const page of pages) {
    const { result } = (await (await fetch(`${base}/api/result?pageId=${encodeURIComponent(page.id)}&model=${encodeURIComponent(model)}&ns=${ns}`)).json()) as { result: PageResult | null };
    if (!result) continue;
    const d = await decodeImage(await readPageImage(page));
    const ids = predictInpaint(d.ctx.getImageData(0, 0, d.w, d.h), result.regions);
    if (!ids.length) continue;
    const res = (await (await fetch(`${base}/api/inpaint`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pageId: page.id, model, ns, ids }) })).json()) as { patches: unknown[]; ms: number };
    n += res.patches.length;
    console.log(`${page.id.padEnd(9)} ${res.patches.length} backgrounds in ${res.ms} ms`);
  }
  console.log(`warm: ${n} backgrounds ready in ${Math.round((performance.now() - t0) / 1000)} s`);
  process.exit(0);
}
const series = [...new Map(pages.map((p) => [p.seriesId, p.title])).entries()];
for (const [seriesId, title] of series) {
  await fetch(`${base}/api/memory/reset`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ns, seriesId, title }) });
  console.log(`memory reset: ${seriesId}`);
}

let total = 0;
for (const page of pages) {
  const t0 = performance.now();
  const res = await fetch(`${base}/api/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pageId: page.id, model, ns, inpaint: true }),
  });
  if (!res.ok || !res.body) throw new Error(`${page.id}: ${res.status}`);
  const text = await res.text();
  const events = text.split("\n").filter(Boolean).map((l) => JSON.parse(l) as { type: string; [k: string]: any });
  const done = events.find((e) => e.type === "done");
  const err = events.find((e) => e.type === "error");
  const patches = events.filter((e) => e.type === "patches").reduce((n, e) => n + e.patches.length, 0);
  if (err) console.log(`${page.id.padEnd(9)} ERROR ${err.message}`);
  else {
    const r = done!.result;
    total += r.usage.costUsd ?? 0;
    console.log(
      `${page.id.padEnd(9)} ${Object.keys(r.translations).length}/${r.regions.length} regions, first ${r.timings.firstRegionMs} ms, page ${r.timings.totalMs} ms, ` +
        `${patches} backgrounds rebuilt during translation, stream ${Math.round(performance.now() - t0)} ms, $${(r.usage.costUsd ?? 0).toFixed(5)}`,
    );
  }
}
console.log(`total $${total.toFixed(4)} — open ${base} and pick a page: it loads from the saved translation.`);
