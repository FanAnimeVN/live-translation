/**
 * Package the exact page requests the product sends to a reading model (system prompt + page
 * image with numbered regions + crops, empty story memory), so local models can be replayed on a
 * remote GPU (Kaggle) and scored back here with the product's own parser (kaggle-score.ts).
 * Ground truth is NOT packed: scoring happens on this machine. Output: .private/kaggle/pack/.
 *
 *   npx tsx tools/eval/src/kaggle-pack.ts [--set local,set1] [--per-set 10]
 */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { buildUserParts, emptyMemory, PROMPT_VERSION, stableContext, SYSTEM_PROMPT, volatileContext } from "@lt/core";
import { decodeImage, detect, listPages, markedPageDataUrl, PRIVATE_DIR, readPageImage, regionCrops } from "@lt/server";

const args = process.argv.slice(2);
const flag = (n: string, d: string) => (args.includes(`--${n}`) ? args[args.indexOf(`--${n}`) + 1] : d);
const sets = flag("set", "local,set1").split(",");
const perSet = Number(flag("per-set", "10"));
const out = join(PRIVATE_DIR, "kaggle", "pack");
await mkdir(join(out, "pages"), { recursive: true });

const all = await listPages();
const index: Array<{ pageId: string; set: string; regions: string[]; kb: number }> = [];
for (const set of sets) {
  const pages = all.filter((p) => p.set === set && p.gt.length);
  // Spread over the set: every k-th page, so several titles are covered.
  const step = Math.max(1, Math.floor(pages.length / perSet));
  for (let i = 0; i < pages.length && index.filter((x) => x.set === set).length < perSet; i += step) {
    const page = pages[i];
    const d = await decodeImage(await readPageImage(page));
    const det = await detect(d);
    if (!det.regions.length) continue;
    const memory = emptyMemory(page.seriesId, page.title);
    const parts = buildUserParts({
      title: page.title,
      position: page.position,
      stableMemory: stableContext(memory, page.position),
      volatileMemory: volatileContext(memory, page.position),
      regions: det.regions,
      image: { w: d.w, h: d.h },
      markedPageDataUrl: await markedPageDataUrl(d, det.regions),
      crops: await regionCrops(d, det.regions, undefined),
    });
    const messages = [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: parts.map((p) => (p.type === "text" ? { type: "text", text: p.text } : { type: "image_url", image_url: { url: p.dataUrl } })) },
    ];
    const body = JSON.stringify({ pageId: page.id, set, promptVersion: PROMPT_VERSION, regions: det.regions, messages });
    await writeFile(join(out, "pages", `${page.id.replace(/[^\w.-]/g, "_")}.json`), body, "utf8");
    index.push({ pageId: page.id, set, regions: det.regions.map((r) => r.id), kb: Math.round(body.length / 1024) });
    console.log(`${set} ${page.id}: ${det.regions.length} regions, ${Math.round(body.length / 1024)} KB`);
  }
}
await writeFile(join(out, "index.json"), JSON.stringify({ promptVersion: PROMPT_VERSION, createdAt: new Date().toISOString(), pages: index }, null, 1), "utf8");
console.log(`${index.length} pages, ${Math.round(index.reduce((a, p) => a + p.kb, 0) / 1024)} MB in ${out}`);
