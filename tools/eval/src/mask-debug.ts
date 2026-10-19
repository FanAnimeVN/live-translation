/**
 * Hole masks of the production inpainting path, for eyeballing what gets redrawn: per
 * free-text region, the source crop | the hole in red over the source | the MI-GAN
 * composite. Uses saved translations for the size guess. Private output in
 * .private/eval/mask-debug/; no network.
 *
 *   npx tsx tools/eval/src/mask-debug.ts <evalRun> <model> <pageId> [regionId...] [--engine migan|lama] [--device cpu|dml|webgpu]
 */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { createCanvas } from "@napi-rs/canvas";
import { area, artTextMask, textArea, type PageResult, type RGBAImage } from "@lt/core";
import { cornersFlat } from "@lt/render";
import { charSizesFor, decodeImage, getPage, loadInpainter, loadLama, PRIVATE_DIR, readPageImage, refineTextBoxes, runLama, runMigan, type InpaintDevice } from "@lt/server";

const args = process.argv.slice(2);
const flag = (n: string, d: string) => (args.includes(`--${n}`) ? args[args.indexOf(`--${n}`) + 1] : d);
const engine = flag("engine", "migan");
const device = flag("device", "cpu") as InpaintDevice;
const [run, model, pageId, ...ids] = args.filter((a, i) => !a.startsWith("--") && !args[i - 1]?.startsWith("--"));
const safe = (s: string) => s.replace(/[^a-zA-Z0-9._-]/g, "_");
const result = JSON.parse(await readFile(join(PRIVATE_DIR, "eval", run, safe(model), `${safe(pageId)}.json`), "utf8")) as PageResult;
const d = await decodeImage(await readPageImage(await getPage(pageId)));
const full = d.ctx.getImageData(0, 0, d.w, d.h) as unknown as RGBAImage;
const sizes = charSizesFor(result);
const session = engine.startsWith("lama") ? await loadLama(engine as "lama" | "lama-cv", device) : await loadInpainter(device);
const out = join(PRIVATE_DIR, "eval", "mask-debug");
await mkdir(out, { recursive: true });

for (const r of result.regions) {
  if (ids.length ? !ids.includes(r.id) : !!r.bubble) continue;
  const members = r.bubble ? textArea(r, cornersFlat(full, r.bubble)) : await refineTextBoxes(d, r);
  const cs = sizes[r.id] && Math.sqrt((sizes[r.id] ** 2 * members.reduce((a, m) => a + area(m), 0)) / area(r.box));
  const job = artTextMask(full, members, { charSize: cs });
  const res = engine.startsWith("lama") ? await runLama(session, full, job) : await runMigan(session, full, job);
  const { x, y, w, h } = job.crop;
  const n = w * h;
  const cv = createCanvas(w * 3 + 8, h);
  const ctx = cv.getContext("2d");
  ctx.fillStyle = "#f00";
  ctx.fillRect(0, 0, cv.width, h);
  for (let k = 0; k < 3; k++) {
    const id = ctx.createImageData(w, h);
    for (let p = 0; p < n; p++) {
      const i = ((y + Math.floor(p / w)) * full.width + x + (p % w)) * 4;
      const hole = job.hole[p] === 1;
      const src = [full.data[i], full.data[i + 1], full.data[i + 2]];
      const px = k === 0 ? src : k === 1 ? (hole ? [255, Math.round(src[1] * 0.35), Math.round(src[2] * 0.35)] : src) : hole ? [res[p], res[n + p], res[2 * n + p]] : src;
      id.data.set([...px, 255], p * 4);
    }
    ctx.putImageData(id, k * (w + 4), 0);
  }
  const file = join(out, `${safe(pageId)}-${r.id}-${engine}.png`);
  await writeFile(file, await cv.encode("png"));
  console.log(`${r.id} members=${members.length} charSize=${cs?.toFixed(1)} coverage=${job.coverage.toFixed(3)} rect=${job.rect} bold=${job.bold} -> ${file}`);
}
