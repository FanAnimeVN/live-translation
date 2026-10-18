/**
 * Render saved page results to PNG for visual QA (private, gitignored .private/renders).
 * Usage: npx tsx tools/eval/src/render.ts <model> [pageId...] [--debug]
 */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import type { PageResult } from "@lt/core";
import type { Rejected } from "../../../apps/server/src/inpaint";
import { join } from "node:path";
import { createCanvas, GlobalFonts, loadImage } from "@napi-rs/canvas";
import { LETTERING_FONT, renderTranslation, type Ctx2D, type PatchImage } from "@lt/render";
import { charSizesFor, decodeImage, getPage, inpaintRegions, listPages, loadResult, PRIVATE_DIR, readPageImage, ROOT } from "@lt/server";

GlobalFonts.registerFromPath(join(ROOT, "apps", "demo", "public", "fonts", "PatrickHand-Regular.ttf"), LETTERING_FONT);

const args = process.argv.slice(2);
const debug = args.includes("--debug");
const inpaint = !args.includes("--no-inpaint");
const positional = args.filter((a, i) => !a.startsWith("--") && args[i - 1] !== "--eval");
const [model, ...ids] = positional;
const ns = process.env.NS ?? "demo";
const evalRun = args.includes("--eval") ? args[args.indexOf("--eval") + 1] : undefined;
const safe = (s: string) => s.replace(/[^a-zA-Z0-9._-]/g, "_");
async function load(pageId: string): Promise<PageResult | null> {
  if (!evalRun) return loadResult(ns, model, pageId);
  try {
    return JSON.parse(await readFile(join(PRIVATE_DIR, "eval", evalRun, safe(model), `${safe(pageId)}.json`), "utf8")) as PageResult;
  } catch {
    return null;
  }
}
const pages = ids.length ? await Promise.all(ids.map(getPage)) : await listPages();
const out = join(PRIVATE_DIR, "renders", evalRun ?? ns, model.replace(/[^a-zA-Z0-9._-]/g, "_"));
await mkdir(out, { recursive: true });

for (const page of pages) {
  const result = await load(page.id);
  if (!result) continue;
  const d = await decodeImage(await readPageImage(page));
  const canvas = createCanvas(d.w * 2, d.h);
  const ctx = canvas.getContext("2d");
  ctx.drawImage(d.canvas, 0, 0);
  ctx.drawImage(d.canvas, d.w, 0);
  // Render the translation on the right half only.
  const right = createCanvas(d.w, d.h);
  const rctx = right.getContext("2d");
  rctx.drawImage(d.canvas, 0, 0);
  let renders = renderTranslation(rctx as unknown as Ctx2D, { w: d.w, h: d.h }, result.regions, result.translations);
  const need = renders.filter((r) => r.needsInpaint).map((r) => r.id);
  let inpaintMs = 0;
  if (inpaint && need.length) {
    const t0 = performance.now();
    const rejected: Rejected[] = [];
    const patches = await inpaintRegions(d, result.regions.filter((r) => need.includes(r.id)), charSizesFor(result), rejected);
    if (rejected.length) console.log(page.id, "inpaint rejected:", rejected.map((r) => `${r.id}:${r.reason}(${r.coverage.toFixed(2)})`).join(" "));
    inpaintMs = Math.round(performance.now() - t0);
    const images: Record<string, PatchImage> = {};
    for (const p of patches) images[p.id] = { x: p.x, y: p.y, image: await loadImage(Buffer.from(p.dataUrl.split(",")[1], "base64")) };
    rctx.drawImage(d.canvas, 0, 0);
    renders = renderTranslation(rctx as unknown as Ctx2D, { w: d.w, h: d.h }, result.regions, result.translations, { patches: images });
  }
  if (debug) {
    for (const r of result.regions) {
      const st = renders.find((x) => x.id === r.id)?.status ?? "none";
      rctx.strokeStyle = st === "lettered" ? "#16a34a" : st === "kept-original" ? "#dc2626" : "#7c3aed";
      rctx.lineWidth = 2;
      rctx.strokeRect(r.box.x, r.box.y, r.box.w, r.box.h);
      if (r.bubble) {
        rctx.strokeStyle = "#2563eb88";
        rctx.strokeRect(r.bubble.x, r.bubble.y, r.bubble.w, r.bubble.h);
      }
      rctx.fillStyle = "#000";
      rctx.font = "bold 14px sans-serif";
      const e = renders.find((x) => x.id === r.id)?.erase;
      rctx.fillText(`${r.id}${e ? ` f=${e.flatness.toFixed(2)}` : ""}`, r.box.x, r.box.y - 3);
    }
  }
  ctx.drawImage(right, d.w, 0);
  await writeFile(join(out, `${page.id}.png`), await canvas.encode("png"));
  const summary = renders
    .map((r) => {
      const reg = result.regions.find((x) => x.id === r.id)!;
      const t = result.translations[r.id];
      const cs = Math.sqrt((reg.box.w * reg.box.h) / Math.max(1, [...(t?.ja ?? "").replace(/\s/g, "")].length || 4));
      return `${r.id}${reg.bubble ? "B" : "F"}:${r.status}${r.erase ? `(f=${r.erase.flatness.toFixed(2)} i=${r.erase.inkShare.toFixed(2)} m=${r.erase.midShare.toFixed(2)} ${r.erase.mode})` : ""} h=${Math.round(reg.box.h)} cs~${Math.round(cs)}${r.layout?.overflow ? " !overflow" : ""}`;
    })
    .join("\n   ");
  console.log(page.id, need.length ? `(inpainted ${need.length} in ${inpaintMs} ms)` : "", summary);
}
console.log("written to", out);
