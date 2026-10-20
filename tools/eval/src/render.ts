/**
 * Render saved page results to PNG and score the lettering automatically
 * (private, gitignored .private/renders and .private/qa).
 *
 *   npx tsx tools/eval/src/render.ts <model> [pageId...] [--eval <runId>] [--debug] [--no-inpaint]
 *
 * Shaped lettering is listed as id:angle (~ curved, =n printed lines) and id!stacked|across (a shout).
 * --no-balloons keeps saved regions as they are (no balloon search in the pixels).
 *
 * Per page it reports: regions lettered, regions still waiting for inpainting,
 * leftover Japanese under lettering (residue), overflow, lettering overlapping other
 * lettering or unerased text, and lettering leaving its balloon.
 */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { createCanvas, GlobalFonts, loadImage } from "@napi-rs/canvas";
import { expand, intersect, type Box, type PageResult } from "@lt/core";
import { LETTERING_FONT, MAX_RESIDUE, quadsTouch, renderTranslation, type Ctx2D, type PatchImage, type RegionRender } from "@lt/render";
import { adoptPageBalloons, charSizesFor, decodeImage, getPage, INPAINT_DEVICE, INPAINT_ENGINE, inpaintRegions, listPages, loadResult, PRIVATE_DIR, readPageImage, ROOT, warmInpainters } from "@lt/server";
import type { Rejected } from "../../../apps/server/src/inpaint";

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
const out = join(PRIVATE_DIR, "renders", evalRun ?? ns, safe(model));
await mkdir(out, { recursive: true });

interface PageQa {
  pageId: string;
  regions: number;
  lettered: number;
  waitingInpaint: number;
  sfxOrDecorative: number;
  residue: string[];
  overflow: string[];
  overlaps: string[];
  overUnerased: string[];
  outsideBalloon: string[];
  inpaintMs: number;
  rejected: string[];
  /** Lettering laid out like the raw: tilted (degrees), along a curve (~), on printed lines (=n). */
  shaped: string[];
}
const report: PageQa[] = [];
if (inpaint) await warmInpainters();
const engines: Record<string, number> = {};

for (const page of pages) {
  const result = await load(page.id);
  if (!result) continue;
  const d = await decodeImage(await readPageImage(page));
  // Results saved before balloons were looked for in the pixels get them now (as detection does).
  if (!args.includes("--no-balloons")) result.regions = await adoptPageBalloons(d, result.regions);
  const canvas = createCanvas(d.w * 2, d.h);
  const ctx = canvas.getContext("2d");
  ctx.drawImage(d.canvas, 0, 0);
  // Render the translation on the right half only.
  const right = createCanvas(d.w, d.h);
  const rctx = right.getContext("2d");
  rctx.drawImage(d.canvas, 0, 0);
  let renders = renderTranslation(rctx as unknown as Ctx2D, { w: d.w, h: d.h }, result.regions, result.translations);
  const need = renders.filter((r) => r.status === "needs-inpaint").map((r) => r.id);
  let inpaintMs = 0;
  const rejected: Rejected[] = [];
  if (inpaint && need.length) {
    const t0 = performance.now();
    const patches = await inpaintRegions(d, result.regions.filter((r) => need.includes(r.id)), charSizesFor(result), rejected, result.regions);
    inpaintMs = Math.round(performance.now() - t0);
    const images: Record<string, PatchImage> = {};
    for (const p of patches) engines[p.engine ?? "migan"] = (engines[p.engine ?? "migan"] ?? 0) + 1;
    for (const p of patches) images[p.id] = { x: p.x, y: p.y, image: await loadImage(Buffer.from(p.dataUrl.split(",")[1], "base64")), textBoxes: p.textBoxes, textExtent: p.textExtent, ink: p.ink, outline: p.outline, keepOut: p.keepOut };
    rctx.drawImage(d.canvas, 0, 0);
    const keep = new Set(rejected.filter((x) => x.reason === "bold-text").map((x) => x.id));
    renders = renderTranslation(rctx as unknown as Ctx2D, { w: d.w, h: d.h }, result.regions, result.translations, { patches: images, keep });
  }
  const qa = score(page.id, result, renders, inpaintMs, rejected);
  report.push(qa);
  if (debug) {
    for (const r of result.regions) {
      const st = renders.find((x) => x.id === r.id)?.status ?? "none";
      rctx.strokeStyle = st === "lettered" ? "#16a34a" : st === "needs-inpaint" ? "#dc2626" : "#7c3aed";
      rctx.lineWidth = 2;
      rctx.strokeRect(r.box.x, r.box.y, r.box.w, r.box.h);
      if (r.bubble) {
        rctx.strokeStyle = "#2563eb88";
        rctx.strokeRect(r.bubble.x, r.bubble.y, r.bubble.w, r.bubble.h);
      }
      rctx.fillStyle = "#000";
      rctx.font = "bold 14px sans-serif";
      rctx.fillText(r.id, r.box.x, r.box.y - 3);
    }
  }
  ctx.drawImage(right, d.w, 0);
  await writeFile(join(out, `${page.id}.png`), await canvas.encode("png"));
  const flags = [
    qa.residue.length && `residue ${qa.residue.join(",")}`,
    qa.overflow.length && `overflow ${qa.overflow.join(",")}`,
    qa.overlaps.length && `overlap ${qa.overlaps.join(",")}`,
    qa.overUnerased.length && `over-unerased ${qa.overUnerased.join(",")}`,
    qa.outsideBalloon.length && `outside-balloon ${qa.outsideBalloon.join(",")}`,
    qa.waitingInpaint && `not-redrawn ${renders.filter((r) => r.status === "needs-inpaint").map((r) => r.id).join(",")}`,
  ].filter(Boolean);
  console.log(`${page.id.padEnd(9)} lettered ${qa.lettered}/${qa.regions - qa.sfxOrDecorative} translatable, sfx/decor ${qa.sfxOrDecorative}, inpaint ${need.length} in ${inpaintMs} ms ${flags.length ? "| " + flags.join(" | ") : "| clean"}${qa.shaped.length ? ` (shaped ${qa.shaped.join(",")})` : ""}`);
}

const total = (k: keyof PageQa) => report.reduce((s, r) => s + (Array.isArray(r[k]) ? (r[k] as string[]).length : Number(r[k]) || 0), 0);
console.log(
  `\nTOTAL lettered ${total("lettered")}, not redrawn ${total("waitingInpaint")}, residue ${total("residue")}, overflow ${total("overflow")}, ` +
    `overlap ${total("overlaps")}, over-unerased ${total("overUnerased")}, outside-balloon ${total("outsideBalloon")}, inpaint ${total("inpaintMs")} ms`,
);
await mkdir(join(PRIVATE_DIR, "qa"), { recursive: true });
await writeFile(join(PRIVATE_DIR, "qa", `${evalRun ?? ns}-${safe(model)}.json`), JSON.stringify(report, null, 1), "utf8");
console.log(`inpainting ${INPAINT_ENGINE} on ${INPAINT_DEVICE}: patches by engine ${JSON.stringify(engines)}`);
console.log("written to", out);

function score(pageId: string, result: PageResult, renders: RegionRender[], inpaintMs: number, rejected: Rejected[]): PageQa {
  const byId = new Map(result.regions.map((r) => [r.id, r]));
  const lettered = renders.filter((r) => r.status === "lettered" && r.textBox);
  const unerased = renders.filter((r) => r.status === "sfx" || r.status === "skipped" || r.status === "needs-inpaint");
  const overlapArea = (a: Box, b: Box) => {
    const i = intersect(a, b);
    return i ? i.w * i.h : 0;
  };
  const overlaps: string[] = [];
  for (let i = 0; i < lettered.length; i++) {
    for (let j = i + 1; j < lettered.length; j++) {
      const [a, b] = [lettered[i], lettered[j]];
      // Tilted lettering is compared as drawn: overlapping by more than 2 px.
      const hit = a.textQuad && b.textQuad && (a.angle !== undefined || b.angle !== undefined) ? quadsTouch(a.textQuad, b.textQuad, -2) : overlapArea(a.textBox!, b.textBox!) > 16;
      if (hit) overlaps.push(`${a.id}+${b.id}`);
    }
  }
  const overUnerased: string[] = [];
  for (const l of lettered) {
    for (const u of unerased) {
      const reg = byId.get(u.id)!;
      if (overlapArea(l.textBox!, reg.box) > 16) overUnerased.push(`${l.id}>${u.id}`);
    }
  }
  const outsideBalloon = lettered
    .filter((l) => {
      const reg = byId.get(l.id)!;
      if (!reg.bubble) return false;
      const b = expand(reg.bubble, 3);
      const t = l.textBox!;
      return t.x < b.x || t.y < b.y || t.x + t.w > b.x + b.w || t.y + t.h > b.y + b.h;
    })
    .map((l) => l.id);
  return {
    pageId,
    regions: result.regions.length,
    lettered: lettered.length,
    waitingInpaint: renders.filter((r) => r.status === "needs-inpaint").length,
    sfxOrDecorative: renders.filter((r) => r.status === "sfx" || r.status === "skipped" || r.status === "empty").length,
    residue: lettered.filter((r) => (r.residue ?? 0) > MAX_RESIDUE).map((r) => r.id),
    overflow: lettered.filter((r) => r.overflow).map((r) => r.id),
    overlaps,
    overUnerased,
    outsideBalloon,
    inpaintMs,
    rejected: rejected.map((r) => `${r.id}:${r.reason}`),
    shaped: [
      ...lettered
        .filter((r) => r.angle !== undefined)
        .map((r) => `${r.id}:${((r.angle! * 180) / Math.PI).toFixed(0)}${r.curved ? "~" : ""}${r.printedLines ? `=${r.printedLines}` : ""}`),
      ...lettered.filter((r) => r.display).map((r) => `${r.id}!${r.display}`),
    ],
  };
}
