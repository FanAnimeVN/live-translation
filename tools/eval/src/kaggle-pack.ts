/**
 * Package the exact page requests the product sends to a reading model (system prompt + page
 * image with numbered regions + crops, empty story memory), so local models can be replayed on a
 * remote GPU (Kaggle) and scored back here with the product's own parser (kaggle-score.ts).
 *
 * Besides the page requests, each page carries plain crops for dedicated OCR models: one per
 * detected region (the real two-stage pipeline) and one per label box (OCR alone, no detector).
 * `mt-source.json` holds the labelled Japanese lines, so translation models can be compared on
 * perfect OCR. The Vietnamese gold is NOT packed: scoring happens on this machine.
 * Output: .private/kaggle/<name>/ (pages/*.json, index.json, mt-source.json).
 *
 *   npx tsx tools/eval/src/kaggle-pack.ts [--set local,set1] [--per-set 10]
 *   npx tsx tools/eval/src/kaggle-pack.ts --pages @.cache/tmp/team25-pages.txt --name team25
 *   npx tsx tools/eval/src/kaggle-pack.ts --per-set 1000 --test @.cache/tmp/team25-pages.txt --name gt60
 */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { createCanvas } from "@napi-rs/canvas";
import { buildUserParts, emptyMemory, PROMPT_VERSION, stableContext, SYSTEM_PROMPT, volatileContext, type Box } from "@lt/core";
import { decodeImage, detect, listPages, markedPageDataUrl, PRIVATE_DIR, readPageImage, regionCrops } from "@lt/server";

type DecodedPage = Awaited<ReturnType<typeof decodeImage>>;
import { validGt } from "./gt";

const args = process.argv.slice(2);
const flag = (n: string, d: string) => (args.includes(`--${n}`) ? args[args.indexOf(`--${n}`) + 1] : d);
const sets = flag("set", "local,set1").split(",");
const perSet = Number(flag("per-set", "10"));
const pagesArg = flag("pages", "");
const testArg = flag("test", "");
// Pages scored in the remote run (the expensive stages only touch these); the rest are "dev" for OCR and later training.
const testIds = new Set(testArg ? (testArg.startsWith("@") ? await readFile(testArg.slice(1), "utf8") : testArg).split(/[,\s]+/).filter(Boolean) : []);
const wanted = pagesArg ? (pagesArg.startsWith("@") ? await readFile(pagesArg.slice(1), "utf8") : pagesArg).split(/[,\s]+/).filter(Boolean) : undefined;
const out = join(PRIVATE_DIR, "kaggle", flag("name", "pack"));
await mkdir(join(out, "pages"), { recursive: true });

/** A plain crop for OCR models: the box plus a small margin, at the page's own resolution. */
async function boxCrop(page: DecodedPage, b: Box, m = 4): Promise<string> {
  const x = Math.max(0, Math.floor(b.x - m)), y = Math.max(0, Math.floor(b.y - m));
  const w = Math.max(1, Math.min(page.w - x, Math.ceil(b.w + 2 * m))), h = Math.max(1, Math.min(page.h - y, Math.ceil(b.h + 2 * m)));
  const canvas = createCanvas(w, h);
  canvas.getContext("2d").drawImage(page.canvas, x, y, w, h, 0, 0, w, h);
  return `data:image/png;base64,${(await canvas.encode("png")).toString("base64")}`;
}

const all = await listPages();
const chosen = wanted
  ? wanted.map((id) => {
      const p = all.find((x) => x.id === id);
      if (!p) throw new Error(`unknown page ${id}`);
      return p;
    })
  : sets.flatMap((set) => {
      const pages = all.filter((p) => p.set === set && p.gt.length);
      // Spread over the set: every k-th page, so several titles are covered.
      const step = Math.max(1, Math.floor(pages.length / perSet));
      return pages.filter((_, i) => i % step === 0).slice(0, perSet);
    });

const index: Array<{ pageId: string; set: string; split: string; regions: string[]; gt: number; kb: number }> = [];
const mtSource: Array<{ pageId: string; i: number; order: number; ja: string }> = [];
for (const page of chosen) {
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
  const gt = validGt(page.gt, d);
  const ocr = await Promise.all(det.regions.map(async (r) => ({ id: r.id, dataUrl: await boxCrop(d, r.box) })));
  const gtCrops = await Promise.all(gt.map(async (g) => ({ i: page.gt.indexOf(g), dataUrl: await boxCrop(d, g.bbox) })));
  for (const g of gt) if (g.ja_ocr_truth.trim()) mtSource.push({ pageId: page.id, i: page.gt.indexOf(g), order: g.reading_order, ja: g.ja_ocr_truth });
  const body = JSON.stringify({ pageId: page.id, set: page.set, promptVersion: PROMPT_VERSION, regions: det.regions, messages, ocr, gtCrops });
  await writeFile(join(out, "pages", `${page.id.replace(/[^\w.-]/g, "_")}.json`), body, "utf8");
  index.push({ pageId: page.id, set: page.set, split: !testIds.size || testIds.has(page.id) ? "test" : "dev", regions: det.regions.map((r) => r.id), gt: gt.length, kb: Math.round(body.length / 1024) });
  console.log(`${page.set} ${page.id}: ${det.regions.length} regions, ${gt.length} labels, ${Math.round(body.length / 1024)} KB`);
}
await writeFile(join(out, "mt-source.json"), JSON.stringify(mtSource), "utf8");
await writeFile(join(out, "index.json"), JSON.stringify({ promptVersion: PROMPT_VERSION, createdAt: new Date().toISOString(), detectCtd: process.env.DETECT_CTD ?? "default", pages: index }, null, 1), "utf8");
console.log(`${index.length} pages, ${mtSource.length} labelled lines, ${Math.round(index.reduce((a, p) => a + p.kb, 0) / 1024)} MB in ${out}`);
