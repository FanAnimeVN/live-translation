/**
 * Inspect inpainting for selected regions: mask coverage, glyph residue before and
 * after MI-GAN, and whether the whole-box retry fired. Private output only.
 *   npx tsx tools/eval/src/debug/inpaint-probe.ts <run> <model> <pageId> <regionId...>
 */
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { createCanvas } from "@napi-rs/canvas";
import { artTextMask, glyphResidue, type PageResult } from "@lt/core";
import { charSizesFor, decodeImage, getPage, inpaintRegions, PRIVATE_DIR, readPageImage, refineTextBoxes } from "@lt/server";
import type { Rejected } from "../../../../apps/server/src/inpaint";

const [run, model, pageId, ...ids] = process.argv.slice(2);
const res = JSON.parse(await readFile(join(PRIVATE_DIR, "eval", run, model.replace(/[^a-zA-Z0-9._-]/g, "_"), `${pageId}.json`), "utf8")) as PageResult;
const d = await decodeImage(await readPageImage(await getPage(pageId)));
const full = d.ctx.getImageData(0, 0, d.w, d.h);
const sizes = charSizesFor(res);
await mkdir(join(PRIVATE_DIR, "probe"), { recursive: true });
for (const id of ids) {
  const r = res.regions.find((x) => x.id === id)!;
  const members = r.bubble ? r.members : await refineTextBoxes(d, r);
  const boxArea = members.reduce((a, m) => a + m.w * m.h, 0);
  const cs = sizes[id] && Math.sqrt((sizes[id] ** 2 * boxArea) / (r.box.w * r.box.h));
  const job = artTextMask(full, members, { charSize: cs });
  console.log(id, "cs", sizes[id]?.toFixed(1), "->", cs?.toFixed(1), "box", r.box, "refined", members.map((m) => [m.x, m.y, m.w, m.h].map(Math.round)));
  console.log("  mask coverage", job.coverage.toFixed(3), "rect", job.rect, "crop", job.crop, "residue(original)", glyphResidue(full, members, cs).toFixed(3));
  // hole mask image for eyeballing
  const c = createCanvas(job.crop.w * 2, job.crop.h);
  const ctx = c.getContext("2d");
  ctx.drawImage(d.canvas, job.crop.x, job.crop.y, job.crop.w, job.crop.h, 0, 0, job.crop.w, job.crop.h);
  const m = ctx.createImageData(job.crop.w, job.crop.h);
  for (let p = 0; p < job.hole.length; p++) {
    const v = job.hole[p] ? 0 : 255;
    m.data[p * 4] = m.data[p * 4 + 1] = m.data[p * 4 + 2] = v;
    m.data[p * 4 + 3] = 255;
  }
  ctx.putImageData(m, job.crop.w, 0);
  await writeFile(join(PRIVATE_DIR, "probe", `${pageId}-${id}-mask.png`), await c.encode("png"));
  const rejected: Rejected[] = [];
  const t0 = performance.now();
  const patches = await inpaintRegions(d, [r], sizes, rejected);
  console.log("  inpaint", Math.round(performance.now() - t0), "ms", "diagnostics", rejected);
  console.log("  patch", patches[0] && { x: patches[0].x, y: patches[0].y, w: patches[0].w, h: patches[0].h, coverage: patches[0].coverage.toFixed(3) });
}

// Save the last region's patch next to its mask for eyeballing.
{
  const id = ids[ids.length - 1];
  const r = res.regions.find((x) => x.id === id)!;
  const rejected: Rejected[] = [];
  const [p] = await inpaintRegions(d, [r], sizes, rejected);
  if (p) await writeFile(join(PRIVATE_DIR, "probe", `${pageId}-${id}-patch.png`), Buffer.from(p.dataUrl.split(",")[1], "base64"));
}
