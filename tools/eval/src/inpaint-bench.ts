/**
 * MI-GAN vs LaMa on the GT pages, with an answer key: a real text-shaped hole (the glyph
 * mask of an actual free-text region) is cut into nearby artwork that holds no text, each
 * engine fills it, and the fill is compared with the original pixels — mean absolute error,
 * PSNR, and whether texture survives (a flat grey patch inside hatching is the failure
 * readers notice). Also times each engine and writes a visual sheet on real text regions.
 * Private output in .private/eval/inpaint-bench/; no network.
 *
 *   npx tsx tools/eval/src/inpaint-bench.ts [--set local,set1] [--cases 40] [--engines migan,lama,lama-cv] [--device cpu|dml|webgpu]
 *
 * Textured holes (hatching, screentone) are reported apart from plain ones: that is where
 * the engines differ. "Bias" is the fill's mean luminance minus the original's (a light
 * fill in dark hatching shows as ghost strokes); "texture" is the fill's luminance spread
 * over the original's (1 = same busyness, near 0 = flat patch).
 */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { createCanvas, type Canvas } from "@napi-rs/canvas";
import { artTextMask, intersect, type Box, type InpaintJob, type RGBAImage } from "@lt/core";
import { decodeImage, detect, listPages, loadInpainter, loadLama, PRIVATE_DIR, readPageImage, runLama, runMigan, type InpaintDevice, type LamaVariant } from "@lt/server";

const args = process.argv.slice(2);
const flag = (n: string, d: string) => (args.includes(`--${n}`) ? args[args.indexOf(`--${n}`) + 1] : d);
const sets = flag("set", "").split(",").filter(Boolean);
const maxCases = Number(flag("cases", "40"));
const engines = flag("engines", "migan,lama,lama-cv").split(",") as Array<"migan" | LamaVariant>;
const device = flag("device", "cpu") as InpaintDevice;
const out = join(PRIVATE_DIR, "eval", "inpaint-bench");
await mkdir(out, { recursive: true });

let seed = 20261019;
const rand = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32);
const lum = (d: Uint8ClampedArray | Uint8Array, i: number) => 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];

interface Case { page: string; full: RGBAImage; job: InpaintJob; real: boolean }
const cases: Case[] = [];
const sheetCases: Case[] = [];
for (const page of (await listPages()).filter((p) => !sets.length || sets.includes(p.set))) {
  if (cases.length >= maxCases) break;
  const d = await decodeImage(await readPageImage(page));
  const full = d.ctx.getImageData(0, 0, d.w, d.h) as unknown as RGBAImage;
  const det = await detect(d);
  const taken: Box[] = [...det.regions.map((r) => r.bubble ?? r.box), ...page.gt.map((g) => g.bbox)];
  for (const r of det.regions.filter((x) => !x.bubble).slice(0, 2)) {
    const tpl = artTextMask(full, r.members);
    if (tpl.rect || tpl.coverage < 0.03) continue;
    if (sheetCases.length < 10) sheetCases.push({ page: page.id, full, job: tpl, real: true });
    const { w, h } = tpl.crop;
    // Find art with no text nearby where the same hole can be cut: textured, not blank paper.
    for (let attempt = 0; attempt < 60; attempt++) {
      const x = Math.floor(rand() * (d.w - w));
      const y = Math.floor(rand() * (d.h - h));
      const box = { x, y, w, h };
      if (taken.some((t) => intersect({ x: t.x - 12, y: t.y - 12, w: t.w + 24, h: t.h + 24 }, box))) continue;
      let s = 0, q = 0;
      for (let yy = 0; yy < h; yy += 2) for (let xx = 0; xx < w; xx += 2) { const v = lum(full.data, ((y + yy) * d.w + x + xx) * 4); s += v; q += v * v; }
      const n = Math.ceil(h / 2) * Math.ceil(w / 2);
      const mean = s / n;
      const std = Math.sqrt(Math.max(0, q / n - mean * mean));
      if (std < 22 || mean > 228) continue;
      cases.push({ page: page.id, full, job: { ...tpl, crop: box }, real: false });
      break;
    }
  }
}
console.log(`${cases.length} synthetic cases with an answer key, ${sheetCases.length} real text regions for the sheet`);

const sheet: Record<string, Canvas[]> = {};
const table: string[] = [];
for (const engine of engines) {
  const t0 = performance.now();
  const session = engine === "migan" ? await loadInpainter(device) : await loadLama(engine, device);
  const loadMs = Math.round(performance.now() - t0);
  const run = (c: Case) => (engine === "migan" ? runMigan(session, c.full, c.job) : runLama(session, c.full, c.job));
  await run(cases[0]); // warm-up: the first GPU run compiles kernels
  let mae = 0, holes = 0, flat = 0, textured = 0;
  const psnr: number[] = [];
  const ms: number[] = [];
  const tex = { mae: [] as number[], bias: [] as number[], ratio: [] as number[] };
  const plain = { mae: [] as number[], bias: [] as number[] };
  for (const c of cases) {
    const t = performance.now();
    const res = await run(c);
    ms.push(performance.now() - t);
    const { x, y, w, h } = c.job.crop;
    const n = w * h;
    let se = 0, ae = 0, k = 0, gs = 0, gq = 0, rs = 0, rq = 0;
    for (let p = 0; p < n; p++) {
      if (!c.job.hole[p]) continue;
      const i = ((y + Math.floor(p / w)) * c.full.width + x + (p % w)) * 4;
      for (let ch = 0; ch < 3; ch++) {
        const diff = res[ch * n + p] - c.full.data[i + ch];
        se += diff * diff;
        ae += Math.abs(diff);
      }
      const gl = lum(c.full.data, i);
      const rl = 0.299 * res[p] + 0.587 * res[n + p] + 0.114 * res[2 * n + p];
      gs += gl; gq += gl * gl; rs += rl; rq += rl * rl;
      k++;
    }
    if (!k) continue;
    holes++;
    mae += ae / (3 * k);
    psnr.push(10 * Math.log10((255 * 255) / Math.max(1e-6, se / (3 * k))));
    const gstd = Math.sqrt(Math.max(0, gq / k - (gs / k) ** 2));
    const rstd = Math.sqrt(Math.max(0, rq / k - (rs / k) ** 2));
    const caseMae = ae / (3 * k);
    const bias = (rs - gs) / k;
    if (gstd > 20) {
      textured++;
      if (rstd < 0.5 * gstd) flat++;
      tex.mae.push(caseMae);
      tex.bias.push(bias);
      tex.ratio.push(rstd / gstd);
    } else {
      plain.mae.push(caseMae);
      plain.bias.push(bias);
    }
  }
  // Visual sheet on real text: original | engine fill (hole only).
  sheet[engine] = [];
  for (const c of sheetCases) {
    const res = await run(c);
    const { x, y, w, h } = c.job.crop;
    const cv = createCanvas(w, h);
    const ctx = cv.getContext("2d");
    const img = ctx.createImageData(w, h);
    for (let p = 0; p < w * h; p++) {
      const i = ((y + Math.floor(p / w)) * c.full.width + x + (p % w)) * 4;
      const hole = c.job.hole[p] === 1;
      img.data[p * 4] = hole ? res[p] : c.full.data[i];
      img.data[p * 4 + 1] = hole ? res[w * h + p] : c.full.data[i + 1];
      img.data[p * 4 + 2] = hole ? res[2 * w * h + p] : c.full.data[i + 2];
      img.data[p * 4 + 3] = 255;
    }
    ctx.putImageData(img, 0, 0);
    sheet[engine].push(cv);
  }
  const sorted = [...ms].sort((a, b) => a - b);
  const med = (v: number[]) => [...v].sort((a, b) => a - b)[Math.floor(v.length / 2)] ?? NaN;
  const mean = (v: number[]) => (v.length ? v.reduce((a, b) => a + b, 0) / v.length : NaN);
  table.push(
    `| ${engine} (${device}) | ${holes} | ${(mae / holes).toFixed(1)} | ${med(psnr).toFixed(1)} dB | ${mean(tex.mae).toFixed(1)} / ${mean(plain.mae).toFixed(1)} | ` +
      `${mean(tex.bias).toFixed(1)} / ${mean(plain.bias).toFixed(1)} | ${med(tex.ratio).toFixed(2)} | ${flat}/${textured} | ${Math.round(sorted[Math.floor(sorted.length / 2)])} ms | ${Math.round(sorted[Math.floor(sorted.length * 0.9)])} ms | ${loadMs} ms |`,
  );
  if ("release" in session) await (session as { release: () => Promise<void> }).release().catch(() => {});
}

console.log(
  "\n| Engine | Holes | MAE (0-255, lower better) | PSNR median | MAE textured / plain | Bias textured / plain | Texture kept (median, 1 = same) | Flat patches | Time median | Time p90 | First load |",
);
console.log("|---|---|---|---|---|---|---|---|---|---|---|");
for (const row of table) console.log(row);

// Sheet: one row per real text region — original | each engine.
const cols = ["original", ...engines];
const cw = 220;
const rowsH = sheetCases.map((c) => Math.round((c.job.crop.h * cw) / c.job.crop.w));
const S = createCanvas(cw * cols.length, rowsH.reduce((a, b) => a + b + 18, 18));
const sx = S.getContext("2d");
sx.fillStyle = "#fff";
sx.fillRect(0, 0, S.width, S.height);
sx.fillStyle = "#c00";
sx.font = "13px sans-serif";
cols.forEach((c, i) => sx.fillText(c, i * cw + 6, 13));
let yy = 18;
sheetCases.forEach((c, r) => {
  const { x, y, w, h } = c.job.crop;
  const o = createCanvas(w, h);
  const oc = o.getContext("2d");
  const id = oc.createImageData(w, h);
  for (let p = 0; p < w * h; p++) {
    const i = ((y + Math.floor(p / w)) * c.full.width + x + (p % w)) * 4;
    id.data[p * 4] = c.full.data[i];
    id.data[p * 4 + 1] = c.full.data[i + 1];
    id.data[p * 4 + 2] = c.full.data[i + 2];
    id.data[p * 4 + 3] = 255;
  }
  oc.putImageData(id, 0, 0);
  sx.drawImage(o, 0, yy, cw, rowsH[r]);
  engines.forEach((e, i) => sx.drawImage(sheet[e][r], (i + 1) * cw, yy, cw, rowsH[r]));
  yy += rowsH[r] + 18;
});
await writeFile(join(out, "sheet.png"), await S.encode("png"));
console.log(`sheet: ${join(out, "sheet.png")}`);
