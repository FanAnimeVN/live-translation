import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import * as ort from "onnxruntime-node";
import { createCanvas } from "@napi-rs/canvas";
import { area, artTextMask, clampBox, containment, expand, glyphResidue, holeRingStd, patchBlends, roundBox, textArea, type Box, type InpaintJob, type PageResult, type PatchData, type RGBAImage, type TextRegion } from "@lt/core";
import { cornersFlat } from "@lt/render";
import { detectInCrop } from "./detector";
import { INPAINT_DEVICE, INPAINT_ENGINE, LAMA_DEVICE, sessionOptions, type InpaintDevice } from "./device";
import { ROOT } from "./env";
import type { DecodedPage } from "./image";
import { loadLama, runLama } from "./lama";

/** andraniksargsyan/migan @ 406830d0fa60666da0071c342ad2fbc8f30c5c64, MIT (Picsart AI Research). */
export const MIGAN_FILE = join(ROOT, "models", "inpaint", "migan_pipeline_v2.onnx");
export const MIGAN_SHA256 = "6f1f3530a1a2324b19752018ce756088b07973cda8d7d890034ace5c8a48c40b";

const sessions = new Map<InpaintDevice, Promise<ort.InferenceSession>>();

export function loadInpainter(device: InpaintDevice = INPAINT_DEVICE): Promise<ort.InferenceSession> {
  let s = sessions.get(device);
  if (!s) {
    s = (async () => {
      const bytes = await readFile(MIGAN_FILE);
      const sha = createHash("sha256").update(bytes).digest("hex");
      if (sha !== MIGAN_SHA256) throw new Error(`MI-GAN checksum mismatch (${sha})`);
      return ort.InferenceSession.create(bytes, sessionOptions(device));
    })();
    sessions.set(device, s);
  }
  return s;
}

/** LaMa once loaded; until then (it takes ~20 s) every hole goes to MI-GAN rather than wait. */
let lama: ort.InferenceSession | undefined;
let lamaLoading: Promise<void> | undefined;
const lamaWanted = INPAINT_ENGINE === "lama" || (INPAINT_ENGINE === "auto" && INPAINT_DEVICE !== "cpu");

/** Load the inpainters the settings call for, in the background (server start). */
export function warmInpainters(): Promise<void> {
  const migan = loadInpainter().then(() => undefined);
  if (lamaWanted)
    lamaLoading ??= loadLama("lama", LAMA_DEVICE).then(
      (s) => void (lama = s),
      (e: Error) => console.error(`LaMa failed to load on ${LAMA_DEVICE}, MI-GAN only:`, e.message),
    );
  return Promise.all([migan, lamaLoading]).then(() => undefined);
}

/** The engine for one hole: LaMa where it is ready and wanted, MI-GAN otherwise. */
function engineFor(full: RGBAImage, job: InpaintJob): "migan" | "lama" {
  if (!lama) return "migan";
  if (INPAINT_ENGINE === "lama") return "lama";
  // Textured surroundings (hatching, screentone): MI-GAN leaves grey ghosts of the letters there.
  return holeRingStd(full, job) > TEXTURED_RING ? "lama" : "migan";
}

/** Ring spread above which a hole counts as sitting in textured art. */
const TEXTURED_RING = 30;

export type Patch = PatchData;

/** Diagnostics for a reconstruction that needed the fallback (the text is still redrawn). */
export interface Rejected {
  id: string;
  /** bold-text: display lettering drawn with thick strokes stays part of the art (no patch). */
  reason: "rect-fallback" | "glyphs-survived" | "visible-patch" | "bold-text";
  coverage: number;
}

/** Glyph-shaped ink left in the text core after reconstruction that triggers a whole-box retry. */
const MAX_RESIDUE_AFTER = 0.02;

/** Reconstruct the artwork under each region's text (MI-GAN, or LaMa in textured art; see `engineFor`). */
export async function inpaintRegions(
  page: DecodedPage,
  regions: TextRegion[],
  charSizes: Record<string, number> = {},
  rejected: Rejected[] = [],
): Promise<Patch[]> {
  const s = await loadInpainter();
  if (lamaWanted) void warmInpainters();
  const full = page.ctx.getImageData(0, 0, page.w, page.h);
  let engine: "migan" | "lama" = "migan";
  const redraw = (job: InpaintJob) => {
    engine = engineFor(full, job);
    return engine === "lama" ? runLama(lama!, full, job) : runMigan(s, full, job);
  };
  const out: Patch[] = [];
  for (const r of regions) {
    const t0 = performance.now();
    const members = r.bubble ? textArea(r, cornersFlat(full, r.bubble)) : await refineTextBoxes(page, r);
    // The size guess is box area / character count: a tighter box means smaller glyphs.
    const cs = charSizes[r.id] && Math.sqrt((charSizes[r.id] ** 2 * members.reduce((a, m) => a + area(m), 0)) / area(r.box));
    let job = artTextMask(full, members, { charSize: cs });
    if (job.bold) {
      rejected.push({ id: r.id, reason: "bold-text", coverage: job.coverage });
      continue;
    }
    let result = await redraw(job);
    if (job.rect) rejected.push({ id: r.id, reason: "rect-fallback", coverage: job.coverage });
    else if (residueAfter(full, result, job, members, cs) > MAX_RESIDUE_AFTER) {
      // Strokes escaped the glyph mask: reconstruct the whole text box instead (protected art stays).
      rejected.push({ id: r.id, reason: "glyphs-survived", coverage: job.coverage });
      job = artTextMask(full, members, { charSize: cs, rect: true });
      result = await redraw(job);
    } else if (!patchBlends(full, result, job).ok) {
      rejected.push({ id: r.id, reason: "visible-patch", coverage: job.coverage });
    }
    const { x, y, w, h } = job.crop;
    const n = w * h;
    const canvas = createCanvas(w, h);
    const ctx = canvas.getContext("2d");
    const patch = ctx.createImageData(w, h);
    for (let p = 0; p < n; p++) {
      const px = p % w;
      const py = (p - px) / w;
      const i = ((y + py) * page.w + (x + px)) * 4;
      const hole = job.hole[p] === 1;
      // Only hole pixels change; everything else stays the source pixel.
      patch.data[p * 4] = hole ? result[p] : full.data[i];
      patch.data[p * 4 + 1] = hole ? result[n + p] : full.data[i + 1];
      patch.data[p * 4 + 2] = hole ? result[2 * n + p] : full.data[i + 2];
      // Transparent outside the hole: overlapping patches must never paint back source pixels.
      patch.data[p * 4 + 3] = hole ? 255 : 0;
    }
    ctx.putImageData(patch, 0, 0);
    const png = await canvas.encode("png");
    out.push({ id: r.id, x, y, w, h, dataUrl: `data:image/png;base64,${png.toString("base64")}`, coverage: job.coverage, ms: Math.round(performance.now() - t0), textBoxes: members, textExtent: job.extent, engine });
  }
  return out;
}

export async function runMigan(s: ort.InferenceSession, full: RGBAImage, job: InpaintJob): Promise<Uint8Array> {
  const { x, y, w, h } = job.crop;
  const n = w * h;
  const image = new Uint8Array(3 * n);
  const mask = new Uint8Array(n);
  for (let p = 0; p < n; p++) {
    const px = p % w;
    const py = (p - px) / w;
    const i = ((y + py) * full.width + (x + px)) * 4;
    image[p] = full.data[i];
    image[n + p] = full.data[i + 1];
    image[2 * n + p] = full.data[i + 2];
    mask[p] = job.hole[p] ? 0 : 255;
  }
  const res = await s.run({
    image: new ort.Tensor("uint8", image, [1, 3, h, w]),
    mask: new ort.Tensor("uint8", mask, [1, 1, h, w]),
  });
  return res.result.data as Uint8Array;
}

/**
 * Tight text boxes for a free-text region. The page detector sees small text at about
 * half size and returns loose boxes that swallow nearby art (a whisper beside a face);
 * detecting again on a zoomed crop boxes the text itself. Falls back to the region's
 * own boxes when nothing better is found.
 */
export async function refineTextBoxes(page: DecodedPage, r: TextRegion): Promise<Box[]> {
  const u = r.box;
  const crop = roundBox(clampBox(expand(u, Math.max(10, 0.4 * Math.max(u.w, u.h))), page.w, page.h));
  if (640 / Math.max(crop.w, crop.h) < 1.5) return r.members; // big text: page-level boxes are already tight
  const near = expand(u, 6);
  const boxes = (await detectInCrop(page, crop, 0.25)).map((d) => d.box).filter((b) => containment(b, near) >= 0.6);
  if (!boxes.length) return r.members;
  return boxes.reduce((a, b) => a + area(b), 0) < 0.9 * area(u) ? boxes : r.members;
}

/** Glyph residue of the text boxes after compositing the reconstruction into a copy of the crop. */
function residueAfter(full: RGBAImage, result: Uint8Array, job: InpaintJob, members: Box[], charSize?: number): number {
  const { x, y, w, h } = job.crop;
  const n = w * h;
  const data = new Uint8ClampedArray(n * 4);
  for (let p = 0; p < n; p++) {
    const px = p % w;
    const py = (p - px) / w;
    const i = ((y + py) * full.width + (x + px)) * 4;
    const hole = job.hole[p] === 1;
    data[p * 4] = hole ? result[p] : full.data[i];
    data[p * 4 + 1] = hole ? result[n + p] : full.data[i + 1];
    data[p * 4 + 2] = hole ? result[2 * n + p] : full.data[i + 2];
    data[p * 4 + 3] = 255;
  }
  const local = members.map((m) => ({ x: m.x - x, y: m.y - y, w: m.w, h: m.h }));
  return glyphResidue({ width: w, height: h, data }, local, charSize);
}

/** Estimated source glyph size per region, from the transcription length. */
export function charSizesFor(result: PageResult): Record<string, number> {
  const out: Record<string, number> = {};
  for (const r of result.regions) {
    const n = [...(result.translations[r.id]?.ja ?? "").replace(/\s/g, "")].length;
    if (n) out[r.id] = Math.sqrt(area(r.box) / n);
  }
  return out;
}
